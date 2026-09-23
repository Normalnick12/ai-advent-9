"""One provider attempt, native Bearer authorization, immutable redacted evidence."""
import asyncio
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from uuid import uuid4

import httpx
from openai import AsyncOpenAI, OpenAIError

from app.dependency_watch_models import WatchCall, WatchOperation, WatchReceipt, WatchRequest, WatchSummary
from app.mcp_lab_service import valid_endpoint

SERVER = "dependency_watch"
TOOLS = {"create": "create_dependency_watch", "summary": "get_dependency_watch_summary"}
INSTRUCTIONS = (
    "Выполни выбранную операцию один раз. Не повторяй tool call, не исправляй и не регенерируй результат. "
    "Для create обязательны max_runs и точные координаты; каждый принятый вызов создаёт новый watch. "
    "Для summary используй только выбранный watch_id. Факты сводки заданы deterministic aggregate; "
    "null означает отсутствие данных, а не ноль. Не обещай новые версии, стабильность или безопасность. "
    "Кратко объясни результат по-русски; при ошибке или неизвестном исходе сообщи об этом."
)


def redact(value, token):
    if isinstance(value, str):
        return value.replace(token, "[REDACTED]") if token else value
    if isinstance(value, list):
        return [redact(v, token) for v in value]
    if isinstance(value, dict):
        return {redact(k, token): "[REDACTED]" if k.lower() in ("authorization", "token", "api_key", "headers")
                else redact(v, token) for k, v in value.items()}
    return value


def payload(request, url, token):
    return {"model": "gpt-5.6", "input": request.prompt,
        "instructions": INSTRUCTIONS + (f" Выбранный watch_id: {request.watch_id}." if request.watch_id else ""),
        "reasoning": {"effort": "none"}, "max_output_tokens": 1800, "store": False,
        "tools": [{"type": "mcp", "server_label": SERVER, "server_url": url, "authorization": token,
                   "allowed_tools": [TOOLS[request.operation]], "require_approval": "never"}],
        "tool_choice": {"type": "mcp", "server_label": SERVER, "name": TOOLS[request.operation]}}


def parse_call(item, request):
    fields = {key: item.get(key) for key in ("id", "server_label", "name", "arguments", "status", "output", "error")}
    if item.get("error"):
        return WatchCall(**fields, outcome="unclassified_error")
    try:
        if item.get("server_label") != SERVER or item.get("name") != TOOLS[request.operation]:
            raise ValueError("unexpected tool")
        raw = json.loads(item.get("output") or "")
        if isinstance(raw, dict) and (raw.get("isError") or raw.get("is_error")):
            return WatchCall(**fields, outcome="tool_error")
        if isinstance(raw, dict) and ("structuredContent" in raw or "structured_content" in raw):
            raw = raw.get("structuredContent") or raw.get("structured_content")
        elif isinstance(raw, dict) and "content" in raw:
            content = raw["content"]
            if len(content) != 1 or content[0].get("type") != "text":
                raise ValueError("unsupported wrapper")
            raw = json.loads(content[0]["text"])
        args = json.loads(item.get("arguments") or "")
        if item.get("status") not in (None, "completed"):
            raise ValueError("not completed")
        if request.operation == "create":
            receipt = WatchReceipt.model_validate(raw)
            for key in ("group_id", "artifact_id", "max_runs", "interval_seconds"):
                expected = args.get(key, 21600 if key == "interval_seconds" else None)
                if getattr(receipt, key) != expected or (key in ("max_runs", "interval_seconds") and type(expected) is not int):
                    raise ValueError("create arguments mismatch")
            if receipt.runs_total != 0 or receipt.status != "active":
                raise ValueError("invalid create receipt")
            return WatchCall(**fields, outcome="completed", receipt=receipt)
        summary = WatchSummary.model_validate(raw)
        if str(summary.watch_id) != args.get("watch_id") or summary.watch_id != request.watch_id:
            raise ValueError("summary identity mismatch")
        return WatchCall(**fields, outcome="completed", summary=summary)
    except (ValueError, TypeError, KeyError, AttributeError):
        return WatchCall(**fields, outcome="invalid_tool_result")


