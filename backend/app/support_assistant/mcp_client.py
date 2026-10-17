"""Bounded real stdio MCP discovery and one get_ticket call per request."""
import asyncio
from pathlib import Path
import sys

from mcp import Client
from mcp.client.stdio import StdioServerParameters, stdio_client

from app.developer_assistant.mcp_client import diagnostics, leaf_errors
from app.document_indexing.corpus import ROOT
from .models import TicketResult

TOOL = 'get_ticket'
LAUNCHER = ROOT / 'backend/scripts/day33_ticket_mcp.py'


class McpFailure(ValueError):
    def __init__(self, reason, trace):
        self.trace = trace
        super().__init__(reason)


def parameters(launcher=LAUNCHER):
    return StdioServerParameters(command=sys.executable, args=[str(Path(launcher).resolve())],
        cwd=str(ROOT), env={'PYTHONUTF8': '1', 'PYTHONDONTWRITEBYTECODE': '1'})


async def discover_and_call(client, ticket_id, trace):
    cursor, seen, tools = None, set(), []
    while True:
        page = await client.list_tools(cursor=cursor)
        tools.extend(page.tools)
        cursor = page.next_cursor
        if cursor is None:
            break
        if cursor in seen:
            raise McpFailure('discovery_cursor_cycle', trace)
        seen.add(cursor)
    selected = [t for t in tools if t.name == TOOL]
    if len(selected) != 1:
        raise McpFailure('tool_missing', trace)
    tool = selected[0]
    schema = tool.input_schema
    properties = schema.get('properties', {})
    if (set(properties) != {'ticket_id'} or schema.get('required') != ['ticket_id']
            or properties['ticket_id'].get('type') != 'string'
            or properties['ticket_id'].get('pattern') != '^T-[0-9]{3}$'
            or schema.get('additionalProperties') is not False
            or not tool.output_schema or not tool.annotations or tool.annotations.read_only_hint is not True):
        raise McpFailure('tool_incompatible', trace)
    trace['discovery'] = 'completed'
    trace['call'] = 'started'
    raw = await client.call_tool(TOOL, {'ticket_id': ticket_id})
    if raw.is_error:
        raise McpFailure('tool_error', trace)
    try:
        result = TicketResult.model_validate(raw.structured_content)
        if result.ticket_id != ticket_id:
            raise ValueError('ticket_id_mismatch')
    except (ValueError, TypeError):
        raise McpFailure('invalid_result', trace) from None
    trace.update(call='completed', call_id=result.call_id, server_pid=result.server_pid,
                 outcome=result.status)
    return result


async def get_ticket(ticket_id, *, launcher=LAUNCHER, timeout=15):
    trace = dict(tool=TOOL, requested_ticket_id=ticket_id, discovery='not_completed', call='not_started')
    try:
        with diagnostics() as log:
            async with asyncio.timeout(timeout):
                async with Client(stdio_client(parameters(launcher), errlog=log), cache=None) as client:
                    trace.update(protocol=client.protocol_version, server=client.server_info.name)
                    result = await discover_and_call(client, ticket_id, trace)
        return result, trace
    except Exception as error:
        leaves = leaf_errors(error)
        reason = next((str(e) for e in leaves if isinstance(e, McpFailure)),
                      'timeout' if any(isinstance(e, TimeoutError) for e in leaves) else 'transport_error')
        trace['error'] = reason
        raise McpFailure(reason, trace) from None
