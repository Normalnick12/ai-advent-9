"""One local POST. A used directory cannot dispatch again, even after a timeout."""
import argparse
import json
import os
from pathlib import Path
import httpx

PROMPT = "Получи версии androidx.core:core-ktx из Google Maven, вычисли количество и три последних элемента в порядке источника и сохрани JSON-отчёт на сервере."


def launch(attempt_dir, *, base_url="http://127.0.0.1:8000", deadline=600, transport=None):
    path = Path(attempt_dir)
    path.mkdir(parents=True, exist_ok=False)
    with (path / "dispatch.json").open("x", encoding="utf-8") as file:
        json.dump({"prompt": PROMPT, "endpoint": base_url + "/api/v1/mcp-composition/run",
                   "outcome": "unknown_if_no_result", "automatic_retries": 0}, file)
        file.flush()
        os.fsync(file.fileno())
    try:
        with httpx.Client(transport=transport, timeout=deadline, follow_redirects=False) as client:
            response = client.post(base_url + "/api/v1/mcp-composition/run", json={"prompt": PROMPT})
        (path / "backend-response.bin").write_bytes(response.content)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError:
        (path / "unknown.txt").write_text("Outcome unknown. Do not retry this attempt.\n", encoding="utf-8")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("attempt_dir")
    parser.add_argument("--deadline", type=int, required=True)
    args = parser.parse_args()
    result = launch(args.attempt_dir, deadline=args.deadline)
    print("Evidence:", result.get("evidence_path"))
    print("Raw final:", result.get("final_text"))
    print("Outcome:", result.get("outcome"), result.get("invocation"))
