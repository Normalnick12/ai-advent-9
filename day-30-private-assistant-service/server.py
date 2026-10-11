"""Explicit optional launcher. No model calls or network setup at import/startup."""
import argparse
import logging
import sys

sys.dont_write_bytecode = True


def main():
    parser = argparse.ArgumentParser(description="Optional private local assistant HTTP service")
    parser.add_argument("--config", required=True, help="Local JSON configuration outside Git")
    parser.add_argument("--port", type=int, default=8030)
    args = parser.parse_args()
    try:
        from laa_service.config import load_config
        from laa_service.app import create_app
        import uvicorn
        if not 1 <= args.port <= 65535:
            raise ValueError
        config = load_config(args.config)
        for name in ("httpx", "httpcore"):
            # Absorb descendant records too; logger.disabled is not inherited.
            logger = logging.getLogger(name)
            logger.handlers = [logging.NullHandler()]
            logger.propagate = False
        logging.getLogger("uvicorn.access").disabled = True
        logging.basicConfig(level=logging.INFO, format="%(message)s")
        uvicorn.run(create_app(config), host="127.0.0.1", port=args.port, workers=1,
                    # Keep this policy: default dictConfig re-enables loggers.
                    log_config=None,
                    access_log=False, proxy_headers=False, server_header=False,
                    limit_concurrency=32, timeout_graceful_shutdown=5, ws="none")
    except Exception:
        print("Service could not start. Check local configuration and HTTP dependencies.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
