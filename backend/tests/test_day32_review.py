import argparse
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml

from app.document_indexing.corpus import ROOT
from app.document_indexing.embedding import DIMENSION, Embeddings
from app.llm_client import LlmResult
from app.openai_agent_payload import generation_payload
from app.pr_review import ReviewError, reject_secrets
from app.pr_review import rag, report, review
from app.token_diagnostics import CountFailure
from test_day32_snapshot import MemoryGitHub, BASE, HEAD, OLD, REVIEWER, PATH, REPO


class Embedder:
    def __init__(self): self.calls, self.closed = [], False
    def embed(self, texts):
        self.calls.append(texts)
        return Embeddings([[1.] + [0.]*(DIMENSION-1) for _ in texts], len(texts))
    def close(self): self.closed = True


class Client:
    def __init__(self, mode='good'): self.mode, self.calls, self.closed = mode, [], False
    async def complete(self, messages, config):
        payload = generation_payload(messages, config)
        self.calls.append(payload)
        data = json.loads(messages[0].content)
        value = dict(status='reviewed', summary='Проверены изменения.', limitations=[], findings=[dict(
            category='bug', severity='medium', title='Возвращается неверное значение',
            explanation='Вызов вернёт ноль вместо единицы.', recommendation='Вернуть правильное значение.',
            change_id='D2', context_ids=[data['documentation'][0]['id'], data['code'][0]['id']])])
        if self.mode == 'empty': value['findings'] = []
        if self.mode == 'abstain': value.update(status='insufficient_context', findings=[])
        if self.mode == 'bad_id': value['findings'][0]['context_ids'] = ['invented']
        if self.mode == 'bad_line': value['findings'][0]['change_id'] = 'D999'
        if self.mode == 'duplicate': value['findings'][0]['context_ids'] = ['S1', 'S1']
        if self.mode == 'extra': value['command'] = 'execute this'
        if self.mode == 'contradiction': value['status'] = 'insufficient_context'
        if self.mode in {'error', 'incomplete', 'refused'}: return LlmResult(self.mode)
        return LlmResult('completed', reply='invalid' if self.mode == 'invalid' else json.dumps(value),
                         resolved_model='gpt-5.6-sol', provider_status='completed')
    async def close(self): self.closed = True


class Counter:
    def __init__(self, count=100): self.value, self.calls, self.closed = count, [], False
    async def count(self, messages, config, *, include_instructions):
        self.calls.append((messages, config, include_instructions))
        if self.value == 'error': raise CountFailure('fixture')
        return self.value
    async def close(self): self.closed = True


@pytest.fixture
def prepared():
    gh = MemoryGitHub()
    snap = gh.snapshot(7)
    groups, queries, coverage = rag.prepare(gh, snap)
    embedder = Embedder()
    context, usage = rag.retrieve(groups, queries, embedder)
    return gh, snap, context, usage


def test_rag_uses_both_groups_and_explicit_revisions_without_crawling():
    gh = MemoryGitHub()
    snap = gh.snapshot(7)
    groups, queries, coverage = rag.prepare(gh, snap)
    assert {s[0] for s in gh.source_reads if s[0].endswith('.md')} == set(rag.DOCS)
    assert all(s[1] == BASE for s in gh.source_reads if s[0].endswith('.md'))
    assert (PATH, HEAD, False) in gh.source_reads
    assert coverage['missing_tests'] == ['backend/tests/test_example.py']
    assert all('import' not in q for q in queries)
    e = Embedder()
    selected, usage = rag.retrieve(groups, queries, e)
    assert set(selected) == {'documentation', 'code'}
    assert all(selected.values()) and len(e.calls) == 2
    assert e.calls[-1] == queries and usage['embedding_calls'] == 2
    assert all(c['revision'] == HEAD for c in selected['code'])
    assert all(c['revision'] == BASE for c in selected['documentation'])
    assert all(c['start_line'] > 0 and c['end_line'] >= c['start_line'] for xs in selected.values() for c in xs)
    assert not any('embedding' in c or 'score' in c for xs in selected.values() for c in xs)


def test_obvious_tests_are_bounded_and_missing_tests_do_not_expand_search():
    assert rag.related_tests('backend/app/first_rag/core.py') == ['backend/tests/test_first_rag.py']
    assert rag.related_tests('backend/app/developer_assistant/index.py') == ['backend/tests/test_day31_index.py']
    assert rag.related_tests('backend/app/developer_assistant/service.py') == ['backend/tests/test_day31_help.py']
    assert rag.related_tests('backend/app/foo.py') == ['backend/tests/test_foo.py']
    assert rag.related_tests('android-app/app/src/main/java/x/Foo.kt') == [
        'android-app/app/src/test/java/x/FooTest.kt', 'android-app/app/src/androidTest/java/x/FooTest.kt']
    assert rag.related_tests('unrelated/file.txt') == []


