"""Offline sizing from retained Day 19 data, not a new dependency lookup."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.mcp_orchestration_service import Settings


def measure():
    source = ROOT / "day-19-mcp-composition/evidence/preflight-20260924.json"
    lookup = json.loads(source.read_text(encoding="utf-8"))["lookup"]
    one = len(json.dumps({"lookup": lookup}, ensure_ascii=True, indent=2).encode("utf-8"))
    transfers = 2 * one
    # Byte bound for retained data only. Research size/number of calls are model-selected.
    allowance = transfers * 2 + 8192 + 4096
    settings = Settings("", "")
    return dict(kind="offline_configuration", measured_at=datetime.now(timezone.utc).isoformat(),
        model="gpt-5.6", tool_choice="auto", reasoning_effort="none", store=False,
        max_retries=0, max_output_tokens=settings.budget, deadline_seconds=settings.deadline,
        historical_source=str(source.relative_to(ROOT)), source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        historical_version_count=len(lookup["versions"]), one_full_summary_arguments_bytes=one,
        two_full_transfers_bytes=transfers, research_arguments_allowance=8192,
        final_and_framing_allowance=4096, estimate_with_2x_transfer_growth=allowance,
        sizing_status="PASS" if allowance <= settings.budget else "BLOCKED",
        rationale="UTF-8 byte upper bound for two historical full transfers, 2x growth plus research/final allowance; 900s finite deadline.",
        limitations="Not actual Room/WorkManager sizes, not tokenizer usage, latency prediction or guaranteed fit. Future research/calls can exceed allowances; incomplete is retained without retry.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output")
    result = measure()
    with Path(parser.parse_args().output).open("x", encoding="utf-8") as file:
        json.dump(result, file, indent=2)
        file.write("\n")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["sizing_status"] == "PASS" else 1)
