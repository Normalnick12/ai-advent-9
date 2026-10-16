"""Only this server executes Git. stdout belongs exclusively to MCP."""
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Literal
from uuid import uuid4, UUID

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field, model_validator

TOOL = 'get_current_branch'


class BranchResult(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    status: Literal['branch', 'detached']
    branch: str | None
    call_id: str
    server_pid: int = Field(gt=0)

    @model_validator(mode='after')
    def consistent(self):
        UUID(self.call_id)
        if (self.status == 'branch' and (not self.branch or not self.branch.strip())
                or self.status == 'detached' and self.branch is not None):
            raise ValueError('invalid_branch_state')
        return self


def run_git(root, arguments):
    try:
        # The caller explicitly owns this fixed root; do not inherit unrelated global Git config.
        return subprocess.run(['git', '-c', 'safe.directory=' + str(root), '-C', str(root), *arguments], shell=False,
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              encoding='utf-8', errors='strict', timeout=5,
                              creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    except FileNotFoundError:
        raise ToolError('git_missing') from None
    except subprocess.TimeoutExpired:
        raise ToolError('git_timeout') from None
    except (OSError, UnicodeError):
        raise ToolError('git_failure') from None


def current_branch(root):
    call_id, outcome = str(uuid4()), 'error'
    try:
        root = Path(root).resolve(strict=True)
        top = run_git(root, ['rev-parse', '--show-toplevel'])
        if top.returncode or Path(top.stdout.strip()).resolve() != root:
            raise ToolError('not_repository_root')
        symbolic = run_git(root, ['symbolic-ref', '--quiet', '--short', 'HEAD'])
        if symbolic.returncode == 0 and symbolic.stdout.strip():
            outcome, branch = 'branch', symbolic.stdout.rstrip('\r\n')
        elif symbolic.returncode == 1:
            head = run_git(root, ['rev-parse', '--verify', 'HEAD'])
            if head.returncode:
                raise ToolError('git_failure')
            outcome, branch = 'detached', None
        else:
            raise ToolError('git_failure')
        return BranchResult(status=outcome, branch=branch, call_id=call_id, server_pid=os.getpid())
    except OSError:
        raise ToolError('not_repository_root') from None
    finally:
        print(json.dumps(dict(event='git_branch_call', call_id=call_id,
                              server_pid=os.getpid(), outcome=outcome)), file=sys.stderr, flush=True)


class GitServer(MCPServer):
    async def call_tool(self, name, arguments, context=None):
        if arguments:
            raise ToolError('unexpected_arguments')
        return await super().call_tool(name, arguments, context)

    async def list_tools(self):
        tools = await super().list_tools()
        for tool in tools:
            tool.input_schema['additionalProperties'] = False
        return tools


def create_server(root):
    server = GitServer('Day 31 Git MCP', version='1.0.0')

    @server.tool(annotations=ToolAnnotations(read_only_hint=True, destructive_hint=False,
                                            idempotent_hint=True, open_world_hint=False))
    def get_current_branch() -> BranchResult:
        """Read the current branch or detached HEAD of the server-owned repository. No arguments."""
        return current_branch(root)

    return server
