"""Small HTTP boundary: authentication and bounded body before application parsing."""
import asyncio
from contextlib import asynccontextmanager
import hmac
import json
import logging
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from .service import ApiError, Service, validate_chat

LOG = logging.getLogger("laa.http")
ROUTES = {("GET", "/healthz"): "health", ("GET", "/readyz"): "ready",
          ("GET", "/v1/status"): "status", ("POST", "/v1/chat"): "chat"}


def error_response(error, request_id):
    headers = {"Cache-Control": "no-store", "X-Request-ID": request_id}
    if error.retry is not None:
        headers["Retry-After"] = str(error.retry)
    if error.status == 401:
        headers["WWW-Authenticate"] = "Bearer"
    return JSONResponse({"error": {"code": error.code, "message": error.code}, "request_id": request_id},
                        status_code=error.status, headers=headers)


class Boundary:
    def __init__(self, app, service, body_timeout=10):
        self.app, self.service, self.body_timeout = app, service, body_timeout

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id, started = uuid4().hex, time.monotonic()
        scope.setdefault("state", {})["request_id"] = request_id
        route = ROUTES.get((scope["method"], scope["path"]), "unknown")
        status = 500
        async def safe_send(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message["headers"] = [(k, v) for k, v in message.get("headers", [])
                                      if k.lower() not in {b"cache-control", b"x-request-id"}] + [
                    (b"cache-control", b"no-store"), (b"x-request-id", request_id.encode())]
            await send(message)
        try:
            if route != "health":
                auth = [v for k, v in scope["headers"] if k.lower() == b"authorization"]
                label = None
                if len(auth) == 1 and len(auth[0]) <= 256 and auth[0].startswith(b"Bearer "):
                    token = auth[0][7:]
                    for candidate, expected in self.service.config.tokens.items():
                        if hmac.compare_digest(token, expected.encode("ascii")):
                            label = candidate
                if label is None:
                    raise ApiError(401, "unauthenticated")
                if route == "unknown":
                    raise ApiError(404, "not_found")
                self.service.buckets[label, "chat" if route == "chat" else "status"].take()
            if route == "chat":
                headers = dict(scope["headers"])
                if (headers.get(b"content-type", b"").split(b";")[0].strip().lower() != b"application/json"
                        or headers.get(b"content-encoding", b"identity").lower() != b"identity"):
                    raise ApiError(415, "unsupported_media_type")
                raw_length = headers.get(b"content-length")
                if raw_length:
                    try:
                        length = int(raw_length)
                    except ValueError:
                        raise ApiError(422, "invalid_request") from None
                    if length < 0:
                        raise ApiError(422, "invalid_request")
                    if length > 32768:
                        raise ApiError(413, "request_too_large")
                data = bytearray()
                try:
                    async with asyncio.timeout(self.body_timeout):
                        while True:
                            msg = await receive()
                            if msg["type"] == "http.disconnect":
                                raise ApiError(422, "invalid_request")
                            chunk = msg.get("body", b"")
                            if len(data) + len(chunk) > 32768:
                                raise ApiError(413, "request_too_large")
                            data.extend(chunk)
                            if not msg.get("more_body", False):
                                break
                except TimeoutError:
                    raise ApiError(504, "body_timeout") from None
                # Parse once; no upstream I/O and no Pydantic input echoes.
                try:
                    value = json.loads(data)
                except (ValueError, RecursionError):
                    raise ApiError(422, "invalid_request") from None
                scope["state"]["chat"] = validate_chat(value)
            await self.app(scope, receive, safe_send)
        except ApiError as exc:
            await error_response(exc, request_id)(scope, receive, safe_send)
        except Exception:
            await error_response(ApiError(500, "internal_error"), request_id)(scope, receive, safe_send)
        finally:
            LOG.info("http_finished request_id=%s route=%s status=%s elapsed_ms=%s",
                     request_id, route, status, round((time.monotonic() - started) * 1000))


def create_app(config, transport=None, *, deadline=120, ready_timeout=5, body_timeout=10, shutdown_timeout=5, clock=time.monotonic):
    service = Service(config, transport, clock=clock, deadline=deadline,
                      ready_timeout=ready_timeout, shutdown_timeout=shutdown_timeout)
    @asynccontextmanager
    async def lifespan(app):
        yield
        await service.close()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None, debug=False)
    app.state.service = service
    app.add_middleware(Boundary, service=service, body_timeout=body_timeout)

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return error_response(ApiError(exc.status_code, "not_found"), request.state.request_id)

    @app.get("/healthz")
    async def health():
        return {"status": "ok"}

    @app.get("/readyz")
    async def ready():
        ok = await service.readiness()
        return JSONResponse({"ready": ok}, status_code=200 if ok else 503)

    @app.get("/v1/status")
    async def status():
        return service.status()

    @app.post("/v1/chat")
    async def chat(request: Request):
        async def disconnected():
            while True:
                if (await request.receive())["type"] == "http.disconnect":
                    return
        return await service.chat(request.state.chat, request.state.request_id, disconnected)

    return app
