import asyncio
from contextlib import asynccontextmanager
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, call

import pytest
from mcp.types import ListToolsResult, Tool

import main


def test_format_preserves_description_and_complete_schema():
    schema = {
        "type": "object",
        "properties": {"query": {"$ref": "#/$defs/query"}},
        "required": ["query"],
        "$defs": {"query": {"type": "string", "description": "Запрос"}},
        "additionalProperties": False,
    }
    tool = Tool(name="example_search", description="Поиск\nдокументации", input_schema=schema)
    output = main.format_catalog([tool])
    assert "Количество tools: 1" in output
    assert "Name: example_search" in output
    assert "Description: Поиск\nдокументации" in output
    rendered_schema = output.split("Input schema:\n", 1)[1]
    assert json.loads(rendered_schema) == schema
    assert '\n  "type"' in rendered_schema
    assert "Запрос" in rendered_schema


@pytest.fixture
def connection(monkeypatch):
    """Only replace the Client boundary; no transport or MCP server emulation."""
    client = SimpleNamespace(
        protocol_version="test-protocol",
        server_info=SimpleNamespace(name="Test server", version="test-version"),
        list_tools=AsyncMock(),
        closed=False,
        exit_error=None,
    )

    @asynccontextmanager
    async def connect(endpoint):
        assert endpoint == main.ENDPOINT
        try:
            yield client
        finally:
            client.closed = True
            if client.exit_error:
                raise client.exit_error

    monkeypatch.setattr(main, "Client", connect)
    return client


def test_pages_are_aggregated_and_success_follows_cleanup(connection, capsys, monkeypatch):
    first = Tool(name="alpha", input_schema={"type": "object"})
    second = Tool(name="beta", description="Second", input_schema={})
    connection.list_tools.side_effect = [
        ListToolsResult(tools=[first], next_cursor="page-2"),
        ListToolsResult(tools=[second]),
    ]
    original_print = print

    def observe_print(*args, **kwargs):
        if args and "Discovery завершено" in str(args[0]):
            assert connection.closed
        original_print(*args, **kwargs)

    monkeypatch.setattr(main, "print", observe_print, raising=False)
    assert main.main() == 0
    output = capsys.readouterr()
    assert not output.err
    assert main.ENDPOINT in output.out
    assert "MCP connection: успешно" in output.out
    assert "Protocol version: test-protocol" in output.out
    assert "Server name: Test server" in output.out
    assert "Server version: test-version" in output.out
    assert "Количество tools: 2" in output.out
    assert output.out.index("Name: alpha") < output.out.index("Name: beta")
    assert f"Description: {main.UNAVAILABLE}" in output.out
    assert "Discovery завершено" in output.out
    assert connection.list_tools.await_args_list == [call(cursor=None), call(cursor="page-2")]


def test_empty_catalog_and_missing_identity(connection, capsys):
    connection.server_info = None
    connection.list_tools.return_value = ListToolsResult(tools=[])
    assert main.main() == 0
    output = capsys.readouterr()
    assert f"Server name: {main.UNAVAILABLE}" in output.out
    assert f"Server version: {main.UNAVAILABLE}" in output.out
    assert "Количество tools: 0" in output.out
    connection.list_tools.assert_awaited_once_with(cursor=None)
    assert connection.closed


def test_second_page_failure_is_not_partial_success(connection, capsys):
    connection.list_tools.side_effect = [
        ListToolsResult(tools=[Tool(name="partial", input_schema={})], next_cursor="next"),
        ExceptionGroup("transport", [RuntimeError("listing failed")]),
    ]
    assert main.main() == 1
    output = capsys.readouterr()
    assert "listing failed" in output.err
    assert "Количество tools:" not in output.out
    assert "Discovery завершено" not in output.out
    assert connection.closed


def test_negotiation_failure_has_no_connection_success(monkeypatch, capsys):
    @asynccontextmanager
    async def unavailable(endpoint):
        raise RuntimeError("negotiation failed")
        yield  # Defines an async context manager without establishing a connection.

    monkeypatch.setattr(main, "Client", unavailable)
    assert main.main() == 1
    output = capsys.readouterr()
    assert "negotiation failed" in output.err
    assert "MCP connection: успешно" not in output.out
    assert "Discovery завершено" not in output.out


def test_timeout_closes_context(connection, monkeypatch, capsys):
    async def pending(**kwargs):
        await asyncio.Future()

    connection.list_tools.side_effect = pending
    monkeypatch.setattr(main, "TIMEOUT_SECONDS", 0)
    assert main.main() == 1
    output = capsys.readouterr()
    assert "истекло время ожидания MCP" in output.err
    assert "Discovery завершено" not in output.out
    assert connection.closed


def test_cleanup_failure_prevents_success(connection, capsys):
    connection.list_tools.return_value = ListToolsResult(tools=[])
    connection.exit_error = RuntimeError("cleanup failed")
    assert main.main() == 1
    output = capsys.readouterr()
    assert "cleanup failed" in output.err
    assert "Discovery завершено" not in output.out
