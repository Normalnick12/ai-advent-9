"""Authenticated remote MCP plus one supervised background scheduler."""
import asyncio
from contextlib import asynccontextmanager, suppress
import hmac
import logging
import os
from pathlib import Path
import re
from uuid import UUID

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from starlette.responses import JSONResponse
from starlette.routing import Route

from scheduler import Scheduler
from storage import Store
from watch_models import ArtifactId, CreateInput, GroupId, Interval, MaxRuns, Receipt, Summary, WatchError


class OwnerLock:
    """OS releases the advisory lock on process death; never delete the lock file."""
    def __init__(self, path):
        self.path, self.file = Path(path), None

    def acquire(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.file = self.path.open("a+b")
        try:
            if os.name == "nt":
                import msvcrt
                self.file.seek(0)
                if not self.file.read(1):
                    self.file.write(b"0")
                    self.file.flush()
                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.file.close()
            self.file = None
            raise WatchError("scheduler_owner_exists") from None

    def release(self):
        if self.file:
            self.file.close()
            self.file = None


def create_server(get_store):
    server = MCPServer("Dependency Watch", version="0.1.0")

    @server.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False,
                                             idempotent_hint=False, open_world_hint=True))
    async def create_dependency_watch(group_id: GroupId, artifact_id: ArtifactId,
                                      max_runs: MaxRuns, interval_seconds: Interval = 21600) -> Receipt:
        """Schedule finite Google Maven checks; every accepted call creates a NEW watch.

        No retry or idempotent-create guarantee. max_runs includes failures. Normally
        interval_seconds >= 3600; short demo intervals require server configuration.
        Creation only persists a schedule; it does not perform a lookup.
        """
        try:
            return get_store().create(CreateInput(group_id=group_id, artifact_id=artifact_id,
                max_runs=max_runs, interval_seconds=interval_seconds))
        except WatchError as exc:
            raise ToolError(str(exc)) from None

    @server.tool(annotations=ToolAnnotations(read_only_hint=True, destructive_hint=False,
                                             idempotent_hint=True, open_world_hint=False))
    async def get_dependency_watch_summary(watch_id: UUID) -> Summary:
        """Read committed deterministic facts for exactly this watch. No new checks.

        Null version counts mean no comparable snapshot. Failed/interrupted runs
        count toward max_runs. Model prose must not replace these persisted facts.
        """
        try:
            return get_store().summary(watch_id)
        except WatchError as exc:
            raise ToolError(str(exc)) from None
    return server


class BearerMiddleware:
    def __init__(self, app, token):
        self.app, self.expected = app, ("Bearer " + token).encode("utf-8")

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and (scope["path"] == "/mcp" or scope["path"].startswith("/mcp/")):
            values = [v for k, v in scope["headers"] if k.lower() == b"authorization"]
            if len(values) != 1 or not hmac.compare_digest(values[0], self.expected):
                await JSONResponse({"error": "unauthorized"}, 401,
                                   headers={"WWW-Authenticate": "Bearer"})(scope, receive, send)
                return
        await self.app(scope, receive, send)


def security(host):
    hosts = ["localhost", "localhost:*", "127.0.0.1", "127.0.0.1:*"]
    origins = ["http://localhost:*", "http://127.0.0.1:*"]
    if host:
        if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", host):
            raise WatchError("invalid_public_host")
        hosts += [host, host + ":443"]
        origins += ["https://" + host, "https://" + host + ":443"]
    return TransportSecuritySettings(enable_dns_rebinding_protection=True,
        allowed_hosts=hosts, allowed_origins=origins)


def create_app(*, path=None, token=None, public_host=None, allow_short=None,
               clock=None, lookup_fn=None, fatal_callback=None):
    token = token if token is not None else os.getenv("DAY18_MCP_TOKEN", "")
    if not token or token.strip() != token or any(c.isspace() for c in token) or len(token) < 32:
        raise WatchError("missing_or_invalid_bearer_token")
    path = Path(path or os.getenv("DAY18_DATABASE_PATH", ".local/day18/watch.sqlite3")).resolve()
    public_host = public_host or os.getenv("DAY18_MCP_PUBLIC_HOST")
    if allow_short is None:
        flag = os.getenv("DAY18_ALLOW_SHORT_INTERVALS", "false")
        if flag not in ("true", "false"):
            raise WatchError("invalid_short_interval_configuration")
        allow_short = flag == "true"
    state = {"store": None, "ready": False}

    def get_store():
        if not state["ready"] or not state["store"].healthy:
            raise WatchError("service_unavailable")
        return state["store"]

    server = create_server(get_store)
    app = server.streamable_http_app(streamable_http_path="/mcp", json_response=True,
        stateless_http=True, transport_security=security(public_host))
    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(app):
        lock = OwnerLock(str(path) + ".lock")
        lock.acquire()
        task = None
        try:
            store = Store(path, allow_short=allow_short, **({"clock": clock} if clock else {}))
            store.recover()  # commit BEFORE accepting summary or starting the worker
            state["store"] = store
            scheduler = Scheduler(store, **({"clock": clock} if clock else {}),
                                  **({"lookup_fn": lookup_fn} if lookup_fn else {}))
            app.state.store, app.state.scheduler = store, scheduler
            async with original_lifespan(app):
                state["ready"] = True
                task = asyncio.create_task(scheduler.run(), name="day18-scheduler")
                app.state.worker = task

                def worker_done(done):
                    if scheduler.stop_event.is_set():
                        return
                    state["ready"] = False
                    logging.getLogger("day18.runtime").error('{"event":"scheduler_failed"}')
                    if fatal_callback:
                        fatal_callback()
                task.add_done_callback(worker_done)
                yield
                state["ready"] = False
                scheduler.stop_event.set()
        finally:
            state["ready"] = False
            if task:
                if not task.done():
                    task.cancel()  # a persisted running slot is recovered on next startup
                with suppress(asyncio.CancelledError, Exception):
                    await task
            lock.release()

    async def health(request):
        healthy = state["ready"] and state["store"].healthy
        return JSONResponse({"status": "ok" if healthy else "unavailable"}, 200 if healthy else 503)

    app.router.lifespan_context = lifespan
    app.routes.append(Route("/health", health))
    app.add_middleware(BearerMiddleware, token=token)
    return app
