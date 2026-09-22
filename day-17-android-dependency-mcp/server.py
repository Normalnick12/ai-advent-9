"""One read-only Google Maven tool, served by the official MCP SDK."""

import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import uuid4

import httpx
from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field, TypeAdapter
from starlette.responses import JSONResponse
from starlette.routing import Route

GROUP_PATTERN = r"^[A-Za-z0-9_][A-Za-z0-9_-]*(?:\.[A-Za-z0-9_][A-Za-z0-9_-]*)*$"
ARTIFACT_PATTERN = r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$"
GroupId = Annotated[str, Field(strict=True, min_length=1, max_length=256,
    pattern=GROUP_PATTERN, description="Exact Maven group, e.g. androidx.core. No spaces or URL/path syntax.")]
ArtifactId = Annotated[str, Field(strict=True, min_length=1, max_length=256,
    pattern=ARTIFACT_PATTERN, description="Exact artifact in this group, e.g. core-ktx. No URL/path syntax.")]
MAX_BODY_BYTES = 2 * 1024 * 1024
UPSTREAM_SECONDS = 15
logger = logging.getLogger("google_maven_lookup")


class VersionsResult(BaseModel):
    status: Literal["found", "group_not_found", "artifact_not_found", "no_versions"]
    group_id: str
    artifact_id: str
    versions: list[str]
    source_url: str
    checked_at: datetime
    lookup_id: str


class LookupFailure(Exception):
    def __init__(self, category: str):
        self.category = category
        super().__init__(category)


def source_url(group_id: str) -> str:
    return f"https://dl.google.com/dl/android/maven2/{group_id.replace('.', '/')}/group-index.xml"


def parse_index(body: bytes, group_id: str, artifact_id: str) -> tuple[str, list[str]]:
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
    if raw == "":
        return "no_versions", []
    versions = raw.split(",")
    if any(not v or any(c.isspace() for c in v) for v in versions):
        raise LookupFailure("upstream_xml")
    return "found", versions


async def lookup(group_id: str, artifact_id: str, transport=None) -> VersionsResult:
    # Also validate direct calls; decorated calls are validated by the SDK first.
    TypeAdapter(GroupId).validate_python(group_id)
    TypeAdapter(ArtifactId).validate_python(artifact_id)
    lookup_id = str(uuid4())
    url = source_url(group_id)
    started = time.monotonic()
    http_status = None
    outcome = "upstream_network"
    versions: list[str] = []
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
                        chunks = bytearray()
                        async for chunk in response.aiter_bytes():
                            if len(chunks) + len(chunk) > MAX_BODY_BYTES:
                                raise LookupFailure("upstream_response")
                            chunks.extend(chunk)
                        outcome, versions = parse_index(bytes(chunks), group_id, artifact_id)
        return VersionsResult(status=outcome, group_id=group_id, artifact_id=artifact_id,
                              versions=versions, source_url=url,
                              checked_at=datetime.now(timezone.utc), lookup_id=lookup_id)
    except (TimeoutError, httpx.TimeoutException) as exc:
        outcome = "upstream_timeout"
        raise ToolError(f"{outcome}; lookup_id={lookup_id}") from exc
    except httpx.RequestError as exc:
        outcome = "upstream_network"
        raise ToolError(f"{outcome}; lookup_id={lookup_id}") from exc
    except LookupFailure as exc:
        outcome = exc.category
        raise ToolError(f"{outcome}; lookup_id={lookup_id}") from exc
    finally:
        logger.info(json.dumps({"event": "google_maven_lookup", "lookup_id": lookup_id,
            "group_id": group_id, "artifact_id": artifact_id, "source_url": url,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "elapsed_ms": round((time.monotonic() - started) * 1000),
            "http_status": http_status, "outcome": outcome, "versions_count": len(versions)}))


def create_server(transport=None) -> MCPServer:
    server = MCPServer("Android Dependency MCP", version="0.1.0")

    @server.tool(annotations=ToolAnnotations(read_only_hint=True, destructive_hint=False,
                                             idempotent_hint=True, open_world_hint=True))
    async def get_google_maven_versions(group_id: GroupId, artifact_id: ArtifactId) -> VersionsResult:
        """Get all published versions of an exact dependency from Google Maven only.

        Returns source order, not latest/stable recommendations or compatibility/security advice.
        Negative lookups describe Google Maven only; upstream failures are tool errors.
        """
        return await lookup(group_id, artifact_id, transport)

    return server


def transport_security(public_host: str | None = None) -> TransportSecuritySettings:
    hosts = ["localhost", "localhost:*", "127.0.0.1", "127.0.0.1:*"]
    origins = ["http://localhost:*", "http://127.0.0.1:*"]
    if public_host:
        if not re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?", public_host):
            raise ValueError("MCP_PUBLIC_HOST must be a hostname, without scheme/path/port")
        hosts.extend([public_host, f"{public_host}:443"])
        origins.extend([f"https://{public_host}", f"https://{public_host}:443"])
    return TransportSecuritySettings(enable_dns_rebinding_protection=True,
                                     allowed_hosts=hosts, allowed_origins=origins)


async def health(request):
    return JSONResponse({"status": "ok"})


def create_app(server=None, public_host=None):
    server = server or create_server()
    app = server.streamable_http_app(streamable_http_path="/mcp", json_response=True,
        stateless_http=True, transport_security=transport_security(public_host))
    app.routes.append(Route("/health", health))
    return app


logging.basicConfig(level=logging.INFO)
mcp = create_server()
app = create_app(mcp, os.getenv("MCP_PUBLIC_HOST") or os.getenv("RENDER_EXTERNAL_HOSTNAME"))