def test_no_code_and_chunk_limit_stop_before_provider(monkeypatch):
    gh = MemoryGitHub()
    snap = gh.snapshot(7)
    snap.files = [dict(path='readme.md', old_path='readme.md', status='modified', patch='a')]
    with pytest.raises(ReviewError, match='insufficient_context'): rag.prepare(gh, snap)
    snap = gh.snapshot(7)
    monkeypatch.setattr(rag, 'MAX_CHUNKS', 1)
    with pytest.raises(ReviewError, match='too_large'): rag.prepare(gh, snap)


def test_actual_demo_corpus_fits_approved_limits_without_api():
    class LocalSnapshotData:
        def file(self, path, revision, *, optional=False):
            file = ROOT/path
            return file.read_text(encoding='utf-8-sig') if file.exists() else None
    snap = MemoryGitHub().snapshot(7)
    snap.files = [dict(path=p, old_path=p, status='modified', patch='offline sizing') for p in
                  ('backend/app/first_rag/core.py', 'backend/app/developer_assistant/index.py')]
    groups, queries, coverage = rag.prepare(LocalSnapshotData(), snap)
    assert 0 < coverage['chunk_count'] <= 160 and coverage['source_count'] <= 25
    assert len(queries) == 2 and all(groups.values())


def test_untrusted_code_is_chunked_as_text_not_executed(tmp_path):
    gh = MemoryGitHub()
    original = gh.file
    sentinel = tmp_path/'never-created'
    def file(path, revision, *, optional=False):
        if path == PATH:
            return f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('executed')\n"
        return original(path, revision, optional=optional)
    gh.file = file
    groups, _, _ = rag.prepare(gh, gh.snapshot(7))
    assert groups['code'] and not sentinel.exists()


@pytest.mark.asyncio
async def test_single_generation_exact_input_and_evidence_render(prepared):
    gh, snap, context, usage = prepared
    client, counter = Client(), Counter()
    result = await review.analyze(snap, context, client, counter, usage)
    assert len(client.calls) == len(counter.calls) == 1
    payload = client.calls[0]
    sent = json.loads(payload['input'][0]['content'])
    assert sent['diff'] == snap.diff and sent['documentation'] == context['documentation']
    assert sent['code'] == context['code'] and sent['changes'] == list(snap.changes.values())
    assert payload['model'] == 'gpt-5.6' and payload['store'] is False
    assert payload['text']['format']['strict'] is True and payload['max_output_tokens'] == 4000
    assert counter.calls[0][2] is True and payload['truncation'] == 'disabled'
    rendered = report.render(REPO, 7, result, snap=snap, context=context, usage=usage)
    assert HEAD in rendered and f'/blob/{HEAD}/{PATH}#L2-L2' in rendered
    assert f'/blob/{BASE}/README.md' in rendered and 'S1' in rendered and 'C1' in rendered
    assert 'Основания' in rendered and 'Advisory' in rendered


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['bad_id', 'bad_line', 'duplicate', 'extra', 'contradiction', 'invalid',
                                  'error', 'incomplete', 'refused'])
async def test_invalid_result_is_explicit_without_second_generation(prepared, mode):
    _, snap, context, usage = prepared
    c = Client(mode)
    with pytest.raises(ReviewError) as error:
        await review.analyze(snap, context, c, Counter(), usage)
    assert error.value.status in {'provider_error', 'validation_error'}
    assert len(c.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['empty', 'abstain'])
async def test_categories_can_be_empty(prepared, mode):
    _, snap, context, usage = prepared
    result = await review.analyze(snap, context, Client(mode), Counter(), usage)
    assert not result['findings']


@pytest.mark.asyncio
@pytest.mark.parametrize('count', [24001, 'error', -1, True])
async def test_preflight_stops_generation(prepared, count):
    _, snap, context, usage = prepared
    c = Client()
    with pytest.raises(ReviewError): await review.analyze(snap, context, c, Counter(count), usage)
    assert not c.calls


def test_untrusted_text_cannot_create_links_mentions_or_workflow_commands():
    text = report.escape('![image](https://evil.invalid)\n::error::secret\n<script>x</script> @owner')
    assert '![' not in text and '<script>' not in text and '@owner' not in text
    assert '\n::error::' not in text and r'https\:' in text


def test_secret_input_is_rejected_without_echo(monkeypatch):
    token = 'fixture-credential-1234567'
    monkeypatch.setenv('OPENAI_API_KEY', token)
    with pytest.raises(ReviewError) as e: reject_secrets('text ' + token)
    assert token not in str(e.value)


