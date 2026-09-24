"""Strict wire contracts. Values are validated, never repaired."""
from datetime import datetime
import re
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, AfterValidator, model_validator


def matching(pattern):
    def check(value):
        if re.fullmatch(pattern, value) is None:
            raise ValueError("invalid_format")
        return value
    return AfterValidator(check)


GroupId = Annotated[str, Field(strict=True, min_length=1, max_length=256,
    pattern=r"^[A-Za-z0-9_][A-Za-z0-9_-]*(\.[A-Za-z0-9_][A-Za-z0-9_-]*)*$"),
    matching(r"[A-Za-z0-9_][A-Za-z0-9_-]*(\.[A-Za-z0-9_][A-Za-z0-9_-]*)*")]
ArtifactId = Annotated[str, Field(strict=True, min_length=1, max_length=256,
    pattern=r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$"), matching(r"[A-Za-z0-9_][A-Za-z0-9_.-]*")]
Hash = Annotated[str, matching(r"[0-9a-f]{64}"), Field(pattern=r"^[0-9a-f]{64}$")]
Version = Annotated[str, Field(min_length=1), matching(r"\S+")]
Status = Literal["found", "group_not_found", "artifact_not_found", "no_versions"]


def source_url(group_id):
    return f"https://dl.google.com/dl/android/maven2/{group_id.replace('.', '/')}/group-index.xml"


def uuid_string(value):
    if str(UUID(value)) != value:
        raise ValueError("noncanonical_uuid")
    return value


def utc_string(value):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z", value):
        raise ValueError("noncanonical_time")
    datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
    return value


Identifier = Annotated[str, AfterValidator(uuid_string)]
Timestamp = Annotated[str, AfterValidator(utc_string)]


class StrictObject(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", hide_input_in_errors=True)


class Coordinates(StrictObject):
    group_id: GroupId
    artifact_id: ArtifactId


class Identity(Coordinates):
    status: Status
    source_url: str
    checked_at: Timestamp
    lookup_id: Identifier

    @model_validator(mode="after")
    def correct_url(self):
        if self.source_url != source_url(self.group_id):
            raise ValueError("source_mismatch")
        return self


class LookupResult(Identity):
    versions: list[Version]

    @model_validator(mode="after")
    def list_status(self):
        if (self.status == "found") != bool(self.versions):
            raise ValueError("status_versions_mismatch")
        return self


class DependencyReport(Identity):
    schema_version: Annotated[int, Field(ge=1, le=1)]
    version_count: Annotated[int, Field(ge=0)]
    last_three: Annotated[list[Version], Field(max_length=3)]
    input_sha256: Hash

    @model_validator(mode="after")
    def counts(self):
        if ((self.status == "found") != (self.version_count > 0)
                or len(self.last_three) != min(self.version_count, 3)):
            raise ValueError("report_counts_mismatch")
        return self


class SaveReceipt(StrictObject):
    status: Literal["saved"]
    lookup_id: Identifier
    file_id: Hash
    sha256: Hash
    bytes: Annotated[int, Field(gt=0)]

    @model_validator(mode="after")
    def same_hash(self):
        if self.file_id != self.sha256:
            raise ValueError("receipt_hash_mismatch")
        return self


class SummaryInput(StrictObject):
    lookup: LookupResult


class SaveInput(StrictObject):
    report: DependencyReport
