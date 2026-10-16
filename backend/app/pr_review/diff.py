"""Parse complete unified hunks and derive authoritative changed-line anchors."""
import re

from . import MAX_LINES, ReviewError, require, source_path

HUNK = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?:.*)$')


def parse_patch(patch, *, old_path, new_path, old_revision, new_revision, start_id=1):
    require(isinstance(patch, str), 'incomplete_diff', 'missing_patch')
    anchors, consumed, added, deleted = {}, False, 0, 0
    old = new = left_old = left_new = 0
    for line in patch.splitlines():
        match = HUNK.fullmatch(line)
        if match:
            require(left_old == left_new == 0, 'incomplete_diff', 'truncated_hunk')
            old, left_old, new, left_new = (int(match[1]), int(match[2] or 1),
                                           int(match[3]), int(match[4] or 1))
            consumed = True
            continue
        if line == '\\ No newline at end of file':
            require(consumed, 'incomplete_diff', 'invalid_newline_marker')
            continue
        require(consumed and line and line[0] in ' +-','incomplete_diff', 'invalid_hunk')
        prefix, text = line[0], line[1:]
        if prefix == ' ':
            left_old -= 1
            left_new -= 1
            old += 1
            new += 1
        else:
            is_new = prefix == '+'
            number = new if is_new else old
            require(number > 0, 'incomplete_diff', 'invalid_changed_line')
            cid = 'D' + str(start_id + len(anchors))
            anchors[cid] = dict(id=cid, path=new_path if is_new else old_path,
                revision=new_revision if is_new else old_revision, side='new' if is_new else 'old',
                start_line=number, end_line=number, text=text)
            if is_new:
                left_new -= 1
                new += 1
                added += 1
            else:
                left_old -= 1
                old += 1
                deleted += 1
        require(left_old >= 0 and left_new >= 0, 'incomplete_diff', 'hunk_overflow')
        require(added + deleted <= MAX_LINES, 'too_large', 'changed_lines_limit')
    require(left_old == left_new == 0, 'incomplete_diff', 'truncated_hunk')
    return anchors, added, deleted


def parse_diff(raw, files, *, old_revision, new_revision):
    require(raw.startswith('diff --git '), 'incomplete_diff', 'missing_diff')
    sections = re.split(r'(?m)^diff --git ', raw)[1:]
    require(len(sections) == len(files), 'incomplete_diff', 'file_count_mismatch')
    changes, result = {}, []
    # GitHub /files ordering is not a contract: match sections by trusted metadata paths.
    unmatched = {f['filename']: f for f in files}
    for section in sections:
        lines = section.splitlines()
        require(lines, 'incomplete_diff', 'empty_section')
        candidates = []
        for path, f in unmatched.items():
            old_path = f.get('previous_filename', path)
            # Quoted/escaped git paths are refused rather than guessed.
            if lines[0] == f'a/{old_path} b/{path}':
                candidates.append(f)
        require(len(candidates) == 1, 'unsupported_scope', 'unsupported_diff_path')
        f = candidates[0]
        name = source_path(f['filename'])
        old_name = source_path(f.get('previous_filename', name))
        unmatched.pop(name)
        status = f['status']
        require(status in {'added', 'removed', 'modified', 'renamed'}, 'unsupported_scope', 'file_status')
        require(not any(l.startswith(('Binary files ', 'GIT binary patch', 'Submodule ')) for l in lines),
                'unsupported_scope', 'binary_or_submodule')
        require(not any(l.endswith(('120000', '160000')) and
                        l.startswith(('index ', 'old mode ', 'new mode ', 'new file mode ', 'deleted file mode '))
                        for l in lines),
                'unsupported_scope', 'symlink_or_submodule')
        first = next((i for i, l in enumerate(lines) if HUNK.fullmatch(l)), len(lines))
        headers = lines[1:first]
        expected_old = '/dev/null' if status == 'added' else 'a/' + old_name
        expected_new = '/dev/null' if status == 'removed' else 'b/' + name
        if first < len(lines):
            require('--- ' + expected_old in headers and '+++ ' + expected_new in headers,
                    'incomplete_diff', 'file_header_mismatch')
        else:
            require(status == 'renamed' and f['additions'] == f['deletions'] == 0
                    and 'rename from ' + old_name in headers and 'rename to ' + name in headers,
                    'incomplete_diff', 'missing_hunks')
        anchors, adds, dels = parse_patch('\n'.join(lines[first:]), old_path=old_name,
            new_path=name, old_revision=old_revision, new_revision=new_revision, start_id=len(changes)+1)
        require(adds == f['additions'] and dels == f['deletions'], 'incomplete_diff', 'line_count_mismatch')
        changes.update(anchors)
        result.append(dict(path=name, old_path=old_name, status=status, patch='\n'.join(lines[first:])))
    require(bool(changes), 'insufficient_context', 'no_changed_text_lines')
    require(len(changes) <= MAX_LINES, 'too_large', 'changed_lines_limit')
    return result, changes
