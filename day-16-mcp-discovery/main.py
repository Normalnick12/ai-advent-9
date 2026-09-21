"""Day 16: discover DeepWiki's tool catalog without invoking any tools."""

import asyncio
import json
import sys

from mcp import Client
from mcp.types import Tool

ENDPOINT = "https://mcp.deepwiki.com/mcp"
TIMEOUT_SECONDS = 60
UNAVAILABLE = "не предоставлено"


async def collect_tools(client: Client) -> list[Tool]:
    tools = []
    cursor = None
    while True:
        page = await client.list_tools(cursor=cursor)
        tools.extend(page.tools)
        if page.next_cursor is None:
            return tools
        cursor = page.next_cursor


def format_catalog(tools: list[Tool]) -> str:
    lines = [f"Количество tools: {len(tools)}"]
    for tool in tools:
        lines.extend([
            "",
            f"Name: {tool.name}",
            f"Description: {tool.description or UNAVAILABLE}",
            "Input schema:",
            json.dumps(tool.input_schema, ensure_ascii=False, indent=2),
        ])
    return "\n".join(lines)


async def discover() -> None:
    print(f"Endpoint: {ENDPOINT}", flush=True)
    async with asyncio.timeout(TIMEOUT_SECONDS):
        async with Client(ENDPOINT) as client:
            print("MCP connection: успешно; protocol negotiation завершено.")
            print(f"Protocol version: {client.protocol_version}")
            info = client.server_info
            print(f"Server name: {getattr(info, 'name', None) or UNAVAILABLE}")
            print(f"Server version: {getattr(info, 'version', None) or UNAVAILABLE}", flush=True)
            tools = await collect_tools(client)
            print(format_catalog(tools), flush=True)


def error_message(error: Exception) -> str:
    # Async transports can wrap the useful network error in an ExceptionGroup.
    if isinstance(error, ExceptionGroup):
        return "; ".join(error_message(item) for item in error.exceptions)
    if isinstance(error, TimeoutError):
        return "истекло время ожидания MCP"
    return f"{type(error).__name__}: {error}"


def main() -> int:
    try:
        asyncio.run(discover())
        print("Discovery завершено. Соединение закрыто.", flush=True)
    except KeyboardInterrupt:
        print("Discovery прервано пользователем.", file=sys.stderr)
        return 130
    except Exception as error:
        print(f"Ошибка discovery: {error_message(error)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