def test_publish_updates_one_comment_and_preserves_user_comment(prepared):
    gh, snap, _, _ = prepared
    user_comment = dict(id=99, body=report.MARKER + '{}-->', user=dict(login='someone', type='User'))
    gh.comments = [user_comment]
    assert report.publish(gh, snap, 'first', source_run=100, reviewer_sha=REVIEWER) == 50
    assert report.publish(gh, snap, 'second', source_run=101, reviewer_sha=REVIEWER) == 50
    assert [x[0] for x in gh.writes] == ['POST', 'PATCH']
    assert user_comment in gh.comments and len(gh.comments) == 2
    assert gh.comments[-1]['body'].endswith('second')


def test_late_old_run_cannot_replace_new_report(prepared):
    gh, snap, _, _ = prepared
    report.publish(gh, snap, 'new', source_run=102, reviewer_sha=REVIEWER)
    with pytest.raises(ReviewError, match='superseded'):
        report.publish(gh, snap, 'old', source_run=100, reviewer_sha=REVIEWER)
    assert len(gh.writes) == 1
    gh.metadata['head']['sha'] = 'f'*40
    with pytest.raises(ReviewError, match='stale'):
        report.publish(gh, snap, 'late', source_run=103, reviewer_sha=REVIEWER)
    assert len(gh.writes) == 1


def test_race_after_write_is_visible_and_duplicate_bot_markers_refused(prepared):
    gh, snap, _, _ = prepared
    original = gh.current
    calls = 0
    def current(s):
        nonlocal calls
        calls += 1
        if calls == 2: gh.metadata['head']['sha'] = 'e'*40
        return original(s)
    gh.current = current
    with pytest.raises(ReviewError, match='stale'):
        report.publish(gh, snap, 'snapshot', source_run=100, reviewer_sha=REVIEWER)
    assert len(gh.writes) == 1 and HEAD in gh.writes[0][2]
    gh.comments.append(deepcopy(gh.comments[0]))
    with pytest.raises(ReviewError, match='ambiguous_bot_comment'): report.existing_comment(gh, 7)


@pytest.fixture
def cli():
    spec = importlib.util.spec_from_file_location('day32_cli', ROOT/'backend/scripts/day32_review.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_local_cli_runs_all_layers_without_publication(cli, monkeypatch, capsys):
    gh, e, c, counter = MemoryGitHub(), Embedder(), Client(), Counter()
    monkeypatch.setenv('OPENAI_API_KEY', 'fake-key-for-tests')
    monkeypatch.setenv('GITHUB_TOKEN', 'fake-github-for-tests')
    result = await cli.execute(argparse.Namespace(mode='local', repo=REPO, pr=7),
        gh_factory=lambda *a: gh, embedder_factory=lambda: e, client_factory=lambda: c, counter_factory=lambda: counter)
    assert result == 0 and 'reviewed' in capsys.readouterr().out
    assert not gh.writes and e.closed and c.closed and counter.closed


@pytest.mark.asyncio
async def test_actions_cli_reports_and_publishes_only_after_gate(cli, monkeypatch, tmp_path, capsys):
    gh = MemoryGitHub()
    event_path = tmp_path/'event.json'
    event_path.write_text(json.dumps(gh.event))
    summary = tmp_path/'summary.md'
    for key, value in dict(OPENAI_API_KEY='fake-key-for-tests', GITHUB_TOKEN='fake-github-for-tests',
            GITHUB_REPOSITORY=REPO, GITHUB_RUN_ID='200', GITHUB_EVENT_PATH=str(event_path),
            GITHUB_STEP_SUMMARY=str(summary)).items(): monkeypatch.setenv(key, value)
    monkeypatch.setattr(cli, 'trusted_environment', lambda env: REVIEWER)
    result = await cli.execute(argparse.Namespace(mode='actions'), gh_factory=lambda *a: gh,
        embedder_factory=Embedder, client_factory=Client, counter_factory=Counter)
    output = capsys.readouterr().out
    assert result == 0 and len(gh.writes) == 1 and summary.read_text(encoding='utf-8') == output.rstrip('\n')
    assert REVIEWER in output and 'fake-key' not in output and 'fake-github' not in output
    assert '#issuecomment-50' in output and '> The index' not in output


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['incomplete_diff', 'provider', 'publication'])
async def test_actions_failures_have_explicit_summary(cli, monkeypatch, tmp_path, capsys, failure):
    gh = MemoryGitHub()
    event = tmp_path/'event.json'
    event.write_text(json.dumps(gh.event))
    summary = tmp_path/'summary.md'
    for key, value in dict(OPENAI_API_KEY='fake-key-for-tests', GITHUB_TOKEN='fake-github-for-tests',
            GITHUB_REPOSITORY=REPO, GITHUB_RUN_ID='200', GITHUB_EVENT_PATH=str(event),
            GITHUB_STEP_SUMMARY=str(summary)).items(): monkeypatch.setenv(key, value)
    monkeypatch.setattr(cli, 'trusted_environment', lambda env: REVIEWER)
    if failure == 'incomplete_diff': gh.files[0]['additions'] = 4
    if failure == 'publication':
        original = gh.request
        def request(path, **kwargs):
            if kwargs.get('method') in {'POST', 'PATCH'}:
                raise ReviewError('github_error', 'fixture_failure')
            return original(path, **kwargs)
        gh.request = request
    client = Client('incomplete' if failure == 'provider' else 'good')
    result = await cli.execute(argparse.Namespace(mode='actions'), gh_factory=lambda *a: gh,
        embedder_factory=Embedder, client_factory=lambda: client, counter_factory=Counter)
    output = summary.read_text(encoding='utf-8').replace('\\', '')
    expected = 'provider_error' if failure == 'provider' else 'publication_error' if failure == 'publication' else 'incomplete_diff'
    assert result == 1 and expected in output and 'Нет замечаний' not in output
    if failure == 'incomplete_diff': assert not client.calls and not gh.writes
    if failure == 'provider': assert len(client.calls) == 1 and 'provider' in gh.writes[0][2]


