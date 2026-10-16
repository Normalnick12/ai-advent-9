"""Day 32 CLI; default local mode never publishes. Reviewed files remain in memory."""
import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.pr_review import ReviewError, TECHNICAL, require, sha
from app.pr_review.github import GitHub, resolve_run
from app.pr_review import rag, report, review


def parser():
    p = argparse.ArgumentParser(description='Day 32: ограниченное RAG-ревью настоящего PR')
    commands = p.add_subparsers(dest='mode', required=True)
    local = commands.add_parser('local', help='Отчёт в stdout, без публикации')
    local.add_argument('--repo', required=True)
    local.add_argument('--pr', required=True, type=int)
    commands.add_parser('actions', help='Только доверенный workflow_run из main')
    return p


def trusted_environment(env):
    require(env.get('GITHUB_ACTIONS') == 'true' and env.get('GITHUB_EVENT_NAME') == 'workflow_run'
            and env.get('GITHUB_REF') == 'refs/heads/main'
            and env.get('GITHUB_WORKFLOW_REF') == env.get('GITHUB_REPOSITORY', '')
                + '/.github/workflows/day32-pr-review.yml@refs/heads/main',
            'configuration_error', 'not_trusted_workflow')
    reviewer = sha(env.get('GITHUB_SHA'))
    actual = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
    require(actual == reviewer, 'configuration_error', 'checkout_not_reviewer_sha')
    return reviewer


async def execute(args, *, gh_factory=GitHub, embedder_factory=None, client_factory=None, counter_factory=None):
    actions = args.mode == 'actions'
    gh = snap = None
    context, usage, coverage = {}, {}, {}
    number, source_run, reviewer_sha = getattr(args, 'pr', 0), None, ''
    repo, own_run = getattr(args, 'repo', ''), None
    result = dict(status='configuration_error', reason='not_started')
    try:
        if actions:
            reviewer_sha = trusted_environment(os.environ)
            repo = os.environ['GITHUB_REPOSITORY']
            own_run = int(os.environ['GITHUB_RUN_ID'])
            event_path = Path(os.environ['GITHUB_EVENT_PATH'])
            require(event_path.stat().st_size <= 2*1024*1024, 'configuration_error', 'event_size_limit')
            event = json.loads(event_path.read_text(encoding='utf-8'))
        token = os.getenv('GITHUB_TOKEN') or os.getenv('GH_TOKEN', '')
        require(bool(token), 'configuration_error', 'github_token_missing')
        gh = gh_factory(repo, token)
        if actions:
            number, source_run = resolve_run(gh, event, reviewer_sha=reviewer_sha)
        snap = gh.snapshot(number)
        groups, queries, coverage = rag.prepare(gh, snap)
        gh.current(snap)
        if not os.getenv('OPENAI_API_KEY'):
            raise ReviewError('configuration_error', 'openai_key_missing')
        from app.document_indexing.embedding import OpenAIEmbedder
        from app.openai_responses_llm_client import OpenAIResponsesLlmClient
        from app.openai_token_counter import OpenAIInputTokenCounter
        embedder = (embedder_factory or OpenAIEmbedder)()
        try:
            context, counts = await asyncio.to_thread(rag.retrieve, groups, queries, embedder)
            usage.update(counts)
        finally:
            embedder.close()
        gh.current(snap)
        client, counter = (client_factory or OpenAIResponsesLlmClient)(), (counter_factory or OpenAIInputTokenCounter)()
        try:
            result = await review.analyze(snap, context, client, counter, usage)
        finally:
            await client.close()
            await counter.close()
        result['limitations'] += ['RAG ограничен пятью документами Day 31, изменённым кодом и очевидными тестами.']
    except ReviewError as error:
        result = dict(status=error.status, reason=error.reason)
    except (KeyError, TypeError, ValueError, OSError, subprocess.SubprocessError):
        result = dict(status='github_error' if gh else 'configuration_error', reason='invalid_or_unavailable_data')
    except Exception:
        result = dict(status='provider_error', reason='operation_failed')
    usage['coverage'] = coverage
    comment_id = None
    try:
        text = report.render(repo, number, result, snap=snap, context=context, usage=usage,
                             reviewer_sha=reviewer_sha, run_id=own_run)
    except ReviewError as error:
        result = dict(status=error.status, reason=error.reason)
        text = report.render(repo, number, result, snap=snap, reviewer_sha=reviewer_sha, run_id=own_run)
    if actions and gh and snap and result['status'] not in {'stale', 'superseded', 'skipped'}:
        try:
            comment_id = report.publish(gh, snap, text, source_run=source_run, reviewer_sha=reviewer_sha)
        except ReviewError as error:
            result = dict(status=error.status, reason=error.reason)
            text = report.render(repo, number, result, snap=snap, context=context, usage=usage,
                                 reviewer_sha=reviewer_sha, run_id=own_run)
        except Exception:
            result = dict(status='publication_error', reason='publication_failed')
            text = report.render(repo, number, result, snap=snap, reviewer_sha=reviewer_sha, run_id=own_run)
    if gh:
        gh.close()
    if actions:
        text = report.summary(repo, number, result, snap=snap, context=context, usage=usage,
            reviewer_sha=reviewer_sha, run_id=own_run, comment_id=comment_id)
    if actions and os.getenv('GITHUB_STEP_SUMMARY'):
        # The runtime owns this path. No PR/model field is used as a filesystem path.
        Path(os.environ['GITHUB_STEP_SUMMARY']).write_text(text, encoding='utf-8')
    print(text)
    return 1 if result['status'] in TECHNICAL else 0


def main(argv=None):
    args = parser().parse_args(argv)
    logging.disable(logging.CRITICAL)
    try:
        return asyncio.run(execute(args))
    except KeyboardInterrupt:
        print('Day 32: cancelled')
        return 130
    except Exception:
        print('Day 32: configuration_error; report_unavailable')
        return 1


if __name__ == '__main__':
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding='utf-8', errors='replace')
    raise SystemExit(main())
