"""Production entrypoint: worker failure stops HTTP and exits nonzero for systemd."""
import asyncio
import logging
import uvicorn

from server import create_app


async def serve():
    fatal = asyncio.Event()
    app = create_app(fatal_callback=fatal.set)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8018,
        workers=1, access_log=False, timeout_graceful_shutdown=20))
    http = asyncio.create_task(server.serve())
    failed = asyncio.create_task(fatal.wait())
    try:
        await asyncio.wait([http, failed], return_when=asyncio.FIRST_COMPLETED)
        if fatal.is_set():
            server.should_exit = True
        await http
        return 1 if fatal.is_set() or not server.started else 0
    finally:
        failed.cancel()
        await asyncio.gather(failed, return_exceptions=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(asyncio.run(serve()))