@pytest.mark.asyncio
async def test_bad_event_stops_before_any_provider(cli, monkeypatch, tmp_path, capsys):
    gh = MemoryGitHub()
    gh.run['pull_requests'] = []
    event_path = tmp_path/'event.json'
    event_path.write_text(json.dumps(gh.event))
    for key, value in dict(GITHUB_TOKEN='fixture-token', GITHUB_REPOSITORY=REPO, GITHUB_RUN_ID='200',
                           GITHUB_EVENT_PATH=str(event_path)).items(): monkeypatch.setenv(key, value)
    monkeypatch.delenv('GITHUB_STEP_SUMMARY', raising=False)
    monkeypatch.setattr(cli, 'trusted_environment', lambda env: REVIEWER)
    factory = Mock(side_effect=AssertionError('provider must not be constructed'))
    result = await cli.execute(argparse.Namespace(mode='actions'), gh_factory=lambda *a: gh,
                               embedder_factory=factory)
    assert result == 1 and 'ambiguous_pr_association' in capsys.readouterr().out.replace('\\', '')
    assert not gh.writes and not factory.called


def test_trusted_environment_requires_main_workflow_and_actual_checkout(cli, monkeypatch):
    env = dict(GITHUB_ACTIONS='true', GITHUB_EVENT_NAME='workflow_run', GITHUB_REF='refs/heads/main',
        GITHUB_REPOSITORY=REPO, GITHUB_SHA=REVIEWER,
        GITHUB_WORKFLOW_REF=REPO+'/.github/workflows/day32-pr-review.yml@refs/heads/main')
    monkeypatch.setattr(cli.subprocess, 'run', lambda *a, **k: argparse.Namespace(stdout=REVIEWER+'\n'))
    assert cli.trusted_environment(env) == REVIEWER
    with pytest.raises(ReviewError): cli.trusted_environment(dict(env, GITHUB_REF='refs/pull/7/merge'))
    with pytest.raises(ReviewError): cli.trusted_environment(dict(env, GITHUB_SHA=HEAD))


def test_workflow_security_structure_and_pins():
    # BaseLoader preserves YAML's `on` key instead of interpreting it as a YAML 1.1 boolean.
    signal = yaml.load((ROOT/'.github/workflows/day32-pr-signal.yml').read_text(), Loader=yaml.BaseLoader)
    trusted = yaml.load((ROOT/'.github/workflows/day32-pr-review.yml').read_text(), Loader=yaml.BaseLoader)
    assert signal['permissions'] == {} and set(signal['on']) == {'pull_request'}
    assert all('uses' not in step and 'env' not in step for step in signal['jobs']['signal']['steps'])
    assert set(trusted['on']) == {'workflow_run'}
    job = trusted['jobs']['review']
    assert job['environment'] == 'day32-review'
    assert job['permissions'] == {'contents': 'read', 'actions': 'read', 'pull-requests': 'write'}
    assert trusted['concurrency']['cancel-in-progress'] == 'false'
    assert 'pull_requests[0].number' in trusted['concurrency']['group']
    steps = job['steps']
    assert steps[0]['with'] == {'ref': '${{ github.sha }}', 'persist-credentials': 'false'}
    assert all(len(s['uses'].split('@')[1]) == 40 for s in steps if 'uses' in s)
    assert all('OPENAI_API_KEY' not in s.get('env', {}) for s in steps[:-1])
    assert steps[-1]['run'] == 'python backend/scripts/day32_review.py actions'
    text = json.dumps(trusted)
    assert not any(x in text for x in ('download-artifact', 'actions/cache', 'pull_request.head.sha', 'gh pr checkout'))
