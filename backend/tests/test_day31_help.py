import asyncio
import importlib.util
import json
from functools import partial
from pathlib import Path
import subprocess
import sys
from unittest.mock import AsyncMock, Mock

import jsonschema
import pytest

from app.developer_assistant import index, mcp_client, service
from app.document_indexing.corpus import ROOT
from app.document_indexing.embedding import DIMENSION, Embeddings
from app.grounded_rag.core import abstention
from app.first_rag.core import Index, vector_norm
from app.llm_client import LlmResult
from app.openai_agent_payload import generation_payload

BRANCH = dict(status='branch', branch='day31-test', call_id='596c174e-4ac3-49fa-bd8c-a7296c5b3646', server_pid=1)


class Embedder:
    def __init__(self): self.calls, self.closed = [], False
    def embed(self, texts):
        self.calls.append(texts)
        return Embeddings([[1.] + [0.] * (DIMENSION - 1) for _ in texts], len(texts))
    def close(self): self.closed = True


class Client:
    def __init__(self, mode='good'): self.calls, self.mode = [], mode
    async def complete(self, messages, config):
        payload = generation_payload(messages, config)
        self.calls.append(payload)
        context = json.loads(payload['input'][0]['content'])['context']
        c = context[0]
        answer = dict(status='answered', answer='Backend отвечает Android. [S1]',
                      citation_ids=[next(e['id'] for e in c['evidence'] if e['quote'] == 'Backend отвечает Android.')])
        if self.mode == 'abstain': answer = {k:v for k,v in abstention().items() if k in {'status','answer'}} | {'citation_ids': []}
        if self.mode == 'bad_quote': answer['citations'] = [{'quote': 'invented'}]
        if self.mode == 'bad_source': answer['sources'] = [{'source': 'secret.env'}]
        if self.mode == 'bad_id': answer['citation_ids'] = ['forged']
        if self.mode in {'incomplete', 'refused', 'error'}: return LlmResult(self.mode)
        return LlmResult('completed', reply='broken' if self.mode == 'invalid' else json.dumps(answer))


@pytest.fixture
def project(tmp_path):
    (tmp_path / 'README.md').write_text('# Project\nBackend отвечает Android.\n', encoding='utf8')
    manifest = tmp_path / 'corpus.json'
    manifest.write_text(json.dumps({'sources': [{'source': 'README.md', 'source_type': 'documentation'}]}))
    opts = dict(root=tmp_path, manifest=manifest, path=tmp_path / 'index.sqlite3')
    index.build(Embedder, **opts)
    return opts


async def branch_reader():
    return BRANCH, dict(call='completed', discovery='completed', call_id=BRANCH['call_id'],
                        server_pid=1, server_event='unavailable')


@pytest.mark.asyncio
async def test_actual_context_counts_sources_and_trace(project):
    e, client, trace = Embedder(), Client(), []
    result = await service.answer('Как устроен проект?', client=client, embedder_factory=lambda: e,
                                  branch_reader=branch_reader, observe=trace.append, **project)
    assert e.calls == [['Как устроен проект?']] and e.closed and len(client.calls) == 1
    sent = client.calls[0]
    assert sent['model'] == 'gpt-5.6' and sent['reasoning']['effort'] == 'none'
    assert sent['max_output_tokens'] == 3000 and sent['store'] is False
    assert sent['text']['format']['type'] == 'json_schema' and sent['truncation'] == 'disabled'
    user = json.loads(sent['input'][0]['content'])
    assert user['context'] == result['context'] and user['git_context'] == BRANCH
    assert [t['event'] for t in trace] == ['mcp', 'retrieval', 'generation', 'validation']
    assert trace[0]['server_event'] == 'unavailable'  # Valid MCP result succeeds without stderr evidence.
    assert trace[1]['hits'][0]['source'] == 'README.md'
    assert trace[-1]['status'] == 'passed'
    rendered = service.render(result)
    assert 'Git (MCP): day31-test' in rendered and 'README.md:1-' in rendered
    assert 'Quote: Backend отвечает Android.' in rendered
    raw_trace = json.dumps(trace)
    assert 'Как устроен проект' not in raw_trace and 'Backend отвечает Android' not in raw_trace


@pytest.mark.parametrize('mode', ['bad_quote', 'bad_source', 'bad_id', 'invalid', 'incomplete', 'refused', 'error'])
@pytest.mark.asyncio
async def test_bad_generation_is_not_success_or_retried(project, mode):
    e, client = Embedder(), Client(mode)
    with pytest.raises(ValueError):
        await service.answer('Question', client=client, embedder_factory=lambda: e,
                             branch_reader=branch_reader, **project)
    assert len(client.calls) == 1 and len(e.calls) == 1


@pytest.mark.asyncio
async def test_abstention_and_detached(project):
    async def detached(): return {**BRANCH, 'status': 'detached', 'branch': None}, {}
    result = await service.answer('Unknown?', client=Client('abstain'), embedder_factory=Embedder,
                                 branch_reader=detached, **project)
    assert result['grounded'] == abstention()
    assert 'Git (MCP): detached HEAD' in service.render(result)


