from fastapi import APIRouter, Request

from app.mcp_lab_models import McpLabOperation, McpLabRequest

router = APIRouter(prefix="/api/v1/mcp-tool-lab", tags=["Day 17"])


@router.post("/run", response_model=McpLabOperation)
async def run(body: McpLabRequest, request: Request) -> McpLabOperation:
    return await request.app.state.mcp_tool_lab.run(body)
