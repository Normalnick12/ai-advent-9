"""Exactly three tools, no scheduler and no server-side orchestration."""
from contextvars import ContextVar
import hmac
import json
import logging
import os
import re
import time
from uuid import uuid4

from mcp.server import MCPServer
from mcp.server.mcpserver.tools import Tool
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import ValidationError
from starlette.responses import JSONResponse
from starlette.routing import Route

from .contracts import Coordinates, LookupResult, DependencyReport, SaveReceipt, SummaryInput, SaveInput
from .lookup import lookup, LookupFailure, utc_now
from .report import digest, summarize
from .storage import ReportStore, StorageFailure, safe_root

NAMES = ("get_google_maven_versions", "summarize_dependency_versions", "save_dependency_report")
INPUTS = dict(zip(NAMES, (Coordinates, SummaryInput, SaveInput)))
MAX_REQUEST_BYTES = 32 * 1024 * 1024  # Includes escaping of a complete 2 MiB XML-derived lookup.
invocation = ContextVar("day19_invocation", default=None)


class Events:
    def __init__(self, sink=None):
        self.process_id, self.sequence = str(uuid4()), 0
        self.sink = sink or (lambda event: logging.getLogger("day19.events").info(json.dumps(event)))

    def emit(self, **fields):
        self.sequence += 1
        self.sink(dict(fields, process_id=self.process_id, sequence=self.sequence,
                       monotonic_ns=time.monotonic_ns(), at=utc_now(), invocation_id=invocation.get()))


class ObservedTool(Tool):
    """Pinned MCP 2.2 Tool extension: validate raw JSON BEFORE SDK pre-parsing.

    The SDK's default argument model ignores extras and parses JSON strings. Our
    strict model checks the unmodified transport object and publishes its schema.
    """
    async def run(self, arguments, context, convert_result=False):
        events = self.fn.__day19_events__
        token = invocation.set(str(uuid4()))
        input_hash = digest(arguments)
        lookup_id = None
        events.emit(event="tool_start", tool=self.name, input_sha256=input_hash)
        try:
            try:
                parsed = INPUTS[self.name].model_validate(arguments)
            except ValidationError:
                raise ToolError("invalid_arguments") from None
            values = {k: getattr(parsed, k) for k in type(parsed).model_fields}
            result = await self.fn(**values)
            lookup_id = result.lookup_id
            converted = self.fn_metadata.convert_result(result) if convert_result else result
            events.emit(event="tool_end", tool=self.name, outcome="completed", lookup_id=lookup_id,
                        input_sha256=input_hash, output_sha256=digest(result.model_dump()))
            return converted
        except (LookupFailure, StorageFailure, ToolError) as exc:
            lookup_id = getattr(exc, "lookup_id", None)
            events.emit(event="tool_end", tool=self.name, outcome="error", lookup_id=lookup_id,
                        input_sha256=input_hash, category=str(exc).split(";")[0])
            raise ToolError(str(exc)) from None
        except Exception:
            events.emit(event="tool_end", tool=self.name, outcome="error", lookup_id=lookup_id,
                        input_sha256=input_hash, category="internal_error")
            raise ToolError("internal_error") from None
        finally:
            invocation.reset(token)


def create_server(root, *, transport=None, clock=utc_now, events=None):
    events = events or Events()
    store = ReportStore(root)

    async def get_google_maven_versions(group_id: str, artifact_id: str) -> LookupResult:
        """Fetch ALL Google Maven versions in source order. Pass the ENTIRE result to summarize."""
        return await lookup(group_id, artifact_id, transport=transport, clock=clock, emit=events.emit)

    async def summarize_dependency_versions(lookup: LookupResult) -> DependencyReport:
        """Pass the complete lookup object unchanged. Compute count, last three and hash without I/O."""
        return summarize(lookup)

    async def save_dependency_report(report: DependencyReport) -> SaveReceipt:
        """Pass the complete report unchanged. Save canonical JSON in a fixed server directory.

        No paths or arbitrary content accepted. A repeated identical report has the same receipt.
        """
        return store.save(report)

    tools = []
    for index, fn in enumerate((get_google_maven_versions, summarize_dependency_versions, save_dependency_report)):
        fn.__day19_events__ = events
        tool = ObservedTool.from_function(fn, annotations=ToolAnnotations(
            read_only_hint=index < 2, destructive_hint=False, idempotent_hint=True, open_world_hint=index == 0))
        tool.parameters = INPUTS[fn.__name__].model_json_schema()
        tools.append(tool)
    return MCPServer("Dependency Composition", version="0.1.0", tools=tools)


class Guard:
    def __init__(self, app, token):
        self.app, self.expected = app, ("Bearer " + token).encode()

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and (scope["path"] == "/mcp" or scope["path"].startswith("/mcp/")):
            auth = [v for k, v in scope["headers"] if k.lower() == b"authorization"]
            if len(auth) != 1 or not hmac.compare_digest(auth[0], self.expected):
                return await JSONResponse({"error": "unauthorized"}, 401)(scope, receive, send)
            body = bytearray()
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                body.extend(message.get("body", b""))
                if len(body) > MAX_REQUEST_BYTES:
                    return await JSONResponse({"error": "request_too_large"}, 413)(scope, receive, send)
                if not message.get("more_body", False):
                    break
            consumed = False

            async def bounded_receive():
                nonlocal consumed
                if not consumed:
                    consumed = True
                    return {"type": "http.request", "body": bytes(body), "more_body": False}
                return await receive()
            return await self.app(scope, bounded_receive, send)
        return await self.app(scope, receive, send)


def create_app(*, root=None, token=None, public_host=None, transport=None, events=None):
    token = token if token is not None else os.getenv("DAY19_MCP_TOKEN", "")
    host = public_host if public_host is not None else os.getenv("DAY19_MCP_PUBLIC_HOST", "")
    if len(token) < 32 or any(c.isspace() for c in token):
        raise ValueError("missing_or_invalid_bearer_token")
    if host and not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", host):
        raise ValueError("invalid_public_host")
    root = safe_root(root or os.getenv("DAY19_REPORTS_DIR", "/var/lib/day19/reports"))
    server = create_server(root, transport=transport, events=events)
    security = TransportSecuritySettings(enable_dns_rebinding_protection=True,
        allowed_hosts=["localhost", "localhost:*", "127.0.0.1", "127.0.0.1:*"] + ([host, host + ":443"] if host else []),
        allowed_origins=["http://localhost:*", "http://127.0.0.1:*"] + (["https://" + host, "https://" + host + ":443"] if host else []))
    app = server.streamable_http_app(streamable_http_path="/mcp", json_response=True,
        stateless_http=True, transport_security=security)

    async def health(request):
        return JSONResponse({"status": "ok"})
    app.routes.append(Route("/health", health))
    return Guard(app, token)
