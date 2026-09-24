"""Bounded algorithm adapted from ../day-18-dependency-watch/lookup.py.

No imports from Day 18: the entrypoint, scheduler and SQLite are independent.
"""
import asyncio
from datetime import datetime, timezone
import time
from uuid import uuid4

import httpx
from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

from .contracts import Coordinates, LookupResult, source_url

MAX_BODY_BYTES = 2 * 1024 * 1024
UPSTREAM_SECONDS = 15


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class LookupFailure(Exception):
    def __init__(self, category, lookup_id=None):
        self.category, self.lookup_id = category, lookup_id
        super().__init__(f"{category}; lookup_id={lookup_id}" if lookup_id else category)


def parse_index(body, group_id, artifact_id):
    try:
        root = ElementTree.fromstring(body, forbid_dtd=True)
    except (ElementTree.ParseError, DefusedXmlException, ValueError) as exc:
        raise LookupFailure("upstream_xml") from exc
    if root.tag != group_id:
        raise LookupFailure("upstream_xml")
    matches = [child for child in root if child.tag == artifact_id]
    if not matches:
        return "artifact_not_found", []
    if len(matches) != 1 or "versions" not in matches[0].attrib:
        raise LookupFailure("upstream_xml")
    raw = matches[0].attrib["versions"]
    if not raw:
        return "no_versions", []
    versions = raw.split(",")
    if any(not v or any(c.isspace() for c in v) for v in versions):
        raise LookupFailure("upstream_xml")
    return "found", versions


async def lookup(group_id, artifact_id, *, transport=None, clock=utc_now, emit=lambda **kw: None):
    Coordinates(group_id=group_id, artifact_id=artifact_id)
    lookup_id, url = str(uuid4()), source_url(group_id)
    started, http_status = time.monotonic(), None
    outcome, versions = "upstream_network", []
    try:
        async with asyncio.timeout(UPSTREAM_SECONDS):
            async with httpx.AsyncClient(transport=transport, timeout=UPSTREAM_SECONDS,
                                         follow_redirects=False) as client:
                async with client.stream("GET", url) as response:
                    http_status = response.status_code
                    if http_status == 404:
                        outcome = "group_not_found"
                    elif not 200 <= http_status < 300:
                        raise LookupFailure("upstream_http")
                    else:
                        body = bytearray()
                        async for chunk in response.aiter_bytes():
                            if len(body) + len(chunk) > MAX_BODY_BYTES:
                                raise LookupFailure("upstream_response")
                            body.extend(chunk)
                        outcome, versions = parse_index(bytes(body), group_id, artifact_id)
        return LookupResult(status=outcome, versions=versions, lookup_id=lookup_id,
            checked_at=clock(), group_id=group_id, artifact_id=artifact_id, source_url=url)
    except asyncio.CancelledError:
        outcome = "interrupted"
        raise
    except (TimeoutError, httpx.TimeoutException) as exc:
        outcome = "upstream_timeout"
        raise LookupFailure(outcome, lookup_id) from exc
    except httpx.RequestError as exc:
        outcome = "upstream_network"
        raise LookupFailure(outcome, lookup_id) from exc
    except LookupFailure as exc:
        outcome = exc.category
        raise LookupFailure(outcome, lookup_id) from exc
    finally:
        emit(event="google_maven_lookup", lookup_id=lookup_id, group_id=group_id,
             artifact_id=artifact_id, source_url=url, http_status=http_status, outcome=outcome,
             elapsed_ms=round((time.monotonic() - started) * 1000), versions_count=len(versions))
