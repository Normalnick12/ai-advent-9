"""Single native auto request. No tool execution, argument injection or repair."""
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from uuid import uuid4

import httpx
from openai import AsyncOpenAI, OpenAIError

from .mcp_composition_models import CompositionOperation, CompositionRequest
from .mcp_lab_service import valid_endpoint

SERVER = "dependency_composition"
TOOLS = ["get_google_maven_versions", "summarize_dependency_versions", "save_dependency_report"]
INSTRUCTIONS = (
    "Выполни цепочку один раз: get_google_maven_versions, summarize_dependency_versions, "
    "save_dependency_report. Каждый инструмент вызови отдельно и ровно один раз в этом порядке. "
    "Во второй передай весь объект LookupResult из первого под ключом lookup, включая полный "
    "массив versions, без изменений. В третий передай весь DependencyReport из второго под ключом "
    "report без изменений. Не вычисляй count, tail или hash самостоятельно, не сокращай список. "
    "Не повторяй вызовы и не исправляй ошибки. При execution error остановись и сообщи ошибку. "
    "При успехе ответь одним JSON object без Markdown и дополнительных полей, с ровно полями "
    "group_id, artifact_id, status, version_count, last_three, file_id. Копируй факты report и receipt. "
    "last_three означает последние элементы в порядке источника, не semver latest/stable."
)


def redact(value, secrets):
    if isinstance(value, str):
        for secret in secrets:
            if secret:
                value = value.replace(secret, "[REDACTED]")
        return value
    if isinstance(value, list):
        return [redact(v, secrets) for v in value]
    if isinstance(value, dict):
        return {redact(k, secrets): "[REDACTED]" if k.lower() in
                ("authorization", "api_key", "token", "headers") else redact(v, secrets)
                for k, v in value.items()}
    return value


def payload(prompt, url, token, budget):
    return dict(model="gpt-5.6", input=prompt, instructions=INSTRUCTIONS,
        reasoning={"effort": "none"}, store=False, max_output_tokens=budget, tool_choice="auto",
        tools=[dict(type="mcp", server_label=SERVER, server_url=url, authorization=token,
                    allowed_tools=TOOLS.copy(), require_approval="never")])


def projection(raw):
    items = raw.get("output", [])
    calls = [i for i in items if i.get("type") == "mcp_call"]
    texts = [p["text"] for i in items if i.get("type") == "message" for p in i.get("content", [])
             if p.get("type") == "output_text" and isinstance(p.get("text"), str)]
    final = "\n".join(texts) if texts else None
    return calls, final


def write_new(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as file:
        json.dump(value, file, ensure_ascii=True, indent=2, allow_nan=False)
        file.write("\n")
        file.flush()
        os.fsync(file.fileno())


class CompositionService:
    def __init__(self, client=None, *, url=None, token=None, budget=None, deadline=None, evidence_dir=None):
        self.client = client
        self.url, self.token, self.budget, self.deadline = url, token, budget, deadline
        self.evidence_dir = Path(evidence_dir or Path(__file__).resolve().parents[1] / ".local/day19/evidence")

    async def close(self):
        if self.client is not None:
            await self.client.close()

    async def run(self, request: CompositionRequest):
        operation_id = str(uuid4())
        base = dict(operation_id=operation_id, invocation="not_sent")
        url = self.url if self.url is not None else os.getenv("DAY19_MCP_SERVER_URL", "")
        token = self.token if self.token is not None else os.getenv("DAY19_MCP_TOKEN", "")
        secrets = [token, os.getenv("OPENAI_API_KEY", "")]
        try:
            budget = self.budget if self.budget is not None else int(os.getenv("DAY19_MAX_OUTPUT_TOKENS", ""))
            deadline = self.deadline if self.deadline is not None else int(os.getenv("DAY19_DEADLINE_SECONDS", ""))
            if (not valid_endpoint(url) or len(token) < 32 or any(c.isspace() for c in token)
                    or type(budget) is not int or not 1 <= budget <= 128000
                    or type(deadline) is not int or not 1 <= deadline <= 1800):
                raise ValueError()
        except (ValueError, TypeError):
            return CompositionOperation(**base, outcome="configuration_error")
        config = payload(redact(request.prompt, secrets), url, token, budget)
        path = self.evidence_dir / operation_id
        try:
            path.mkdir(parents=True, exist_ok=False)
            # Reservation and marker must both persist before dispatch. A surviving
            # attempt without response always means UNKNOWN, never permission to retry.
            write_new(path / "attempt.json", dict(operation_id=operation_id,
                started_at=datetime.now(timezone.utc).isoformat(), invocation="unknown",
                request_configuration=redact(config, secrets), deadline_seconds=deadline, max_retries=0))
            # Reserve output before sending too, so obvious permission failures are not_sent.
            response_file = (path / "response.json").open("x", encoding="utf-8", newline="\n")
        except OSError:
            return CompositionOperation(**base, outcome="evidence_storage_error")
        result = CompositionOperation(operation_id=operation_id, invocation="unknown", outcome="provider_error",
                                      evidence_path=str(path))
        try:
            if self.client is None:
                try:
                    self.client = AsyncOpenAI(timeout=httpx.Timeout(deadline, connect=10), max_retries=0)
                except OpenAIError:
                    result.invocation, result.outcome = "not_sent", "configuration_error"
                    return result
            try:
                response = await asyncio.wait_for(self.client.responses.create(**config), timeout=deadline)
            except (TimeoutError, OpenAIError) as exc:
                result.error_category = type(exc).__name__  # no secret-bearing exception text
                write_new(path / "error.json", redact(dict(result.model_dump(),
                    provider_error_body=getattr(exc, "body", None), provider_request_id=getattr(exc, "request_id", None),
                    http_status=getattr(exc, "status_code", None)), secrets))
                result.evidence_saved = True
                return result
            raw = response if isinstance(response, dict) else response.model_dump(mode="json", exclude_unset=True)
            raw = redact(raw, secrets)
            # Store every item as received; projection never replaces the native response.
            json.dump(raw, response_file, ensure_ascii=True, indent=2, allow_nan=False)
            response_file.write("\n")
            response_file.flush()
            os.fsync(response_file.fileno())
            calls, final = projection(raw)
            result.invocation = "observed" if calls else "not_observed"
            result.outcome = "response_received"
            result.provider_status, result.response_id = raw.get("status"), raw.get("id")
            result.final_text = final
            write_new(path / "operation.json", dict(operation_id=operation_id, raw_response="response.json",
                request_configuration=redact(config, secrets), invocation=result.invocation,
                calls=calls, final_text=final, provider_status=result.provider_status,
                payload_bytes=[{k: len(i[k].encode("utf-8")) for k in ("arguments", "output")
                                if isinstance(i.get(k), str)} for i in calls]))
            result.evidence_saved = True
            return result
        except OSError:
            result.error_category = "evidence_storage_error"
            result.evidence_saved = False
            return result
        finally:
            response_file.close()
