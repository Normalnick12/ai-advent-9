import base64
from copy import deepcopy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

from app.pr_review import ReviewError, SIGNAL_PATH, source_path
from app.pr_review.diff import parse_diff, parse_patch
from app.pr_review.github import GitHub, resolve_run

BASE, HEAD, OLD, REVIEWER = ('a'*40, 'b'*40, 'c'*40, 'd'*40)
REPO = 'owner/project'
PATH = 'backend/app/example.py'
DIFF = ('diff --git a/' + PATH + ' b/' + PATH + '\nindex 123..456 100644\n'
        '--- a/' + PATH + '\n+++ b/' + PATH + '\n@@ -1,2 +1,2 @@\n def value():\n-    return 1\n+    return 0\n')
FILE = dict(filename=PATH, status='modified', additions=1, deletions=1, patch='unused')


def metadata():
    repo = dict(id=9, full_name=REPO, default_branch='main')
    return dict(number=7, id=77, state='open', merged=False, changed_files=1,
        user=dict(login='owner'), base=dict(ref='main', sha=BASE, repo=repo),
        head=dict(ref='feature', sha=HEAD, repo=repo))


def event_run():
    p = metadata()
    assoc = dict(number=7, id=77, head=deepcopy(p['head']), base=deepcopy(p['base']))
    run = dict(id=100, workflow_id=20, path=SIGNAL_PATH, event='pull_request', status='completed',
        conclusion='success', repository=deepcopy(p['base']['repo']),
        head_repository=deepcopy(p['head']['repo']), head_sha=HEAD, pull_requests=[assoc],
        actor=dict(login='owner'), triggering_actor=dict(login='owner'))
    return dict(action='completed', repository=deepcopy(p['base']['repo']), workflow_run=run)


class MemoryGitHub(GitHub):
    """Real REST snapshot/comment code over HTTP fixtures; source files are in-memory data."""
    def __init__(self, repo=REPO, token='fixture-token'):
        self.metadata = metadata()
        self.event = event_run()
        self.run = deepcopy(self.event['workflow_run'])
        self.raw_diff, self.files = DIFF, [deepcopy(FILE)]
        self.comments, self.writes, self.calls = [], [], []
        self.source_reads = []
        super().__init__(repo, token, client=httpx.Client(transport=httpx.MockTransport(self.handle)))

    def handle(self, request):
        assert request.url.host == 'api.github.com'
        self.calls.append((request.method, request.url.path))
        suffix = request.url.path.removeprefix('/repos/' + REPO)
        if request.method in {'POST', 'PATCH'}:
            body = json.loads(request.content)['body']
            self.writes.append((request.method, suffix, body))
            c = dict(id=50, body=body, user=dict(login='github-actions[bot]', type='Bot'))
            self.comments = [x for x in self.comments if x['id'] != 50] + [c]
            return httpx.Response(201 if request.method == 'POST' else 200, json=c)
        if suffix == '/pulls/7':
            if request.headers['accept'] == 'application/vnd.github.diff':
                return httpx.Response(200, text=self.raw_diff)
            return httpx.Response(200, json=self.metadata)
        routes = {'': self.event['repository'], '/pulls/7/files': self.files,
                  '/compare/' + BASE + '...' + HEAD: dict(merge_base_commit=dict(sha=OLD)),
                  '/actions/workflows/day32-pr-signal.yml': dict(id=20, path=SIGNAL_PATH),
                  '/actions/runs/100': self.run, '/issues/7/comments': self.comments}
        return httpx.Response(200, json=routes[suffix]) if suffix in routes else httpx.Response(404)

    def file(self, path, revision, *, optional=False):
        self.source_reads.append((path, revision, optional))
        if optional:
            return None
        if path.endswith('.md'):
            return '# Contract\nThe index must be fresh. Source files are never executed.\n'
        return 'def value():\n    return 0\n'


