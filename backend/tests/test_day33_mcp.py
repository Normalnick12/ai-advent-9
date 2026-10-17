import asyncio
import json
import os
from types import SimpleNamespace

from mcp import Client
from mcp.client.stdio import stdio_client
import pytest

from app.support_assistant import mcp_client as mcp, ticket_mcp_server as server
from app.support_assistant.models import DemoData
from test_day31_mcp import exited


@pytest.mark.asyncio
async def test_real_stdio_discovery_single_ticket_missing_invalid_args_and_cleanup(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'PRIVATE-SENTINEL')
    with mcp.diagnostics() as log:
        async with Client(stdio_client(mcp.parameters(), errlog=log), cache=None) as client:
            tools = (await client.list_tools()).tools
            assert [t.name for t in tools] == ['get_ticket']
            assert tools[0].annotations.read_only_hint is True
            assert tools[0].input_schema['additionalProperties'] is False
            results = []
            for tid in ('T-101', 'T-102', 'T-103', 'T-999'):
                trace = {}
                result = await mcp.discover_and_call(client, tid, trace)
                results.append(result)
                assert trace['discovery'] == trace['call'] == 'completed'
                assert result.ticket_id == tid and result.snapshot_at == '2026-10-16T09:00:00Z'
                for other in {'T-101', 'T-102', 'T-103'} - {tid}:
                    assert other not in result.model_dump_json()
            for args in ({'ticket_id': 'T-101', 'path': 'tickets.json'}, {'ticket_id': '../secret'}, {}):
                assert (await client.call_tool('get_ticket', args)).is_error
            pid = results[0].server_pid
            assert pid != os.getpid() and results[-1].ticket is None
            assert results[0].ticket.message == 'Не могу войти в аккаунт.'
        assert exited(pid)
    assert 'OPENAI_API_KEY' not in mcp.parameters().env


@pytest.mark.asyncio
async def test_real_process_cleanup_on_error_and_cancel():
    for error in (RuntimeError('test'), asyncio.CancelledError()):
        with mcp.diagnostics() as log:
            with pytest.raises((ExceptionGroup, asyncio.CancelledError)):
                async with Client(stdio_client(mcp.parameters(), errlog=log), cache=None) as client:
                    pid = (await mcp.discover_and_call(client, 'T-101', {})).server_pid
                    raise error
        assert exited(pid)


@pytest.mark.asyncio
async def test_discovery_pagination_and_rejects_wrong_ticket():
    tool = (await server.create_server().list_tools())[0]
    data = DemoData.model_validate_json(server.DATA.read_text(encoding='utf8'))
    class Fake:
        cursors = []
        async def list_tools(self, cursor=None):
            self.cursors.append(cursor)
            return SimpleNamespace(tools=[tool] if cursor else [], next_cursor=None if cursor else 'next')
        async def call_tool(self, name, args):
            return SimpleNamespace(is_error=False, structured_content=dict(status='found', ticket_id='T-102',
                ticket=data.tickets[1].model_dump(), snapshot_at=data.snapshot_at,
                call_id='596c174e-4ac3-49fa-bd8c-a7296c5b3646', server_pid=1))
    client = Fake()
    with pytest.raises(mcp.McpFailure, match='invalid_result'):
        await mcp.discover_and_call(client, 'T-101', {})
    assert client.cursors == [None, 'next']


@pytest.mark.asyncio
async def test_timeout_missing_launcher_and_malformed_data(tmp_path):
    for options in (dict(launcher=tmp_path/'missing.py'), dict(timeout=0.001)):
        with pytest.raises(mcp.McpFailure):
            await mcp.get_ticket('T-101', **options)
    path = tmp_path/'invalid.json'
    data = json.loads(server.DATA.read_text(encoding='utf8'))
    data['tickets'].append(data['tickets'][0])
    path.write_text(json.dumps(data), encoding='utf8')
    with pytest.raises(ValueError, match='invalid_ticket_ids'):
        server.create_server(path)
