"""Small fixed-host REST helper. PR blobs are data, never checkout/import targets."""
import base64
import hashlib
import json
from dataclasses import dataclass
from urllib.parse import quote

import httpx

from . import (MAX_DIFF_BYTES, MAX_FILES, MAX_SOURCE_BYTES, SIGNAL_PATH, ReviewError,
               positive, repository, require, reject_secrets, sha, source_path)
from .diff import parse_diff


@dataclass
class Snapshot:
    number: int
    base: str
    head: str
    merge_base: str
    files: list
    diff: str
    changes: dict


class GitHub:
    def __init__(self, repo, token='', *, client=None):
        self.repo = repository(repo)
        self.prefix = '/repos/' + self.repo
        self.client = client or httpx.Client(base_url='https://api.github.com', timeout=30,
            follow_redirects=False, headers={'Authorization': 'Bearer ' + token} if token else {})
        self.trees = {}

    def close(self):
        self.client.close()

    def request(self, path, *, method='GET', body=None, limit=2*1024*1024,
                media='application/vnd.github+json', missing=False):
        require(path == self.prefix or path.startswith(self.prefix + '/'), reason='invalid_api_path')
        try:
            with self.client.stream(method, 'https://api.github.com' + path, json=body,
                    headers={'Accept': media, 'X-GitHub-Api-Version': '2022-11-28'}) as response:
                if missing and response.status_code == 404:
                    return None
                require(response.status_code in {200, 201}, reason='http_request_failed')
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    require(len(data) <= limit, 'too_large', 'api_response_bytes')
            return data.decode('utf-8') if media == 'application/vnd.github.diff' else json.loads(data)
        except (httpx.HTTPError, UnicodeError, ValueError):
            raise ReviewError('github_error', 'invalid_or_unavailable_response') from None

    def get(self, suffix, **kwargs):
        return self.request(self.prefix + suffix, **kwargs)

    def pages(self, suffix, *, maximum=10000):
        result = []
        for page in range(1, 102):
            batch = self.get(suffix + f'?per_page=100&page={page}')
            require(isinstance(batch, list), reason='invalid_page')
            result.extend(batch)
            require(len(result) <= maximum, 'too_large', 'pagination_limit')
            if len(batch) < 100:
                return result
        raise ReviewError('github_error', 'pagination_unfinished')

    def pr(self, number):
        require(positive(number), 'configuration_error', 'invalid_pr_number')
        p = self.get(f'/pulls/{number}')
        require(p.get('number') == number and isinstance(p.get('head'), dict)
                and isinstance(p.get('base'), dict), reason='invalid_pr')
        sha(p['head']['sha'])
        sha(p['base']['sha'])
        return p

    def eligible(self, p):
        require(p['state'] == 'open' and not p.get('merged'), 'stale', 'pr_not_open')
        require(p['base']['ref'] == 'main' and p['base']['repo']['full_name'] == self.repo,
                'skipped', 'unsupported_base')
        require(p['head'].get('repo') and p['head']['repo']['id'] == p['base']['repo']['id'],
                'skipped', 'fork_pr')
        require(p['user']['login'] != 'dependabot[bot]', 'skipped', 'dependabot')

    def current(self, snap):
        p = self.pr(snap.number)
        self.eligible(p)
        require((p['base']['sha'], p['head']['sha']) == (snap.base, snap.head), 'stale', 'pr_changed')
        return p

    def snapshot(self, number):
        p = self.pr(number)
        self.eligible(p)
        require(type(p['changed_files']) is int and 0 < p['changed_files'] <= MAX_FILES,
                'too_large', 'file_count_limit')
        files = self.pages(f'/pulls/{number}/files', maximum=MAX_FILES)
        require(len(files) == p['changed_files'], 'incomplete_diff', 'file_count_mismatch')
        for f in files:
            source_path(f['filename'])
            source_path(f.get('previous_filename', f['filename']))
            require(all(type(f.get(k)) is int and f[k] >= 0 for k in ('additions', 'deletions')),
                    'incomplete_diff', 'invalid_counts')
        require(len({f['filename'] for f in files}) == len(files), 'incomplete_diff', 'duplicate_file')
        raw = self.get(f'/pulls/{number}', media='application/vnd.github.diff', limit=MAX_DIFF_BYTES)
        reject_secrets(raw)
        merge_base = sha(self.get(f"/compare/{p['base']['sha']}...{p['head']['sha']}")['merge_base_commit']['sha'])
        parsed, changes = parse_diff(raw, files, old_revision=merge_base, new_revision=p['head']['sha'])
        snap = Snapshot(number, p['base']['sha'], p['head']['sha'], merge_base, parsed, raw, changes)
        self.current(snap)
        return snap

    def file(self, path, revision, *, optional=False):
        source_path(path)
        tree_sha = sha(revision)
        parts = path.split('/')
        for i, part in enumerate(parts):
            if tree_sha not in self.trees:
                tree = self.get('/git/trees/' + tree_sha)
                require(tree.get('truncated') is False and isinstance(tree.get('tree'), list),
                        reason='incomplete_tree')
                self.trees[tree_sha] = tree['tree']
            found = [x for x in self.trees[tree_sha] if x['path'] == part]
            if not found and optional:
                return None
            require(len(found) == 1, reason='source_missing')
            entry = found[0]
            last = i == len(parts) - 1
            require((entry['type'], entry['mode']) in ({('blob', '100644'), ('blob', '100755')}
                    if last else {('tree', '040000')}), 'unsupported_scope', 'source_not_regular')
            tree_sha = sha(entry['sha'])
        require(type(entry.get('size')) is int and 0 <= entry['size'] <= MAX_SOURCE_BYTES,
                'too_large', 'source_bytes_limit')
        blob = self.get('/git/blobs/' + tree_sha, limit=512*1024)
        require(blob.get('encoding') == 'base64' and blob.get('sha') == tree_sha,
                reason='invalid_blob')
        try:
            raw = base64.b64decode(''.join(blob['content'].split()), validate=True)
            require(len(raw) == entry['size'] and len(raw) == blob['size'], reason='blob_size_mismatch')
            identity = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
            require(identity == tree_sha, reason='blob_hash_mismatch')
            text = raw.decode('utf-8-sig').replace('\r\n', '\n').replace('\r', '\n')
        except (ValueError, UnicodeError, KeyError):
            raise ReviewError('unsupported_scope', 'non_utf8_source') from None
        require('\0' not in text, 'unsupported_scope', 'binary_source')
        reject_secrets(text)
        return text