def test_real_rest_snapshot_and_changed_line_sides():
    gh = MemoryGitHub()
    snap = gh.snapshot(7)
    assert (snap.base, snap.head, snap.merge_base) == (BASE, HEAD, OLD)
    assert snap.diff == DIFF
    assert snap.changes['D1'] == dict(id='D1', path=PATH, revision=OLD, side='old',
                                     start_line=2, end_line=2, text='    return 1')
    assert snap.changes['D2']['revision'] == HEAD
    assert snap.changes['D2']['start_line'] == 2
    assert all(method == 'GET' for method, _ in gh.calls)


@pytest.mark.parametrize('edit,status', [
    (lambda g: setattr(g, 'raw_diff', DIFF.rsplit('\n+', 1)[0]), 'incomplete_diff'),
    (lambda g: g.files[0].update(additions=2), 'incomplete_diff'),
    (lambda g: g.metadata.update(changed_files=2), 'incomplete_diff'),
    (lambda g: g.metadata.update(changed_files=11), 'too_large'),
    (lambda g: setattr(g, 'raw_diff', DIFF + 'x'*131073), 'too_large'),
    (lambda g: g.files[0].update(filename='.env'), 'unsupported_scope'),
    (lambda g: setattr(g, 'raw_diff', DIFF.replace('100644', '120000')), 'unsupported_scope'),
])
def test_incomplete_or_oversized_snapshot_fails_closed(edit, status):
    gh = MemoryGitHub()
    edit(gh)
    with pytest.raises(ReviewError) as error:
        gh.snapshot(7)
    assert error.value.status == status
    assert not gh.writes


def test_snapshot_rechecks_sha_after_collection():
    gh = MemoryGitHub()
    original = gh.pr
    calls = 0
    def read(number):
        nonlocal calls
        calls += 1
        if calls == 2:
            gh.metadata['head']['sha'] = 'e'*40
        return original(number)
    gh.pr = read
    with pytest.raises(ReviewError, match='stale'):
        gh.snapshot(7)


@pytest.mark.parametrize('status,patch,adds,dels', [
    ('added', '@@ -0,0 +1 @@\n+x\n', 1, 0),
    ('removed', '@@ -1 +0,0 @@\n-x\n', 0, 1),
    ('renamed', '', 0, 0),
])
def test_add_delete_and_rename(status, patch, adds, dels):
    anchors, a, d = parse_patch(patch, old_path='old.py', new_path='new.py',
                              old_revision=OLD, new_revision=HEAD)
    assert (a, d) == (adds, dels)
    if anchors:
        assert anchors['D1']['path'] == ('old.py' if status == 'removed' else 'new.py')
    raw = 'diff --git a/old.py b/new.py\nsimilarity index 100%\nrename from old.py\nrename to new.py\n'
    # Rename without changed text is explicitly insufficient, never a false clean review.
    if status == 'renamed':
        with pytest.raises(ReviewError, match='insufficient_context'):
            parse_diff(raw, [dict(filename='new.py', previous_filename='old.py', status='renamed',
                                  additions=0, deletions=0)], old_revision=OLD, new_revision=HEAD)


def test_parser_handles_unicode_no_final_newline_and_reordered_files():
    raw = DIFF.replace(PATH, 'два.py') + DIFF.replace(PATH, 'one.py')
    files = [dict(FILE, filename='one.py'), dict(FILE, filename='два.py')]
    parsed, anchors = parse_diff(raw, files, old_revision=OLD, new_revision=HEAD)
    assert {x['path'] for x in parsed} == {'два.py', 'one.py'} and len(anchors) == 4
    anchors, a, d = parse_patch('@@ -1 +1 @@\n-old\n\\ No newline at end of file\n+new\n\\ No newline at end of file',
        old_path='x.py', new_path='x.py', old_revision=OLD, new_revision=HEAD)
    assert (a, d) == (1, 1)


@pytest.mark.parametrize('name', ['../secret', '/absolute', 'a\\b', '.env.example', 'x/.git/a',
                                  'build/a.py', 'x.pem', 'a\n.py', 'x//y', 'C:/x'])
