import asyncio
import ctypes
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

from mcp import Client
from mcp.client.stdio import stdio_client
from mcp.server.mcpserver.exceptions import ToolError
import pytest

from app.developer_assistant import git_mcp_server as server, mcp_client


def git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True, text=True)


def exited(pid):
    if os.name == 'nt':
        kernel = ctypes.windll.kernel32
        kernel.OpenProcess.restype = ctypes.c_void_p
        handle = kernel.OpenProcess(0x100000, False, pid)
        if not handle:
            return True
        try:
            return kernel.WaitForSingleObject(ctypes.c_void_p(handle), 0) == 0
        finally:
            kernel.CloseHandle(ctypes.c_void_p(handle))
    try:
        os.kill(pid, 0)
        return False
    except ProcessLookupError:
        return True


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, 'init', '--initial-branch=day31-test')
    return tmp_path


@pytest.mark.asyncio
async def test_real_stdio_discovery_branch_switch_unborn_detached_and_cleanup(repo):
    with mcp_client.diagnostics() as log:
        async with Client(stdio_client(mcp_client.parameters(repo), errlog=log), cache=None) as client:
            tools = (await client.list_tools()).tools
            assert [t.name for t in tools] == ['get_current_branch']
            assert tools[0].annotations.read_only_hint is True
            assert tools[0].input_schema['additionalProperties'] is False and tools[0].output_schema
            unborn = await mcp_client.discover_and_call(client)
            assert unborn['status'] == 'branch' and unborn['branch'] == 'day31-test'
            assert unborn['server_pid'] != os.getpid()
            invalid = await client.call_tool(server.TOOL, {'repo': str(repo.parent)})
            assert invalid.is_error
            git(repo, '-c', 'user.name=Day31 Test', '-c', 'user.email=day31@example.invalid',
                '-c', 'commit.gpgsign=false', 'commit', '--allow-empty', '-m', 'test fixture')
            branch = await mcp_client.discover_and_call(client)
            assert branch['branch'] == 'day31-test'
            git(repo, 'switch', '-c', 'another-branch')
            switched = await mcp_client.discover_and_call(client)
            assert switched['branch'] == 'another-branch'
            git(repo, 'checkout', '--detach')
            detached = await mcp_client.discover_and_call(client)
            assert detached['status'] == 'detached' and detached['branch'] is None
            assert len({r['call_id'] for r in [unborn, branch, switched, detached]}) == 4
        for result in [unborn, branch, switched, detached]:
            assert mcp_client.server_event(log, result) == 'matched'
        assert exited(unborn['server_pid'])


@pytest.mark.asyncio
async def test_client_optional_stderr_and_safe_environment(repo, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'SENTINEL-PRIVATE-KEY')
    monkeypatch.setattr(mcp_client, 'server_event', lambda *args: 'unavailable')
    branch, trace = await mcp_client.get_branch(root=repo)
    assert branch['branch'] == 'day31-test'
    assert trace['call'] == 'completed' and trace['server_event'] == 'unavailable'
    assert exited(branch['server_pid'])
    params = mcp_client.parameters(repo)
    assert 'OPENAI_API_KEY' not in params.env
    assert 'SENTINEL' not in json.dumps(trace)


@pytest.mark.asyncio
async def test_missing_server_and_invalid_repository(tmp_path):
    with pytest.raises(mcp_client.McpFailure):
        await mcp_client.get_branch(launcher=tmp_path / 'absent.py', timeout=3)
    with pytest.raises(mcp_client.McpFailure, match='tool_error'):
        await mcp_client.get_branch(root=tmp_path)


@pytest.mark.asyncio
async def test_cancel_and_error_close_real_process(repo):
    pid = None
    with mcp_client.diagnostics() as log:
        with pytest.raises(asyncio.CancelledError):
            async with Client(stdio_client(mcp_client.parameters(repo), errlog=log), cache=None) as client:
                pid = (await mcp_client.discover_and_call(client))['server_pid']
                raise asyncio.CancelledError()
    assert exited(pid)
    with mcp_client.diagnostics() as log:
        with pytest.raises(ExceptionGroup):
            async with Client(stdio_client(mcp_client.parameters(repo), errlog=log), cache=None) as client:
                pid = (await mcp_client.discover_and_call(client))['server_pid']
                raise RuntimeError('test failure')
    assert exited(pid)


@pytest.mark.parametrize('mode', ['missing', 'tool_error', 'malformed', 'disconnect'])
@pytest.mark.asyncio
async def test_protocol_failures(mode):
    tool = SimpleNamespace(name=server.TOOL, input_schema={'additionalProperties': False},
                           output_schema={'type': 'object'}, annotations=SimpleNamespace(read_only_hint=True))
    class Fake:
        async def list_tools(self, cursor=None):
            return SimpleNamespace(tools=[] if mode == 'missing' else [tool], next_cursor=None)
        async def call_tool(self, *args):
            if mode == 'disconnect':
                raise ConnectionError()
            return SimpleNamespace(is_error=mode == 'tool_error', structured_content={'branch': 'invented'})
    with pytest.raises((mcp_client.McpFailure, ConnectionError)):
        await mcp_client.discover_and_call(Fake())


@pytest.mark.asyncio
async def test_discovery_pagination():
    tool = (await server.create_server('.').list_tools())[0]
    class Fake:
        def __init__(self): self.cursors = []
        async def list_tools(self, cursor=None):
            self.cursors.append(cursor)
            return SimpleNamespace(tools=[tool] if cursor else [], next_cursor=None if cursor else 'page2')
        async def call_tool(self, name, args):
            assert name == server.TOOL and args == {}
            return SimpleNamespace(is_error=False, structured_content=dict(status='branch', branch='test',
                call_id='596c174e-4ac3-49fa-bd8c-a7296c5b3646', server_pid=1))
    fake = Fake()
    assert (await mcp_client.discover_and_call(fake))['branch'] == 'test'
    assert fake.cursors == [None, 'page2']


@pytest.mark.parametrize('error,category', [(FileNotFoundError(), 'git_missing'),
    (subprocess.TimeoutExpired('git', 5), 'git_timeout'), (OSError('private'), 'git_failure')])
def test_safe_git_errors(monkeypatch, error, category):
    monkeypatch.setattr(server.subprocess, 'run', Mock(side_effect=error))
    with pytest.raises(ToolError, match=category):
        server.run_git('.', ['symbolic-ref'])


def test_failed_git_is_not_detached(repo, monkeypatch):
    results = [SimpleNamespace(returncode=0, stdout=str(repo)), SimpleNamespace(returncode=128, stdout='')]
    monkeypatch.setattr(server, 'run_git', Mock(side_effect=results))
    with pytest.raises(ToolError, match='git_failure'):
        server.current_branch(repo)


@pytest.mark.asyncio
async def test_timeout(repo, monkeypatch):
    async def slow(_):
        await asyncio.sleep(10)
    monkeypatch.setattr(mcp_client, 'discover_and_call', slow)
    with pytest.raises(mcp_client.McpFailure, match='timeout'):
        await mcp_client.get_branch(root=repo, timeout=1)
