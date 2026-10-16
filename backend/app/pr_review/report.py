"""Render only authoritative links and publish through the single CI writer."""
import html
import json
import re
from urllib.parse import quote

from . import VERSION, ReviewError, positive, require

MARKER = '<!-- day32-review:'


def escape(value):
    value = ''.join(c for c in str(value) if ord(c) >= 32 or c in '\n\t')
    value = value.replace('@', '@\u200b')
    return re.sub(r'([\\`*_[\]{}()!|>#~:])', r'\\\1', html.escape(value, quote=True))


def link(repo, item):
    url = f"https://github.com/{repo}/blob/{item['revision']}/{quote(item['path'], safe='/')}"
    url += f"#L{item['start_line']}-L{item['end_line']}"
    return f"[{escape(item['path'])}:{item['start_line']}-{item['end_line']}]({url})"


def render(repo, number, result, *, snap=None, context=None, usage=None, reviewer_sha='', run_id=None):
    context, usage = context or {}, usage or {}
    lines = [f'## Day 32 — PR #{number}', '', '**Статус:** ' + escape(result['status']),
             escape(result.get('reason', result.get('summary', '')))]
    if snap:
        lines += ['', f'Head: `{snap.head}`', f'Base: `{snap.base}`']
    if reviewer_sha:
        lines += [f'Reviewer: `{reviewer_sha}` / `{VERSION}`']
    if run_id:
        lines += [f'[Actions run](https://github.com/{repo}/actions/runs/{run_id})']
    findings = result.get('findings', [])
    for category, title in [('bug', 'Потенциальные баги'), ('architecture', 'Архитектурные проблемы'),
                            ('recommendation', 'Рекомендации')]:
        lines += ['', '### ' + title]
        selected = [f for f in findings if f['category'] == category]
        if not selected:
            lines += ['Нет замечаний в этой категории.' if result['status'] == 'reviewed' else 'Анализ не завершён.']
        for f in selected:
            anchor = snap.changes[f['change_id']]
            lines += ['', f"**{escape(f['severity'])}: {escape(f['title'])}** — {link(repo, anchor)}",
                      escape(f['explanation']), '', 'Рекомендация: ' + escape(f['recommendation']),
                      '', '> ' + escape(anchor['text'][:400]).replace('\n', '\n> ')]
            if f['context_ids']:
                lines += ['Основания: ' + ', '.join(f['context_ids']) + ' (цитаты ниже).']
    lines += ['', '### Контекст и ограничения']
    for group, chunks in context.items():
        for c in chunks:
            lines += [f"- {escape(group)} {c['id']}: {link(repo, c)} (`{c['revision'][:12]}`)"]
            lines += ['> ' + escape(c['text'][:500]).replace('\n', '\n> ')]
    for limitation in result.get('limitations', []):
        lines += ['- ' + escape(limitation)]
    lines += ['', 'Advisory: ссылки проверены программно; смысл замечаний требует оценки человеком. '
              'Отсутствие замечаний не доказывает отсутствие ошибок.']
    lines += ['', '<details><summary>Диагностика</summary>', '',
              '```json', json.dumps(usage, ensure_ascii=True, indent=2), '```', '</details>']
    text = '\n'.join(lines)
    require(len(text) <= 60000, 'publication_error', 'comment_length_limit')
    return text


def summary(repo, number, result, *, snap=None, context=None, usage=None, reviewer_sha='',
            run_id=None, comment_id=None):
    lines = [f'## Day 32 — PR #{number}', '', '**Статус:** ' + escape(result['status']),
             escape(result.get('reason', result.get('summary', '')))]
    if snap:
        lines += ['', f'Head: `{snap.head}`', f'Base: `{snap.base}`']
    if reviewer_sha:
        lines += [f'Reviewer: `{reviewer_sha}` / `{VERSION}`']
    if run_id:
        lines += [f'[Actions run](https://github.com/{repo}/actions/runs/{run_id})']
    if comment_id:
        lines += [f'[Полный отчёт в PR](https://github.com/{repo}/pull/{number}#issuecomment-{comment_id})']
    counts = {k: sum(f['category'] == k for f in result.get('findings', []))
              for k in ('bug', 'architecture', 'recommendation')}
    lines += ['', 'Findings: ' + ', '.join(f'{k}={v}' for k, v in counts.items()), '', 'RAG:']
    for group, chunks in (context or {}).items():
        for c in chunks:
            lines += [f"- {escape(group)} {c['id']}: {link(repo, c)} (`{c['revision'][:12]}`)"]
    lines += ['', '```json', json.dumps(usage or {}, ensure_ascii=True), '```', '',
              'Advisory: отсутствие замечаний не доказывает отсутствие ошибок.']
    return '\n'.join(lines)


def existing_comment(gh, number):
    matches = []
    for c in gh.pages(f'/issues/{number}/comments'):
        user, body = c.get('user', {}), c.get('body', '')
        if user.get('login') != 'github-actions[bot]' or user.get('type') != 'Bot' or not body.startswith(MARKER):
            continue
        try:
            end = body.index('-->')
            meta = json.loads(body[len(MARKER):end])
            require(meta['repository'] == gh.repo and meta['pr'] == number and positive(meta['source_run']),
                    'publication_error', 'invalid_comment_metadata')
        except (ValueError, KeyError, TypeError):
            raise ReviewError('publication_error', 'invalid_comment_metadata') from None
        matches.append((c, meta))
    require(len(matches) <= 1, 'publication_error', 'ambiguous_bot_comment')
    return matches[0] if matches else (None, None)


def publish(gh, snap, text, *, source_run, reviewer_sha):
    require(positive(source_run), 'publication_error', 'invalid_source_run')
    old, previous = existing_comment(gh, snap.number)
    require(not previous or previous['source_run'] <= source_run, 'superseded', 'newer_report_exists')
    # Called only by the workflow with the shared per-PR concurrency group.
    gh.current(snap)
    meta = dict(repository=gh.repo, pr=snap.number, source_run=source_run,
                head=snap.head, base=snap.base, reviewer=reviewer_sha, version=VERSION)
    body = MARKER + json.dumps(meta, separators=(',', ':')) + '-->\n' + text
    try:
        response = gh.get(f"/issues/comments/{old['id']}" if old else f'/issues/{snap.number}/comments',
                          method='PATCH' if old else 'POST', body={'body': body})
        require(positive(response.get('id')), 'publication_error', 'invalid_comment_response')
    except ReviewError as error:
        if error.status in {'github_error', 'too_large'}:
            raise ReviewError('publication_error', 'comment_write_failed') from None
        raise
    gh.current(snap)  # A race after the pre-write check is visible in Summary as stale.
    return response['id']
