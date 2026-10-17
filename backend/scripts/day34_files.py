"""Day 34 local CLI; imports are pinned to this checkout."""
import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
import sys

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
import app
if not Path(app.__file__).resolve().is_relative_to(BACKEND):
    raise SystemExit("checkout_import_mismatch")

from app.project_files_assistant import ROOT, FileAgentError, guard, safe_terminal
from app.project_files_assistant.workspace import prepare
from app.project_files_assistant.changes import apply_candidate, reject, review
from app.project_files_assistant.verify import verify


def parser():
    p = argparse.ArgumentParser(description="Day 34: bounded project files assistant")
    commands = p.add_subparsers(dest="command", required=True)
    cmd = commands.add_parser("prepare")
    cmd.add_argument("scenario", choices=["A", "B"])
    for name in ("run", "review", "apply", "reject", "verify"):
        cmd = commands.add_parser(name)
        cmd.add_argument("run_dir", type=Path)
        if name in {"review", "apply", "reject"}:
            cmd.add_argument("candidate_id")
        if name == "run":
            cmd.add_argument("--env-file", type=Path)
    return p


def checked_run(path):
    path = guard(path)
    runs = guard(ROOT / "backend/.local/day34/runs")
    if not path.is_relative_to(runs) or path.parent != runs:
        raise FileAgentError("run_outside_local_directory")
    return path


def main(argv=None):
    logging.disable(logging.CRITICAL)
    args = parser().parse_args(argv)
    if args.command == "prepare":
        result = dict(run_dir=str(prepare(args.scenario)))
    else:
        run = checked_run(args.run_dir)
        if args.command == "run":
            if not os.environ.get("OPENAI_API_KEY"):
                from dotenv import dotenv_values
                values = dotenv_values(args.env_file or ROOT/"backend/.env")
                key = values.get("OPENAI_API_KEY")
                if not key:
                    raise FileAgentError("OPENAI_API_KEY_missing")
                os.environ["OPENAI_API_KEY"] = key
            from app.project_files_assistant.runner import run as execute
            def observe(item):
                print(safe_terminal(json.dumps(item, ensure_ascii=False)), file=sys.stderr, flush=True)
            result = asyncio.run(execute(run, observe=observe))
        elif args.command == "review":
            print(safe_terminal(review(run, args.candidate_id)))
            return 0
        elif args.command == "apply":
            print(safe_terminal(review(run, args.candidate_id)))
            if not sys.stdin.isatty():
                raise FileAgentError("interactive_confirmation_required")
            try:
                confirmation = input("Введите показанный candidate ID для записи (Enter = отмена): ").strip()
            except EOFError:
                confirmation = ""
            result = apply_candidate(run, args.candidate_id, confirmation)
        elif args.command == "reject":
            result = reject(run, args.candidate_id)
        else:
            result = verify(run)
    print(safe_terminal(json.dumps(result, ensure_ascii=False, indent=2)))
    return 1 if result.get("status") in {"error", "not_proven", "partial_review"} else 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Операция отменена.", file=sys.stderr)
        raise SystemExit(130)
    except (FileAgentError, OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        code = str(exc) if type(exc) is FileAgentError else type(exc).__name__
        print("ERROR: "+code, file=sys.stderr)
        raise SystemExit(1)
