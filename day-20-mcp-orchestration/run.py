"""One explicit LIVE local POST. Use verify.py to review saved evidence offline."""
import argparse
from pathlib import Path
import sys

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.mcp_orchestration_service import PROMPT
from verify import save_report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Explicitly dispatch the single live attempt")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout", type=int, default=930)
    args = parser.parse_args()
    if not args.live:
        parser.error("No request sent. --live is required; use verify.py for offline review.")
    print(PROMPT, flush=True)
    print("LIVE: одна отправка; без повторов. Ожидаем исследование и публикации.", flush=True)
    try:
        with httpx.Client(timeout=args.timeout, follow_redirects=False) as client:
            response = client.post(args.base_url + "/api/v1/mcp-orchestration/run", json={"prompt": PROMPT})
            response.raise_for_status()
            result = response.json()
    except httpx.HTTPError:
        print("Результат неизвестен. Не повторяйте отправку; проверьте backend/.local/day20.")
        return 1
    print("Outcome:", result["outcome"])
    if result.get("evidence_path"):
        print("Evidence:", result["evidence_path"])
        target, verdict = save_report(result["evidence_path"])
        print((target / "report.md").read_text(encoding="utf-8"))
        print("Report:", target / "report.md")
        return 0 if verdict["observed_flow"]["status"] == "PASS" and verdict["final_facts"]["status"] == "PASS" else 1
    return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
