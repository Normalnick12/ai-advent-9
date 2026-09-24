"""Pure deterministic processing; C_v1 is a project format, not RFC JCS."""
import hashlib
import json

from .contracts import DependencyReport, LookupResult


def canonical(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False,
                       separators=(",", ":")) + "\n").encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def summarize(lookup: LookupResult) -> DependencyReport:
    raw = lookup.model_dump()
    return DependencyReport(**{k: v for k, v in raw.items() if k != "versions"},
        schema_version=1, version_count=len(lookup.versions), last_three=lookup.versions[-3:],
        input_sha256=digest(raw))
