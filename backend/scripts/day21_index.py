"""Run from repository root with backend/.venv/Scripts/python.exe."""
import argparse
import os
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.document_indexing.corpus import MANIFEST, ROOT, inventory, load_corpus
from app.document_indexing.report import comparison, display_chunk, examples, prepare
from app.document_indexing.storage import DATABASE, load


def main():
    parser = argparse.ArgumentParser(description="Day 21 document indexing")
    parser.add_argument("command", choices=["corpus", "preview", "build", "compare", "inspect"])
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--example", help="Representative location ID; defaults to all four")
    parser.add_argument("--strategy", choices=["both"], default="both")
    parser.add_argument("--db", type=Path, default=DATABASE)
    parser.add_argument("--run", help="Saved run UUID (required for compare/inspect)")
    selectors = parser.add_mutually_exclusive_group()
    selectors.add_argument("--source", help="Inspect all chunks from a repository-relative source")
    selectors.add_argument("--chunk", help="Inspect one full chunk ID")
    parser.add_argument("--full-vector", action="store_true")
    args = parser.parse_args()
    if args.command in {"compare", "inspect"}:
        if not args.run:
            parser.error("--run is required for compare/inspect")
        data = load(args.run, args.db)
        print(f"Saved run: {args.run}")
        print(comparison(data, persisted=True))
        if args.source or args.chunk:
            selected = [c for chunks in data["chunks"].values() for c in chunks
                        if (args.source and c["source"] == args.source) or (args.chunk and c["chunk_id"] == args.chunk)]
            if not selected:
                raise ValueError("No matching source/chunk")
            for chunk in selected:
                print(display_chunk(chunk, full_vector=args.full_vector))
        else:
            print(examples(data, args.example, full_vector=args.full_vector))
        return
    snapshot = load_corpus(ROOT, args.manifest)
    if args.command == "corpus":
        print(inventory(snapshot))
    elif args.command == "preview":
        data = prepare(snapshot)
        print(comparison(data))
        print(examples(data, args.example))
    else:
        from dotenv import load_dotenv
        from app.document_indexing.embedding import OpenAIEmbedder
        from app.document_indexing.pipeline import build
        load_dotenv(ROOT / "backend/.env", override=False)
        if not os.environ.get("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY is missing in backend environment")
        embedder = OpenAIEmbedder()
        try:
            print(f"Embedding {len(snapshot.sources)} source files via OpenAI; snapshot {snapshot.corpus_hash}", flush=True)
            data = build(snapshot, embedder, args.db, progress=lambda message: print(message, flush=True))
        finally:
            embedder.close()
        print(f"Saved run: {data['run_id']}\nSQLite: {args.db}")
        print(comparison(data, persisted=True))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        main()
    except (ValueError, OSError, KeyError, sqlite3.Error) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