def normalize(raw, request, url, operation_id):
    items = copy.deepcopy([i for i in raw.get("output", []) if i.get("type", "").startswith("mcp_")])
    calls = [parse_call(item, request) for item in items if item["type"] == "mcp_call"]
    parts = [p for item in raw.get("output", []) if item.get("type") == "message" for p in item.get("content", [])]
    text = "\n".join(p["text"] for p in parts if p.get("type") == "output_text" and isinstance(p.get("text"), str)) or None
    status = raw.get("status")
    if any(i.get("error") for i in items if i["type"] == "mcp_list_tools") or any(i["type"] == "mcp_approval_request" for i in items):
        outcome = "mcp_error"
    elif status != "completed":
        outcome = status if status in ("failed", "incomplete") else "provider_error"
    elif any(p.get("type") == "refusal" for p in parts):
        outcome = "refused"
    elif not calls:
        outcome = "not_called"
    else:
        outcome = next((c.outcome for c in calls if c.outcome != "completed"),
                       "completed" if text and text.strip() else "model_response_missing")
    return WatchOperation(operation_id=operation_id, submitted_prompt=request.prompt, operation=request.operation,
        selected_watch_id=request.watch_id, server_url=url, response_id=raw.get("id"), provider_status=status,
        final_text=text, mcp_items=items, calls=calls, outcome=outcome,
        invocation="observed" if calls else "not_observed")


class DependencyWatchService:
    def __init__(self, client=None, *, server_url=None, token=None, evidence_dir=None):
        self.client, self.url, self.token = client, server_url, token
        self.evidence_dir = Path(evidence_dir or Path(__file__).resolve().parents[1] / ".local/day18/evidence")

    async def close(self):
        if self.client is not None:
            await self.client.close()

    async def run(self, request: WatchRequest):
        token = self.token if self.token is not None else os.getenv("DAY18_MCP_TOKEN", "")
        url = self.url if self.url is not None else os.getenv("DAY18_MCP_SERVER_URL", "")
        request = request.model_copy(update={"prompt": redact(request.prompt, token)})
        operation_id = str(uuid4())
        base = dict(operation_id=operation_id, submitted_prompt=request.prompt, operation=request.operation,
                    selected_watch_id=request.watch_id)
        # Reserve evidence BEFORE a potentially non-idempotent create. Never send if unavailable.
        try:
            self.evidence_dir.mkdir(parents=True, exist_ok=True)
            path = self.evidence_dir / (operation_id + ".json")
            file = path.open("x", encoding="utf-8")
        except OSError:
            return WatchOperation(**base, outcome="evidence_storage_error", invocation="not_sent",
                                  error_message="Evidence недоступен; запрос не отправлен.")
        started = datetime.now(timezone.utc).isoformat()
        config = None
        try:
            if not valid_endpoint(url) or len(token) < 32 or any(c.isspace() for c in token):
                operation = WatchOperation(**base, outcome="configuration_error", invocation="not_sent",
                    error_message="Настройте backend DAY18_MCP_SERVER_URL и DAY18_MCP_TOKEN.")
            else:
                config = payload(request, url, token)
                # Write-ahead attempt record survives cancellation/process loss. It never
                # claims a remote create did not happen when no terminal response exists.
                try:
                    with path.with_suffix(".attempt").open("x", encoding="utf-8") as intent:
                        json.dump({"operation_id": operation_id, "started_at": started,
                            "invocation": "unknown", "request_configuration": redact(config, token)}, intent,
                            ensure_ascii=False, indent=2)
                        intent.flush()
                        os.fsync(intent.fileno())
                except OSError:
                    return WatchOperation(**base, outcome="evidence_storage_error", invocation="not_sent",
                        error_message="Evidence недоступен; запрос не отправлен.")
                try:
                    if self.client is None:
                        self.client = AsyncOpenAI(timeout=httpx.Timeout(75, connect=5), max_retries=0)
                    response = await asyncio.wait_for(self.client.responses.create(**config), timeout=75)
                except (TimeoutError, OpenAIError):
                    operation = WatchOperation(**base, server_url=url, outcome="provider_error", invocation="unknown",
                        error_message="Responses не вернул результат. Факт create неизвестен; повтор не выполнялся.")
                else:
                    raw = response if isinstance(response, dict) else response.model_dump(mode="json", exclude_unset=True)
                    operation = normalize(redact(raw, token), request, url, operation_id)
            operation = operation.model_copy(update={"evidence_saved": True})
            record = {"started_at": started, "completed_at": datetime.now(timezone.utc).isoformat(),
                      "request_configuration": redact(config, token), "operation": operation.model_dump(mode="json")}
            json.dump(record, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())
            return operation
        except OSError:
            return operation.model_copy(update={"evidence_saved": False,
                "error_message": "Не удалось сохранить evidence; автоматический повтор не выполнялся."})
        finally:
            file.close()
