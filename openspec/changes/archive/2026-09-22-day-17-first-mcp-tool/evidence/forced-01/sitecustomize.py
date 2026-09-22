"""Local passive observer for one authorized Android attempt; no request generation."""
import json
import os
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path

capture_dir = os.getenv("DAY17_LIVE_CAPTURE_DIR")
if capture_dir:
    import uvicorn.config
    from openai.resources.responses.responses import AsyncResponses

    root = Path(capture_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    active = ContextVar("day17_capture", default=None)
    http_count = 0
    provider_count = 0

    def save(name, value):
        try:
            with (root / name).open("x", encoding="utf-8") as handle:
                json.dump(value, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
        except Exception as error:
            print(f"[day17-capture] save failed: {name}: {type(error).__name__}", flush=True)

    def now():
        return datetime.now(timezone.utc).isoformat()

    original_create = AsyncResponses.create

    async def observed_create(self, *args, **kwargs):
        global provider_count
        attempt = active.get()
        if attempt is None:
            return await original_create(self, *args, **kwargs)
        provider_count += 1
        prefix = f"attempt-{attempt}-provider-{provider_count}"
        # This production payload has no credentials; headers are never captured.
        save(prefix + "-request.json", {"at": now(), "payload": kwargs})
        try:
            response = await original_create(self, *args, **kwargs)
        except BaseException as error:
            save(prefix + "-error.json", {"at": now(), "type": type(error).__name__,
                "status_code": getattr(error, "status_code", None),
                "request_id": getattr(error, "request_id", None)})
            raise
        save(prefix + "-response.json", {"at": now(), "response":
            response.model_dump(mode="json", exclude_unset=True)})
        return response

    AsyncResponses.create = observed_create

    class Capture:
        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            global http_count
            if scope["type"] != "http" or scope.get("path") != "/api/v1/mcp-tool-lab/run":
                return await self.app(scope, receive, send)
            http_count += 1
            attempt = http_count
            token = active.set(attempt)
            request_body = bytearray()
            response_body = bytearray()
            status = None
            save(f"attempt-{attempt}-dispatch.json", {"at": now(),
                "method": scope["method"], "path": scope["path"], "client": scope.get("client")})

            async def observed_receive():
                message = await receive()
                if message["type"] == "http.request":
                    request_body.extend(message.get("body", b""))
                    if not message.get("more_body", False):
                        save(f"attempt-{attempt}-android-request.json", json.loads(request_body))
                return message

            async def observed_send(message):
                nonlocal status
                if message["type"] == "http.response.start":
                    status = message["status"]
                elif message["type"] == "http.response.body":
                    response_body.extend(message.get("body", b""))
                    if not message.get("more_body", False):
                        save(f"attempt-{attempt}-android-response.json", {"at": now(),
                            "http_status": status, "body": json.loads(response_body)})
                await send(message)

            try:
                await self.app(scope, observed_receive, observed_send)
            finally:
                active.reset(token)

    original_load = uvicorn.config.Config.load

    def observed_load(self):
        original_load(self)
        self.loaded_app = Capture(self.loaded_app)

    uvicorn.config.Config.load = observed_load
    print("[day17-capture] passive observer armed; no generation initiated", flush=True)