def test_forbidden_paths(name):
    with pytest.raises(ReviewError):
        source_path(name)


def test_run_association_is_server_verified():
    gh = MemoryGitHub()
    assert resolve_run(gh, gh.event, reviewer_sha=REVIEWER) == (7, 100)
    assert ('GET', '/repos/owner/project/actions/runs/100') in gh.calls


@pytest.mark.parametrize('edit', [
    lambda g: g.run.update(workflow_id=99),
    lambda g: g.run.update(path='.github/workflows/other.yml'),
    lambda g: g.run.update(event='push'),
    lambda g: g.run.update(conclusion='failure'),
    lambda g: g.run.update(pull_requests=[]),
    lambda g: g.run['pull_requests'].append(deepcopy(g.run['pull_requests'][0])),
    lambda g: g.run['pull_requests'][0].update(number=8),
    lambda g: g.run['repository'].update(id=10),
    lambda g: g.run['pull_requests'][0]['head'].update(sha='e'*40),
    lambda g: g.metadata['head'].update(sha='e'*40),
    lambda g: g.run.update(head_repository=dict(id=123)),
    lambda g: g.run.update(actor=dict(login='dependabot[bot]')),
])
def test_untrusted_ambiguous_fork_or_stale_run_stops(edit):
    gh = MemoryGitHub()
    edit(gh)
    with pytest.raises(ReviewError):
        resolve_run(gh, gh.event, reviewer_sha=REVIEWER)
    assert not gh.writes


def test_paginated_data_is_not_silently_truncated():
    pages = []
    def handle(req):
        page = int(req.url.params['page'])
        pages.append(page)
        return httpx.Response(200, json=list(range(100)) if page == 1 else [100])
    gh = GitHub(REPO, client=httpx.Client(transport=httpx.MockTransport(handle)))
    assert len(gh.pages('/issues/7/comments')) == 101 and pages == [1, 2]


@pytest.mark.parametrize('mode', ['good', 'symlink', 'submodule', 'hash', 'missing', 'binary'])
def test_blob_reader_checks_tree_modes_hash_utf8_and_missing(mode):
    raw = 'привет\n'.encode() if mode != 'binary' else b'\0binary'
    blob_sha = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
    def handle(req):
        if '/git/trees/' in req.url.path:
            entry = dict(path='code.py', type='commit' if mode == 'submodule' else 'blob',
                         mode='160000' if mode == 'submodule' else '120000' if mode == 'symlink' else '100644',
                         size=len(raw), sha=blob_sha)
            return httpx.Response(200, json=dict(truncated=False, tree=[] if mode == 'missing' else [entry]))
        return httpx.Response(200, json=dict(sha=blob_sha, size=len(raw), encoding='base64',
            content=base64.b64encode(b'bad' if mode == 'hash' else raw).decode()))
    gh = GitHub(REPO, client=httpx.Client(transport=httpx.MockTransport(handle)))
    if mode == 'good':
        assert gh.file('code.py', HEAD) == 'привет\n'
    elif mode == 'missing':
        assert gh.file('code.py', HEAD, optional=True) is None
        with pytest.raises(ReviewError): gh.file('code.py', HEAD)
    else:
        with pytest.raises(ReviewError): gh.file('code.py', HEAD)


def test_http_error_redirect_and_malformed_json_are_sanitized():
    for status, content in [(403, 'secret upstream body'), (302, ''), (200, 'invalid JSON')]:
        gh = GitHub(REPO, client=httpx.Client(transport=httpx.MockTransport(
            lambda r: httpx.Response(status, text=content, headers={'location': 'https://evil.invalid'}))))
        with pytest.raises(ReviewError) as error: gh.pr(7)
        assert content not in str(error.value) or not content


def test_cli_help_needs_no_key_or_network():
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run([sys.executable, str(root/'backend/scripts/day32_review.py'), '--help'],
                            capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0 and 'local' in result.stdout and 'actions' in result.stdout
