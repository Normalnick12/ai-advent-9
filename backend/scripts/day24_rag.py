"""Day 24 frozen eval; offline reports require only the saved result folder."""
import argparse
import asyncio
import os
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from app.document_indexing.corpus import ROOT
from app.document_indexing.storage import DATABASE
from app.first_rag.core import read_index
from app.grounded_rag.core import replay
from app.grounded_rag.experiment import run_eval
from app.grounded_rag.report import render


def parser():
    root=argparse.ArgumentParser(description='Day 24: frozen retrieval + grounded answer contract')
    sub=root.add_subparsers(dest='command',required=True)
    p=sub.add_parser('eval')
    p.add_argument('--baseline',type=Path,required=True)
    p.add_argument('--db',type=Path,default=DATABASE)
    p.add_argument('--output-root',type=Path,default=ROOT/'backend/.local/day24')
    p=sub.add_parser('report')
    p.add_argument('result',type=Path)
    p.add_argument('--question',dest='question_id')
    display=p.add_mutually_exclusive_group()
    display.add_argument('--full',action='store_true')
    display.add_argument('--video',action='store_true')
    return root


async def execute(args):
    if args.command=='report':
        print(render(args.result,question_id=args.question_id,full=args.full,video=args.video))
        return
    index=read_index(args.db,baseline=True)
    baseline,retrievals=replay(args.baseline,index)
    from dotenv import load_dotenv
    load_dotenv(ROOT/'backend/.env',override=False)
    if not os.environ.get('OPENAI_API_KEY'):
        raise ValueError('OPENAI_API_KEY is missing from backend environment')
    from app.first_rag.client import ObservedClient
    client=ObservedClient()
    try:
        folder=await run_eval(baseline,retrievals,output_root=args.output_root,client=client,
                              progress=lambda s:print(s,flush=True))
    finally:
        await client.close()
    print(render(folder,video=True))
    print(f'Saved evidence: {folder}')


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    try:
        asyncio.run(execute(parser().parse_args()))
    except (ValueError,OSError,KeyError,TypeError,sqlite3.Error) as exc:
        print(f'ERROR: {type(exc).__name__}; stopped. Inspect checkpoints; do not replay.',file=sys.stderr)
        sys.exit(1)
