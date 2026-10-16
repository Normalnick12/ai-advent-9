"""A real stdio MCP client. Server stderr is optional diagnostic evidence."""
import asyncio
import json
import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters, stdio_client

from app.document_indexing.corpus import ROOT
from .git_mcp_server import BranchResult, TOOL

LAUNCHER = ROOT / 'backend/scripts/day31_git_mcp.py'


class McpFailure(ValueError):
    pass


def leaf_errors(error):
    if isinstance(error, BaseExceptionGroup):
        return [leaf for nested in error.exceptions for leaf in leaf_errors(nested)]
    return [error]


def parameters(root=ROOT, launcher=LAUNCHER):
    return StdioServerParameters(command=sys.executable,
        args=[str(Path(launcher).resolve()), '--repo', str(Path(root).resolve())],
        cwd=str(ROOT), env={'PYTHONUTF8': '1', 'PYTHONDONTWRITEBYTECODE': '1',
                           'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull,
                           'GIT_TERMINAL_PROMPT': '0'})


@contextmanager
def diagnostics():
    try:
        log = tempfile.TemporaryFile(mode='w+', encoding='utf-8', errors='replace')
    except OSError:
        log = open(os.devnull, 'w+', encoding='utf-8')
    with log:
        yield log


async def discover_and_call(client):
    cursor, seen, tools = None, set(), []
    while True:
        page = await client.list_tools(cursor=cursor)
        tools.extend(page.tools)
        cursor = page.next_cursor
        if cursor is None:
            break
        if cursor in seen:
            raise McpFailure('mcp_discovery_failed')
        seen.add(cursor)
    matching = [t for t in tools if t.name == TOOL]
    if (len(matching) != 1 or not matching[0].output_schema
            or matching[0].input_schema.get('properties', {})
            or matching[0].input_schema.get('additionalProperties') is not False
            or not matching[0].annotations or matching[0].annotations.read_only_hint is not True):
        raise McpFailure('mcp_tool_missing_or_incompatible')
    result = await client.call_tool(TOOL, {})
    if result.is_error:
        raise McpFailure('mcp_tool_error')
    try:
        branch = BranchResult.model_validate(result.structured_content).model_dump()
    except ValueError:
        raise McpFailure('mcp_invalid_result') from None
    return branch


def server_event(log, branch):
    # Best effort only: a valid protocol result never depends on stderr.
    try:
        log.seek(0)
        for line in log.read(65536).splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if (isinstance(event, dict) and event.get('event') == 'git_branch_call'
                    and event.get('call_id') == branch['call_id']
                    and event.get('server_pid') == branch['server_pid']
                    and event.get('outcome') == branch['status']):
                return 'matched'
    except (OSError, ValueError):
        pass
    return 'unavailable'


async def get_branch(*, root=ROOT, launcher=LAUNCHER, timeout=15):
    try:
        with diagnostics() as log:
            async with asyncio.timeout(timeout):
                async with Client(stdio_client(parameters(root, launcher), errlog=log), cache=None) as client:
                    branch = await discover_and_call(client)
                    trace = dict(protocol=client.protocol_version, server=client.server_info.name,
                                 tool=TOOL, discovery='completed', call='completed',
                                 call_id=branch['call_id'], server_pid=branch['server_pid'])
            trace['server_event'] = server_event(log, branch)
            return branch, trace
    except McpFailure:
        raise
    except TimeoutError:
        raise McpFailure('mcp_timeout') from None
    except Exception as error:
        leaves = leaf_errors(error)
        for leaf in leaves:
            if isinstance(leaf, McpFailure):
                raise McpFailure(str(leaf)) from None
        if any(isinstance(leaf, TimeoutError) for leaf in leaves):
            raise McpFailure('mcp_timeout') from None
        raise McpFailure('mcp_startup_or_transport_error') from None
