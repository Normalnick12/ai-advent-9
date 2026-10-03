"""Frozen Day 25 scenarios and saved, keyless reports."""
import argparse
import asyncio
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def parser():
    root = argparse.ArgumentParser(description='Day 25 stateful RAG frozen experiment')
    sub = root.add_subparsers(dest='command', required=True)
    run = sub.add_parser('run')
    run.add_argument('--output-root', type=Path,
                     default=Path(__file__).resolve().parents[1] / '.local/day25/experiments')
    report = sub.add_parser('report')
    report.add_argument('result', type=Path)
    report.add_argument('--video', action='store_true')
    return root


async def execute(args):
    from app.stateful_rag.report import render
    if args.command == 'report':
        text = render(args.result, video=args.video)
        target = args.result / ('video.md' if args.video else 'report.md')
        target.write_text(text, encoding='utf-8')
        print(text)
        print(f'Saved report: {target}')
        return
    from app.document_indexing.corpus import ROOT
    from app.first_rag.core import read_index
    from app.stateful_rag.experiment import run_experiment
    index = read_index(baseline=True)
    from dotenv import load_dotenv
    load_dotenv(ROOT / 'backend/.env', override=False)
    if not os.environ.get('OPENAI_API_KEY'):
        raise ValueError('OPENAI_API_KEY is missing')
    from app.document_indexing.embedding import OpenAIEmbedder
    from app.first_rag.client import ObservedClient
    client, embedder = ObservedClient(), OpenAIEmbedder()
    try:
        folder = await run_experiment(index=index, client=client, embedder=embedder,
            output_root=args.output_root, progress=lambda text: print(text, flush=True))
    finally:
        await client.close()
        embedder.close()
    for video, name in ((False, 'report.md'), (True, 'video.md')):
        (folder / name).write_text(render(folder, video=video), encoding='utf-8')
    print(f'Saved evidence and reports: {folder}')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    try:
        asyncio.run(execute(parser().parse_args()))
    except Exception as exc:
        # No upstream body or credentials in terminal errors; never resume implicitly.
        print(f'ERROR: {type(exc).__name__}; stopped. Inspect saved checkpoints; do not replay.',
              file=sys.stderr)
        sys.exit(1)
