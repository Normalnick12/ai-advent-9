"""Day 31 developer help. Run with the existing backend Python environment."""
import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def parser():
    p = argparse.ArgumentParser(description='Day 31: /help по документации проекта + локальный Git MCP')
    commands = p.add_subparsers(dest='command', required=True)
    commands.add_parser('index', help='Явно построить или проверить актуальность индекса')
    help_command = commands.add_parser('/help', help='Ответить на вопрос о проекте')
    help_command.add_argument('question', nargs='?')
    help_command.add_argument('--trace', action='store_true', help='Безопасная диагностика в stderr')
    help_command.add_argument('--trace-format', choices=('jsonl', 'text'), default='jsonl',
                              help='Формат --trace: jsonl (по умолчанию) или краткий text')
    return p


def format_trace(record, trace_format='jsonl'):
    if trace_format == 'jsonl':
        return json.dumps(record, ensure_ascii=False, allow_nan=False)
    from app.developer_assistant.service import safe

    def value(item):
        return safe('n/a' if item is None else item).replace('\n', '\\n').replace('\t', '\\t')

    event = record.get('event')
    if event == 'mcp':
        return (f"MCP: discovery={value(record.get('discovery'))}; "
                f"tool={value(record.get('tool'))}; call={value(record.get('call'))}; "
                f"server_event={value(record.get('server_event'))}")
    if event == 'retrieval':
        hits = record.get('hits', [])
        lines = [f'RAG: фрагментов={len(hits)}; первые {min(3, len(hits))}:']
        for hit in hits[:3]:
            lines.append(f"  {value(hit.get('source'))}:{value(hit.get('start_line'))}-"
                         f"{value(hit.get('end_line'))}  score={hit['score']:.3f}")
        return '\n'.join(lines)
    if event == 'generation':
        model = record.get('resolved_model') or record.get('requested_model')
        line = f"LLM: model={value(model)}; status={value(record.get('status'))}"
        usage = record.get('usage') or {}
        counts = [f'{key}={value(usage[key])}' for key in ('input_tokens', 'output_tokens', 'total_tokens')
                  if usage.get(key) is not None]
        return line + ('; ' + ', '.join(counts) if counts else '')
    if event == 'validation':
        return f"Validation: {value(record.get('status'))}"
    return 'Trace: неизвестное событие'


def credentials():
    from app.document_indexing.corpus import ROOT
    from dotenv import load_dotenv
    load_dotenv(ROOT / 'backend/.env', override=False)
    if not os.getenv('OPENAI_API_KEY'):
        raise ValueError('OPENAI_API_KEY_missing_in_backend')


def embedder():
    credentials()
    from app.document_indexing.embedding import OpenAIEmbedder
    return OpenAIEmbedder()


async def execute(args):
    from app.developer_assistant import index, service
    from app.openai_responses_llm_client import OpenAIResponsesLlmClient
    if args.command == 'index':
        result = await asyncio.to_thread(index.build, embedder,
                                        progress=lambda s: print(s, file=sys.stderr, flush=True))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    client = OpenAIResponsesLlmClient()
    def observe(record):
        if args.trace:
            print(format_trace(record, args.trace_format), file=sys.stderr, flush=True)
    try:
        result = await service.answer(args.question, client=client, embedder_factory=embedder, observe=observe)
        print(service.render(result))
        return 0
    finally:
        await client.close()


def main(argv=None):
    p = parser()
    args = p.parse_args(argv)
    if args.command == '/help' and args.question is None:
        p.print_help()
        return 0
    if args.command == '/help':
        from app.developer_assistant.service import check_question
        try:
            check_question(args.question)
        except ValueError as error:
            p.error(str(error))
    logging.disable(logging.CRITICAL)  # Third-party HTTP/MCP logs must not dump arbitrary input.
    try:
        return asyncio.run(execute(args))
    except KeyboardInterrupt:
        print('Операция отменена.', file=sys.stderr)
        return 130
    except ValueError as error:
        # All ValueErrors crossing this boundary are our content-free categories.
        print('ERROR: ' + str(error), file=sys.stderr)
        return 1
    except Exception:
        print('ERROR: operation_failed; no automatic retry', file=sys.stderr)
        return 1


if __name__ == '__main__':
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding='utf-8', errors='replace')
    raise SystemExit(main())
