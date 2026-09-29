"""Local Day 22 CLI; report never creates provider clients."""
import argparse
import asyncio
import os
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.document_indexing.corpus import ROOT
from app.document_indexing.storage import DATABASE
from app.first_rag.core import QUESTIONS, check_question, question_set, read_index
from app.first_rag.experiment import run_experiment
from app.first_rag.report import render


def parser():
    root = argparse.ArgumentParser(description="Day 22: observable first RAG query")
    sub = root.add_subparsers(dest="command", required=True)
    for name in ("search", "ask", "eval"):
        p = sub.add_parser(name)
        if name != "eval":
            p.add_argument("question")
        if name == "ask":
            p.add_argument("--mode", choices=("direct", "rag"), required=True)
        p.add_argument("--run", help="Explicit saved Day 21 UUID; required for retrieval")
        p.add_argument("--db", type=Path, default=DATABASE)
        p.add_argument("--top-k", type=int, choices=[5], default=5)
        p.add_argument("--output-root", type=Path, default=ROOT / "backend/.local/day22")
        p.add_argument("--full", action="store_true")
    p = sub.add_parser("report")
    p.add_argument("result", type=Path)
    p.add_argument("--question", dest="question_id")
    p.add_argument("--full", action="store_true")
    p.add_argument("--retrieval-only", action="store_true")
    return root


async def execute(args):
    if args.command == "report":
        print(render(args.result, question_id=args.question_id, full=args.full, retrieval_only=args.retrieval_only))
        return
    command = args.mode if args.command == "ask" else args.command
    index = None
    if command != "direct":
        if not args.run:
            raise ValueError("--run is required for retrieval")
        index = read_index(args.db, args.run, baseline=command == "eval")
    frozen, fingerprint = None, None
    if command == "eval":
        frozen, fingerprint = question_set(QUESTIONS, source_paths=index.sources)
        questions = frozen["questions"]
    else:
        check_question(args.question)
        questions = [dict(id="Q01", question=args.question, difficulty="ad_hoc", expected_facts=[],
                          acceptable_sources=[], negative_control=False)]
    from dotenv import load_dotenv
    load_dotenv(ROOT / "backend/.env", override=False)
    if not os.environ.get("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY is missing from backend environment")
    from app.document_indexing.embedding import OpenAIEmbedder
    from app.first_rag.client import ObservedClient
    embedder = OpenAIEmbedder() if command != "direct" else None
    client = ObservedClient() if command != "search" else None
    try:
        folder = await run_experiment(command, questions, output_root=args.output_root, index=index,
                                      embedder=embedder, client=client, frozen=frozen, question_hash=fingerprint,
                                      progress=lambda line: print(line, flush=True))
    finally:
        if embedder:
            embedder.close()
        if client:
            await client.close()
    print(render(folder, question_id=None if command == "eval" else "Q01", full=args.full,
                 retrieval_only=command == "search"))
    print(f"Saved evidence: {folder}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        asyncio.run(execute(parser().parse_args()))
    except (ValueError, OSError, KeyError, TypeError, sqlite3.Error) as exc:
        # Do not echo exception bodies, environment or provider credentials.
        print(f"ERROR: {type(exc).__name__}; operation stopped. Inspect saved checkpoints; do not replay.", file=sys.stderr)
        sys.exit(1)
