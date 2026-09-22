"""Day 17 transport contract; independent of the shared LlmClient."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator


class McpLabRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=12000)
    mode: Literal["forced", "auto"] = "forced"

    @model_validator(mode="after")
    def nonblank(self):
        if not self.prompt.strip():
            raise ValueError("Prompt must not be blank")
        return self


class MavenEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)
    status: Literal["found", "group_not_found", "artifact_not_found", "no_versions"]
    group_id: str
    artifact_id: str
    versions: list[str]
    source_url: str
    checked_at: datetime
    lookup_id: UUID

    @model_validator(mode="after")
    def consistent(self):
        if (self.status == "found") != bool(self.versions):
            raise ValueError("Inconsistent versions/status")
        if self.checked_at.utcoffset() is None or self.checked_at.utcoffset().total_seconds() != 0:
            raise ValueError("Expected UTC checked_at")
        if any(not v or any(c.isspace() for c in v) for v in self.versions):
            raise ValueError("Invalid version")
        return self


class McpCallEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str | None = None
    server_label: str | None = None
    name: str | None = None
    arguments: str | None = None
    status: str | None = None
    output: str | None = None
    error: JsonValue = None
    outcome: str
    parsed_result: MavenEvidence | None = None
    evidence_error: str | None = None


class McpLabOperation(BaseModel):
    model_config = ConfigDict(frozen=True)
    operation_id: str
    submitted_prompt: str
    mode: Literal["forced", "auto"]
    server_label: str = "android_dependencies"
    server_url: str | None = None
    response_id: str | None = None
    provider_status: str | None = None
    final_text: str | None = None
    mcp_items: list[dict[str, JsonValue]] = Field(default_factory=list)
    imported_tools: list[dict[str, JsonValue]] = Field(default_factory=list)
    calls: list[McpCallEvidence] = Field(default_factory=list)
    outcome: str
    invocation: Literal["observed", "not_observed", "unknown", "not_sent"]
    error_message: str | None = None
