"""Bounded Google Maven lookup adapted from Day 17, independent of MCP."""
import asyncio
from dataclasses import dataclass
import json
import logging
import time
from uuid import uuid4

import httpx
from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException
from pydantic import TypeAdapter

from watch_models import ArtifactId, GroupId, utc_ms, timestamp

MAX_BODY_BYTES = 2 * 1024 * 1024
UPSTREAM_SECONDS = 15
logger = logging.getLogger("day18.lookup")


@dataclass(frozen=True)
class LookupResult:
    status: str
    versions: list[str]
    lookup_id: str
    checked_at: int


class LookupFailure(Exception):
    def __init__(self, category, lookup_id=None, checked_at=None):
        super().__init__(category)
        self.category, self.lookup_id, self.checked_at = category, lookup_id, checked_at


def source_url(group_id):
    return f"https://dl.google.com/dl/android/maven2/{group_id.replace('.', '/')}/group-index.xml"


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


async def lookup(group_id, artifact_id, *, transport=None, clock=utc_ms):
    TypeAdapter(GroupId).validate_python(group_id)
    TypeAdapter(ArtifactId).validate_python(artifact_id)
    lookup_id, url = str(uuid4()), source_url(group_id)
    started, http_status = time.monotonic(), None
    checked_at = None
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
        checked_at = clock()
        return LookupResult(outcome, versions, lookup_id, checked_at)
    except asyncio.CancelledError:
        outcome = "interrupted"
        raise
    except (TimeoutError, httpx.TimeoutException) as exc:
        outcome = "upstream_timeout"
        checked_at = clock()
        raise LookupFailure(outcome, lookup_id, checked_at) from exc
    except httpx.RequestError as exc:
        outcome = "upstream_network"
        checked_at = clock()
        raise LookupFailure(outcome, lookup_id, checked_at) from exc
    except LookupFailure as exc:
        outcome = exc.category
        checked_at = clock()
        raise LookupFailure(outcome, lookup_id, checked_at) from exc
    finally:
        logger.info(json.dumps({"event": "google_maven_lookup", "lookup_id": lookup_id,
            "group_id": group_id, "artifact_id": artifact_id, "source_url": url,
            "checked_at": timestamp(checked_at), "http_status": http_status, "outcome": outcome,
            "elapsed_ms": round((time.monotonic() - started) * 1000), "versions_count": len(versions)}))
