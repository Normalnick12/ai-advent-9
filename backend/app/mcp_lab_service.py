"""One Responses call returns final text and all native MCP evidence together."""
import asyncio
import copy
import ipaddress
import json
import os
import re
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from openai import AsyncOpenAI, OpenAIError
from pydantic import ValidationError

from app.mcp_lab_models import McpCallEvidence, McpLabOperation, McpLabRequest, MavenEvidence

TOOL = "get_google_maven_versions"
SERVER = "android_dependencies"
DEADLINE_SECONDS = 75
INSTRUCTIONS = (
    "Используй данные Google Maven из результата инструмента для ответа о версиях. "
    "Сохраняй порядок источника. Не называй версии latest/stable, совместимыми или безопасными. "
    "Если lookup отрицательный или инструмент недоступен, сообщи это без догадок. "
    "Не повторяй вызов для исправления результата. Отвечай кратко по-русски."
)


def valid_endpoint(value: str | None) -> bool:
    if not value or any(c.isspace() for c in value):
        return False
    try:
        url = urlsplit(value)
        host = url.hostname or ""
        if (url.scheme != "https" or url.path != "/mcp" or url.query or url.fragment
                or url.username or url.password or url.port not in (None, 443)
                or not re.fullmatch(r"[A-Za-z0-9.-]+", host) or "." not in host
                or host.endswith((".localhost", ".local"))):
            return False
        try:
            return ipaddress.ip_address(host).is_global
        except ValueError:
            return True
    except ValueError:
        return False


def request_payload(request: McpLabRequest, url: str) -> dict:
    choice = {"type": "mcp", "server_label": SERVER, "name": TOOL} if request.mode == "forced" else "auto"
    return {"model": "gpt-5.6", "input": request.prompt, "instructions": INSTRUCTIONS,
            "reasoning": {"effort": "none"}, "max_output_tokens": 1200, "store": False,
            "tools": [{"type": "mcp", "server_label": SERVER, "server_url": url,
                       "allowed_tools": [TOOL], "require_approval": "never"}], "tool_choice": choice}


def parse_call(item: dict) -> McpCallEvidence:
    fields = {key: item.get(key) for key in ("id", "server_label", "name", "arguments", "status", "output", "error")}
    if item.get("error"):
        # Provider errors are opaque; do not pretend to know their upstream origin.
        return McpCallEvidence(**fields, outcome="unclassified_error")
    try:
        if item.get("name") != TOOL or item.get("server_label") != SERVER:
            raise ValueError("unexpected_tool")
        raw = json.loads(item.get("output") or "")
        if isinstance(raw, dict) and (raw.get("isError") is True or raw.get("is_error") is True):
            return McpCallEvidence(**fields, outcome="tool_error")
        # Explicitly support MCP CallToolResult plus its structured/text representations.
        if isinstance(raw, dict) and ("structuredContent" in raw or "structured_content" in raw):
            raw = raw.get("structuredContent") or raw.get("structured_content")
        elif isinstance(raw, dict) and "content" in raw:
            content = raw["content"]
            if not isinstance(content, list) or len(content) != 1 or content[0].get("type") != "text":
                raise ValueError("unsupported_content")
            raw = json.loads(content[0]["text"])
        evidence = MavenEvidence.model_validate(raw)
        arguments = json.loads(item.get("arguments") or "")
        if (not isinstance(arguments, dict) or evidence.group_id != arguments.get("group_id")
                or evidence.artifact_id != arguments.get("artifact_id")):
            raise ValueError("coordinates_mismatch")
        if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_-]*(?:\.[A-Za-z0-9_][A-Za-z0-9_-]*)*", evidence.group_id):
            raise ValueError("invalid_coordinates")
        if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", evidence.artifact_id):
            raise ValueError("invalid_coordinates")
        expected_url = f"https://dl.google.com/dl/android/maven2/{evidence.group_id.replace('.', '/')}/group-index.xml"
        if evidence.source_url != expected_url:
            raise ValueError("source_mismatch")
        if item.get("status") not in (None, "completed"):
            raise ValueError("call_not_completed")
        return McpCallEvidence(**fields, outcome=evidence.status, parsed_result=evidence)
    except (ValueError, TypeError, KeyError, AttributeError, ValidationError):
        return McpCallEvidence(**fields, outcome="invalid_tool_result",
                               evidence_error="Результат не соответствует проверяемому контракту tool.")


def normalize_response(raw: dict, request: McpLabRequest, url: str, operation_id: str) -> McpLabOperation:
    items = copy.deepcopy([i for i in raw.get("output", []) if i.get("type", "").startswith("mcp_")])
    lists = [i for i in items if i["type"] == "mcp_list_tools"]
    calls = [parse_call(i) for i in items if i["type"] == "mcp_call"]
    imported = [copy.deepcopy(t) for i in lists for t in i.get("tools", [])]
    parts = [p for i in raw.get("output", []) if i.get("type") == "message" for p in i.get("content", [])]
    text = "\n".join(p["text"] for p in parts if p.get("type") == "output_text" and isinstance(p.get("text"), str)) or None
    refused = any(p.get("type") == "refusal" for p in parts)
    status = raw.get("status")
    discovery_error = any(i.get("error") for i in lists) or any(i["type"] == "mcp_approval_request" for i in items)
    if discovery_error:
        outcome = "mcp_error"
    elif status != "completed":
        outcome = status if status in ("incomplete", "failed") else "provider_error"
    elif refused:
        outcome = "refused"
    elif not calls:
        outcome = "not_called"
    else:
        errors = [c.outcome for c in calls if c.outcome in ("tool_error", "invalid_tool_result", "unclassified_error")]
        outcome = errors[0] if errors else "completed" if text and text.strip() else "model_response_missing"
    return McpLabOperation(operation_id=operation_id, submitted_prompt=request.prompt, mode=request.mode,
        server_url=url, response_id=raw.get("id"), provider_status=status, final_text=text,
        mcp_items=items, imported_tools=imported, calls=calls, outcome=outcome,
        invocation="observed" if calls else "not_observed")


class McpLabService:
    def __init__(self, client=None, server_url: str | None = None):
        self._client = client
        self._server_url = server_url

    async def close(self):
        if self._client is not None:
            await self._client.close()

    async def run(self, request: McpLabRequest) -> McpLabOperation:
        operation_id = str(uuid4())
        url = self._server_url if self._server_url is not None else os.getenv("DAY17_MCP_SERVER_URL")
        base = dict(operation_id=operation_id, submitted_prompt=request.prompt, mode=request.mode)
        if not valid_endpoint(url):
            return McpLabOperation(**base, outcome="configuration_error", invocation="not_sent",
                                   error_message="Настройте DAY17_MCP_SERVER_URL: публичный HTTPS endpoint /mcp.")
        try:
            if self._client is None:
                self._client = AsyncOpenAI(timeout=httpx.Timeout(75, connect=5), max_retries=0)
            response = await asyncio.wait_for(self._client.responses.create(**request_payload(request, url)),
                                              timeout=DEADLINE_SECONDS)
        except (TimeoutError, OpenAIError):
            return McpLabOperation(**base, server_url=url, outcome="provider_error", invocation="unknown",
                error_message="Responses API не вернул результат. Факт remote-вызова неизвестен; повтор не выполнялся.")
        raw = response if isinstance(response, dict) else response.model_dump(mode="json", exclude_unset=True)
        return normalize_response(raw, request, url, operation_id)
