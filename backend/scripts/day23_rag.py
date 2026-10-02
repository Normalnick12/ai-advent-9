"""Day 23 CLI. Report reads only saved evidence, before loading provider clients."""
import argparse
import asyncio
import os
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.document_indexing.corpus import ROOT
from app.document_indexing.storage import DATABASE
from app.first_rag.core import read_index
from app.rewrite_filter_rag.core import load_baseline
from app.rewrite_filter_rag.experiment import compare, retrieve
from app.rewrite_filter_rag.report import render
from app.rewrite_filter_rag.video_report import render_video


def parser():
    root = argparse.ArgumentParser(description='Day 23: frozen query rewrite + cosine filtering')
    sub = root.add_subparsers(dest='command', required=True)
    p = sub.add_parser('retrieve')
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--db', type=Path, default=DATABASE)
    p.add_argument('--output-root', type=Path, default=ROOT/'backend/.local/day23')
    p = sub.add_parser('compare')
    p.add_argument('result', type=Path)
    p = sub.add_parser('report')
    p.add_argument('result', type=Path)
    p.add_argument('--question', dest='question_id')
    p.add_argument('--full', action='store_true')
    p.add_argument('--video', action='store_true', help='Compact offline presentation of saved evidence/review')
    return root


async def execute(args):
    if args.command=='report':
        if args.video:
            print(render_video(args.result,question_id=args.question_id))
        else:
            print(render(args.result,question_id=args.question_id,full=args.full))
        return
    if args.command=='retrieve':
        index=read_index(args.db,baseline=True)
        baseline=load_baseline(args.baseline,index)
    from dotenv import load_dotenv
    load_dotenv(ROOT/'backend/.env',override=False)
    if not os.environ.get('OPENAI_API_KEY'):
        raise ValueError('OPENAI_API_KEY is missing from backend environment')
    from app.first_rag.client import ObservedClient
    client=ObservedClient()
    embedder=None
    try:
        if args.command=='retrieve':
            from app.document_indexing.embedding import OpenAIEmbedder
            embedder=OpenAIEmbedder()
            folder=await retrieve(baseline,index,output_root=args.output_root,client=client,
                                  embedder=embedder,progress=lambda s:print(s,flush=True))
        else:
            folder=await compare(args.result,client=client,progress=lambda s:print(s,flush=True))
    finally:
        if embedder:
            embedder.close()
        await client.close()
    print(render(folder))
    print(f'Saved evidence: {folder}')


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    try:
        asyncio.run(execute(parser().parse_args()))
    except (ValueError,OSError,KeyError,TypeError,sqlite3.Error) as exc:
        print(f'ERROR: {type(exc).__name__}; stopped. Inspect saved checkpoints; do not replay.',file=sys.stderr)
        sys.exit(1)