@pytest.mark.asyncio
async def test_real_missing_mcp_has_no_git_or_provider_fallback(project, monkeypatch):
    client, factory = Client(), Mock(side_effect=AssertionError('No embeddings allowed'))
    # A parent-process Git fallback would hit this; child transport does not use subprocess.run.
    monkeypatch.setattr(subprocess, 'run', Mock(side_effect=AssertionError('No direct Git allowed')))
    reader = partial(mcp_client.get_branch, launcher=project['root'] / 'absent.py', timeout=3)
    with pytest.raises(mcp_client.McpFailure):
        await service.answer('Question', client=client, embedder_factory=factory,
                             branch_reader=reader, **project)
    factory.assert_not_called()
    assert not client.calls and not subprocess.run.called


@pytest.mark.asyncio
async def test_stale_before_mcp_and_provider(project):
    async def forbidden(): raise AssertionError('MCP must not run')
    (project['root'] / 'README.md').write_text('changed')
    with pytest.raises(ValueError, match='stale'):
        await service.answer('Question', client=Client(), embedder_factory=Mock(),
                             branch_reader=forbidden, **project)


@pytest.mark.asyncio
async def test_provider_trace_does_not_leak_question_or_secret(project):
    e, client = Embedder(), Client()
    with_trace = []
    await service.answer('SECRET-QUESTION', client=client, embedder_factory=lambda: e,
                         branch_reader=branch_reader, observe=with_trace.append, **project)
    no_trace = Client()
    await service.answer('SECRET-QUESTION', client=no_trace, embedder_factory=Embedder,
                         branch_reader=branch_reader, **project)
    assert client.calls == no_trace.calls
    assert 'SECRET-QUESTION' not in json.dumps(with_trace)


@pytest.mark.parametrize('args,expected', [(['--help'], 0), (['/help'], 0),
                                         (['/help', '   '], 2), (['wrong'], 2)])
def test_cli_help_other_cwd_and_invalid_input(tmp_path, args, expected):
    result = subprocess.run([sys.executable, str(ROOT / 'backend/scripts/day31_help.py'), *args],
                             cwd=tmp_path, capture_output=True, encoding='utf8')
    assert result.returncode == expected
    assert 'Traceback' not in result.stderr and 'OPENAI_API_KEY' not in result.stderr


def test_cli_error_codes_and_render_controls(monkeypatch, capsys):
    spec = importlib.util.spec_from_file_location('day31_cli', ROOT / 'backend/scripts/day31_help.py')
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    monkeypatch.setattr(cli.logging, 'disable', Mock())
    async def failure(_): raise mcp_client.McpFailure('mcp_timeout')
    monkeypatch.setattr(cli, 'execute', failure)
    assert cli.main(['/help', 'Question']) == 1
    assert 'mcp_timeout' in capsys.readouterr().err
    async def cancelled(_): raise KeyboardInterrupt()
    monkeypatch.setattr(cli, 'execute', cancelled)
    assert cli.main(['/help', 'Question']) == 130
    assert '\x1b' not in service.safe('branch\x1b[31m')


def test_schema_limits_evidence_ids_and_reconstructs_exact_quotes():
    text = '\n'.join(f'Literal source line {i}: keep punctuation.\n' for i in range(50))
    context = [dict(source='docs/project-structure.md', section='Exact / Section', chunk_id='actual-id', text=text)]
    options = service.quote_options(text)
    assert len(options) <= 24 and all(q in text and 0 < len(q) <= 400
                                    and '\n' not in q and '\r' not in q for q in options)
    schema = service.grounded_config(context).text_format['schema']
    valid = dict(status='answered', answer='Supported.', citation_ids=['S1Q1'])
    jsonschema.validate(valid, schema)
    complete = json.loads(service.with_sources(json.dumps(valid), context))
    assert complete['citations'] == [dict(chunk_id='actual-id', quote=options[0])]
    assert complete['sources'] == [dict(source=context[0]['source'], section=context[0]['section'], chunk_id='actual-id')]
    valid['citation_ids'] = ['forged']
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(valid, schema)
    with pytest.raises(ValueError, match='unknown_evidence'):
        service.with_sources(json.dumps(valid), context)


def test_retrieval_includes_document_intro_within_eight_hits():
    def chunk(cid, source, ordinal, x, y, text):
        return dict(chunk_id=cid, source=source, ordinal=ordinal,
                    embedding=[float(x), float(y)] + [0.] * (DIMENSION - 2), text=text)
    chunks = [chunk('intro', 'README.md', 0, 0, 1, '# Setup\nRequires PowerShell 7.'),
              chunk('best', 'README.md', 1, 1, 0, '# Tests\nRun unit tests.')]
    chunks += [chunk(f'other{i}', 'docs/other.md', i, 1, 1, 'Other documentation.') for i in range(7)]
    idx = Index({}, chunks, [vector_norm(c['embedding']) for c in chunks], {'README.md', 'docs/other.md'})
    hits = service.retrieve(idx, [1.] + [0.] * (DIMENSION - 1))
    assert len(hits) == 8 and hits[0]['chunk_id'] == 'best'
    assert hits[-1]['chunk_id'] == 'intro' and hits[-1]['selection'] == 'source_intro'
    assert hits[-1]['cosine_rank'] == 9 and hits[-1]['rank'] == 8
    assert 'other6' not in {h['chunk_id'] for h in hits}


