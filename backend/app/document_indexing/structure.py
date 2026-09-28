"""Source ranges only: Markdown headings, Python AST, Kotlin formatting."""
import ast
import re
from pathlib import PurePosixPath

from .chunking import LIMIT, token_count, windows


def line_offsets(text):
    offsets = [0]
    for line in text.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line))
    return offsets


def headings(text):
    result, fence, offset = [], None, 0
    for line in text.splitlines(keepends=True):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line.rstrip("\r\n"))
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= fence[1] and not marker[2].strip():
                fence = None
        elif marker:
            fence = (marker[1][0], len(marker[1]))
        else:
            heading = re.match(r"^ {0,3}(#{1,6})\s+(.+?)\s*#*\s*$", line)
            if heading:
                result.append((offset, len(heading[1]), heading[2]))
        offset += len(line)
    return result


def paragraph_spans(text, start, end, *, markdown=False):
    """Blank lines split formatting; fenced Markdown code stays one block."""
    cursor = block = start
    fence = None
    for line in text[start:end].splitlines(keepends=True):
        if markdown:
            marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line.rstrip("\r\n"))
            if marker:
                if fence is None:
                    fence = (marker[1][0], len(marker[1]))
                elif marker[1][0] == fence[0] and len(marker[1]) >= fence[1] and not marker[2].strip():
                    fence = None
        cursor += len(line)
        if not fence and not line.strip():
            yield block, cursor
            block = cursor
    if block < end:
        yield block, end


def pack(text, spans, section):
    pending = None
    for start, end in spans:
        if pending is not None and token_count(text[pending:end]) > LIMIT:
            yield pending, start, section, "structural_boundary"
            pending = None
        if token_count(text[start:end]) > LIMIT:
            for a, b in windows(text, start, end):
                yield a, b, section, "oversized_fallback"
        elif pending is None:
            pending = start
        last = end
    if pending is not None:
        yield pending, last, section, "structural_boundary"


def markdown_spans(text, filename):
    marks = headings(text)

    def divide(start, end, section, children):
        if token_count(text[start:end]) <= LIMIT:
            yield start, end, section, "structural_boundary"
        elif children:
            level = min(h[1] for h in children)
            siblings = [h for h in children if h[1] == level]
            if start < siblings[0][0]:
                yield from pack(text, paragraph_spans(text, start, siblings[0][0], markdown=True), section)
            for i, (pos, _, title) in enumerate(siblings):
                stop = siblings[i + 1][0] if i + 1 < len(siblings) else end
                nested = [h for h in children if pos < h[0] < stop]
                yield from divide(pos, stop, f"{section} / {title}", nested)
        else:
            yield from pack(text, paragraph_spans(text, start, end, markdown=True), section)

    yield from divide(0, len(text), filename, marks)


def python_nodes(text):
    offsets = line_offsets(text)

    def visit(nodes, parent=""):
        for node in nodes:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                name = f"{parent}.{node.name}" if parent else node.name
                first = min([node.lineno] + [d.lineno for d in node.decorator_list])
                yield node, name, offsets[first - 1], offsets[node.end_lineno]
                if isinstance(node, ast.ClassDef):
                    yield from visit(node.body, name)

    return list(visit(ast.parse(text).body))


def python_spans(text, filename):
    try:
        nodes = python_nodes(text)
    except SyntaxError:
        for a, b in windows(text):
            yield a, b, filename, "parse_fallback"
        return

    def divide(start, end, parent):
        immediate = [n for n in nodes if n[1].rpartition(".")[0] == parent]
        cursor = start
        for node, name, a, b in immediate:
            if cursor < a:
                yield from fit(cursor, a, parent or filename)
            if isinstance(node, ast.ClassDef) and token_count(text[a:b]) > LIMIT:
                yield from divide(a, b, name)
            else:
                yield from fit(a, b, name)
            cursor = b
        if cursor < end:
            yield from fit(cursor, end, parent or filename)

    def fit(a, b, section):
        if token_count(text[a:b]) <= LIMIT:
            yield a, b, section, "structural_boundary"
        else:
            for x, y in windows(text, a, b):
                yield x, y, section, "oversized_fallback"

    yield from divide(0, len(text), "")


def structural_spans(source):
    suffix = PurePosixPath(source.source).suffix
    if suffix == ".md":
        yield from markdown_spans(source.text, source.title)
    elif suffix == ".py":
        yield from python_spans(source.text, source.title)
    else:
        yield from pack(source.text, paragraph_spans(source.text, 0, len(source.text)), source.title + " / formatting")