def resolve_run(gh, event, *, reviewer_sha):
    """Use server association, never a branch-name guess or an uploaded artifact."""
    sha(reviewer_sha)
    require(event.get('action') == 'completed', reason='invalid_event')
    run_event = event.get('workflow_run', {})
    require(positive(run_event.get('id')), reason='invalid_run')
    repo = gh.get('')
    require(repo.get('full_name') == gh.repo and repo.get('default_branch') == 'main'
            and positive(repo.get('id')), reason='repository_mismatch')
    wf = gh.get('/actions/workflows/' + quote(SIGNAL_PATH.rsplit('/', 1)[-1], safe=''))
    run = gh.get('/actions/runs/' + str(run_event['id']))
    require(run.get('id') == run_event['id'] and run.get('workflow_id') == wf.get('id')
            and wf.get('path') == SIGNAL_PATH and run.get('path', '').split('@')[0] == SIGNAL_PATH
            and run.get('event') == 'pull_request' and run.get('status') == 'completed'
            and run.get('conclusion') == 'success', reason='untrusted_run')
    event_repo = event.get('repository', {})
    require(run.get('repository', {}).get('full_name') == gh.repo
            and run['repository'].get('id') == event_repo.get('id') == repo['id']
            and event_repo.get('full_name') == gh.repo and event_repo.get('default_branch') == 'main',
            reason='repository_mismatch')
    require(run.get('head_repository', {}).get('id') == event_repo.get('id'), 'skipped', 'fork_run')
    require(run.get('actor', {}).get('login') != 'dependabot[bot]' and
            run.get('triggering_actor', {}).get('login') != 'dependabot[bot]', 'skipped', 'dependabot')
    associations = run.get('pull_requests', [])
    event_prs = run_event.get('pull_requests', [])
    require(len(associations) == len(event_prs) == 1, reason='ambiguous_pr_association')
    a, e = associations[0], event_prs[0]
    require(positive(a.get('number')) and a['number'] == e.get('number')
            and a.get('id') == e.get('id') and positive(a.get('id')), reason='association_mismatch')
    head = sha(run.get('head_sha'))
    require(a['head']['sha'] == e['head']['sha'] == head
            and a['head']['repo']['id'] == a['base']['repo']['id'] == event_repo['id'],
            reason='association_head_mismatch')
    p = gh.pr(a['number'])
    gh.eligible(p)
    require(p.get('id') == a['id'] and p['base']['repo']['id'] == event_repo['id'], reason='pr_identity_mismatch')
    require(p['head']['sha'] == head, 'stale', 'run_head_changed')
    return p['number'], run['id']
