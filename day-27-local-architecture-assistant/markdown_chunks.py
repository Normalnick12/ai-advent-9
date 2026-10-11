"""Source-slice Markdown helpers adapted from Week 5 structure.py/chunking.py.

Unlike the original, budgets are characters and even short documents have sections.
"""
import re
from knowledge import canonical, digest

LIMIT, OVERLAP = 1800, 180
PROFILE = {"version": "markdown-slices-v2", "limit": LIMIT, "overlap": OVERLAP,
           "normalization": "utf-8-sig;LF", "headings": "ATX"}
MAX_CHUNKS = 4096
FENCE = re.compile(r"^ {0,3}(" + chr(96) + r"{3,}|~{3,})(.*)$")
HEADING = re.compile(r"^ {0,3}(#{1,6})\s+(.+?)\s*#*\s*$")


def lines(text):
    offset = 0
    for line in text.split("\n"):
        end = min(len(text), offset + len(line) + 1)
        if offset < end:
            yield offset, end, line
        offset = end


def headings(text):
    found, fence = [], None
    for start, end, line in lines(text):
        marker = FENCE.match(line)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= fence[1] and not marker[2].strip():
                fence = None
        elif marker:
            fence = marker[1][0], len(marker[1])
        else:
            h = HEADING.match(line)
            if h:
                found.append((start, len(h[1]), h[2]))
    return found


def paragraphs(text, start, end):
    block, fence = start, None
    for a, b, line in lines(text[start:end]):
        marker = FENCE.match(line)
        if marker:
            if fence is None:
                fence = marker[1][0], len(marker[1])
            elif marker[1][0] == fence[0] and len(marker[1]) >= fence[1] and not marker[2].strip():
                fence = None
        if not fence and not line.strip():
            yield block, start + b
            block = start + b
    if block < end:
        yield block, end


def chunks_for(name, text):
    marks = headings(text)
    sections, stack = [], []
    if not marks or marks[0][0] > 0:
        sections.append((0, name))
    for pos, level, title in marks:
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
        sections.append((pos, " / ".join(t for _, t in stack)))
    result = []

    def add(a, b, section, reason):
        chunk = text[a:b]
        if not chunk.strip():
            return
        result.append({
            "chunk_id": digest(canonical([name, digest(text), PROFILE, a, b])),
            "source": name, "section": section, "ordinal": len(result),
            "start_char": a, "end_char": b,
            "start_line": text.count("\n", 0, a) + 1,
            "end_line": text.count("\n", 0, b - 1) + 1,
            "text": chunk, "text_hash": digest(chunk), "split_reason": reason,
        })

    for i, (start, section) in enumerate(sections):
        end = sections[i + 1][0] if i + 1 < len(sections) else len(text)
        pending = None
        last = start
        for a, b in paragraphs(text, start, end):
            if pending is not None and b - pending > LIMIT:
                add(pending, a, section, "boundary")
                pending = None
            if b - a > LIMIT:
                pos = a
                while pos < b:
                    stop = min(pos + LIMIT, b)
                    add(pos, stop, section, "oversized_fallback")
                    if stop == b:
                        break
                    pos = stop - OVERLAP
            elif pending is None:
                pending = a
            last = b
        if pending is not None:
            add(pending, last, section, "boundary")
    return result


def chunk_snapshot(snapshot):
    result = []
    for name, text in sorted(snapshot.sources.items()):
        result.extend(chunks_for(name, text))
        if len(result) > MAX_CHUNKS:
            raise ValueError("Превышен лимит chunks.")
    if not result:
        raise ValueError("Knowledge не содержит непустого Markdown.")
    return result