@pytest.fixture
def day31_cli():
    spec = importlib.util.spec_from_file_location('day31_cli', ROOT / 'backend/scripts/day31_help.py')
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    return cli


@pytest.mark.parametrize('flags,mode', [(['--trace'], 'jsonl'),
    (['--trace', '--trace-format', 'jsonl'], 'jsonl'),
    (['--trace', '--trace-format', 'text'], 'text'), (['--trace-format', 'text'], None)])
@pytest.mark.asyncio
async def test_cli_trace_formats_unicode_and_unchanged_answer(day31_cli, monkeypatch, capsys, flags, mode):
    from app import openai_responses_llm_client
    secret = 'SECRET-API-KEY-DO-NOT-PRINT'
    question = 'SECRET-QUESTION-DO-NOT-TRACE'
    monkeypatch.setenv('OPENAI_API_KEY', secret)
    hits = [dict(chunk_id=str(i) * 64, source='docs/структура.md', section='Структура проекта',
                 start_line=i + 2, end_line=i + 5, score=0.876543 - i / 10) for i in range(4)]
    records = [dict(event='mcp', discovery='completed', tool='get_current_branch', call='completed',
                    call_id=BRANCH['call_id'], server_pid=1234, server_event='matched'),
               dict(event='retrieval', fingerprint='a' * 64, hits=hits),
               dict(event='generation', requested_model='gpt-5.6', resolved_model='gpt-5.6-sol',
                    status='completed', usage=dict(input_tokens=123, output_tokens=45, total_tokens=168)),
               dict(event='validation', status='passed', errors=[])]
    context = [dict(label='[S1]', **hits[0])]
    result = dict(branch={**BRANCH, 'branch': 'ветка/проверка'}, context=context,
        grounded=dict(status='answered', answer='Backend отвечает Android. [S1]',
            sources=[dict(chunk_id=hits[0]['chunk_id'])],
            citations=[dict(chunk_id=hits[0]['chunk_id'], quote='Backend отвечает Android.')]))
    client = Mock(close=AsyncMock())
    monkeypatch.setattr(openai_responses_llm_client, 'OpenAIResponsesLlmClient', lambda: client)

    async def answer(actual_question, **kwargs):
        assert actual_question == question
        for record in records:
            kwargs['observe'](record)
        return result

    mock_answer = AsyncMock(side_effect=answer)
    monkeypatch.setattr(service, 'answer', mock_answer)
    assert await day31_cli.execute(day31_cli.parser().parse_args(['/help', question, *flags])) == 0
    captured = capsys.readouterr()
    assert captured.out == service.render(result) + '\n'
    assert 'Git (MCP): ветка/проверка' in captured.out
    assert 'Quote: Backend отвечает Android.' in captured.out
    assert secret not in captured.out + captured.err and question not in captured.err
    mock_answer.assert_awaited_once()
    client.close.assert_awaited_once()
    if mode == 'jsonl':
        assert [json.loads(line) for line in captured.err.splitlines()] == records
        assert 'Структура проекта' in captured.err and r'\u' not in captured.err
        assert 'a' * 64 in captured.err and BRANCH['call_id'] in captured.err
        assert captured.err.encode('utf8').decode('utf8') == captured.err
    elif mode == 'text':
        assert 'MCP: discovery=completed; tool=get_current_branch; call=completed; server_event=matched' in captured.err
        assert 'RAG: фрагментов=4; первые 3:' in captured.err
        assert 'docs/структура.md:2-5  score=0.877' in captured.err
        assert 'docs/структура.md:5-8' not in captured.err
        assert 'LLM: model=gpt-5.6-sol; status=completed; input_tokens=123, output_tokens=45, total_tokens=168' in captured.err
        assert 'Validation: passed' in captured.err
        for hidden in ('a' * 64, hits[0]['chunk_id'], BRANCH['call_id'], 'server_pid', 'chunk_id', 'fingerprint', r'\u'):
            assert hidden not in captured.err
    else:
        assert captured.err == ''


def test_text_trace_optional_usage_event_and_control_safety(day31_cli):
    assert day31_cli.format_trace(dict(event='generation', requested_model='gpt-5.6', status='error', usage=None), 'text') == 'LLM: model=gpt-5.6; status=error'
    assert 'server_event=unavailable' in day31_cli.format_trace(dict(event='mcp', server_event='unavailable'), 'text')
    record = dict(event='validation', status='validation_failed\n\x1b[31m', prompt='SECRET-PROMPT', env='SECRET-ENV')
    text = day31_cli.format_trace(record, 'text')
    assert text.startswith('Validation: validation_failed')
    assert '\n' not in text and '\x1b' not in text and 'SECRET' not in text
