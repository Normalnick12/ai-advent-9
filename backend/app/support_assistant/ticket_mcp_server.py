"""Only this process reads the ticket JSON. stdout is reserved for MCP."""
import json
import os
from pathlib import Path
import sys
from uuid import uuid4

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from app.document_indexing.corpus import ROOT
from .models import DemoData, TicketId, TicketResult

TOOL = 'get_ticket'
DATA = ROOT / 'day-33-support-assistant/tickets.json'


class TicketServer(MCPServer):
    async def call_tool(self, name, arguments, context=None):
        if not isinstance(arguments, dict) or set(arguments) != {'ticket_id'}:
            raise ToolError('expected_only_ticket_id')
        return await super().call_tool(name, arguments, context)

    async def list_tools(self):
        tools = await super().list_tools()
        for tool in tools:
            tool.input_schema['additionalProperties'] = False
        return tools


def create_server(data_path=DATA):
    data = DemoData.model_validate_json(Path(data_path).read_text(encoding='utf-8-sig'))
    tickets = {t.ticket_id: t for t in data.tickets}
    server = TicketServer('DemoStore ticket MCP', version='1.0.0')

    @server.tool(annotations=ToolAnnotations(read_only_hint=True, destructive_hint=False,
                                            idempotent_hint=True, open_world_hint=False))
    def get_ticket(ticket_id: TicketId) -> TicketResult:
        """Read one fictional support ticket at the fixed UTC snapshot; never list other tickets."""
        ticket = tickets.get(ticket_id)
        result = TicketResult(status='found' if ticket else 'not_found', ticket_id=ticket_id,
            snapshot_at=data.snapshot_at, ticket=ticket, call_id=str(uuid4()), server_pid=os.getpid())
        print(json.dumps(dict(event='ticket_call', ticket_id=ticket_id, call_id=result.call_id,
                              server_pid=result.server_pid, outcome=result.status)), file=sys.stderr, flush=True)
        return result

    return server
