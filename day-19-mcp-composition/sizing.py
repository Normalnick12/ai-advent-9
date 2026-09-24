"""Conservative full-payload budget, without tokenizer/model/network calls."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from verify import canonical, expected, receipt_for, validate
from launch import PROMPT

ROOT = Path(__file__).resolve().parents[1]
# Read the exact constant without importing the backend or its OpenAI dependencies.
import ast
source = ast.parse((ROOT / "backend/app/mcp_composition_service.py").read_text(encoding="utf-8"))
INSTRUCTIONS = ast.literal_eval(next(node.value for node in source.body if isinstance(node, ast.Assign)
    and any(isinstance(target, ast.Name) and target.id == "INSTRUCTIONS" for target in node.targets)))

MODEL_SOURCE = "https://developers.openai.com/api/docs/models/gpt-5.6-sol"


def measure(lookup, schemas):
    validate(lookup, "lookup")
    report = expected(lookup)
    receipt = receipt_for(report)
    final = dict({k: report[k] for k in ("group_id", "artifact_id", "status", "version_count", "last_three")},
                 file_id=receipt["file_id"])
    objects = dict(lookup=lookup, lookup_arguments={"group_id": "androidx.core", "artifact_id": "core-ktx"},
        summary_arguments={"lookup": lookup}, report=report, save_arguments={"report": report}, receipt=receipt,
        schemas=schemas, prompt={"input": PROMPT, "instructions": INSTRUCTIONS}, final=final)
    sizes = {name: dict(canonical_utf8_bytes=len(canonical(obj)),
        pretty_ascii_bytes=len(json.dumps(obj, ensure_ascii=True, indent=2).encode("utf-8"))) for name, obj in objects.items()}
    # A byte-level tokenizer can encode any UTF-8 byte; one token per byte is a
    # conservative bound for these strings, NOT a provider usage/billing count.
    generated = sum(sizes[n]["pretty_ascii_bytes"] for n in ("lookup_arguments", "summary_arguments", "save_arguments", "final"))
    required = 2 * generated + 4096  # formatting/model envelope/growth uncertainty
    budget = max(16384, 1 << (required - 1).bit_length())
    context = 2 * sum(s["pretty_ascii_bytes"] for s in sizes.values()) + budget + 8192
    return dict(status="PASS" if budget <= 128000 and context <= 1050000 else "BLOCKED",
        measured_at=datetime.now(timezone.utc).isoformat(), model="gpt-5.6", resolved_alias="gpt-5.6-sol",
        model_limits_source=MODEL_SOURCE, model_limits_checked="2026-09-24", context_window=1050000,
        model_max_output_tokens=128000, method="UTF-8 byte upper bound; pretty ASCII envelopes; 2x growth plus framing reserve",
        uncertainty="Conservative estimate, not provider billing; future lookup may grow. No truncation or retries.",
        measurements=sizes, full_version_count=len(lookup["versions"]), generated_token_upper_bound=generated,
        required_with_margin=required, max_output_tokens=budget, output_margin=budget-generated,
        estimated_context_upper_bound=context, context_margin=1050000-context, deadline_seconds=600,
        request_body_limit_bytes=32*1024*1024)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("preflight")
    parser.add_argument("readiness")
    parser.add_argument("output")
    args = parser.parse_args()
    preflight = json.loads(Path(args.preflight).read_text(encoding="utf-8"))
    readiness = json.loads(Path(args.readiness).read_text(encoding="utf-8"))
    result = measure(preflight["lookup"], readiness["tools"])
    with Path(args.output).open("x", encoding="utf-8") as file:
        json.dump(result, file, indent=2)
        file.write("\n")
    print(json.dumps(result, indent=2))
    if result["status"] != "PASS":
        raise SystemExit("Full payload does not fit; stop before live.")
