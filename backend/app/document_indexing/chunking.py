from functools import lru_cache
from importlib.metadata import version
from pathlib import PurePosixPath

from .corpus import Source, canonical, digest

LIMIT = 500
OVERLAP = 50
STRATEGIES = ("fixed-size", "structure-aware")


@lru_cache(maxsize=1)
def encoding():
    import tiktoken
    return tiktoken.get_encoding("cl100k_base")


def token_count(text: str) -> int:
    return len(encoding().encode_ordinary(text))


def config():
    return {"tokenizer": "cl100k_base", "tiktoken_version": version("tiktoken"),
            "max_tokens": LIMIT, "overlap_tokens": OVERLAP, "algorithm": "source-slices-v1",
            "normalization": "utf-8-sig; universal-newlines; no-strip"}


def fitting_length(length, candidate, budget):
    """Keep a measured valid slice; no claim that BPE counts are monotonic."""
    good, probe = 0, min(256, length)
    while probe and token_count(candidate(probe)) <= budget:
        good = probe
        if probe == length:
            return good
        probe = min(length, probe * 2)
    bad = probe
    while good + 1 < bad:
        middle = (good + bad) // 2
        if token_count(candidate(middle)) <= budget:
            good = middle
        else:
            bad = middle
    return good


def windows(text: str, start=0, end=None):
    end = len(text) if end is None else end
    while start < end:
        length = fitting_length(end - start, lambda n: text[start:start + n], LIMIT)
        if length == 0:
            raise ValueError("Cannot fit a source character in token budget")
        stop = start + length
        assert token_count(text[start:stop]) <= LIMIT
        if text[start:stop].strip():
            yield start, stop
        if stop == end:
            break
        overlap = fitting_length(length - 1, lambda n: text[stop - n:stop], OVERLAP)
        start = stop - overlap


def chunk_source(source: Source, strategy: str) -> list[dict]:
    from .structure import headings, structural_spans
    if strategy not in STRATEGIES:
        raise ValueError("Unknown strategy")
    spans = ((a, b, source.title, "token_window") for a, b in windows(source.text)) if strategy == "fixed-size" else structural_spans(source)
    title = source.title
    if PurePosixPath(source.source).suffix == ".md":
        found = headings(source.text)
        if found:
            title = found[0][2]
    chunks = []
    for start, end, section, reason in spans:
        text = source.text[start:end]
        if not text.strip():
            continue
        identity = [source.source, source.source_hash, strategy, config(), start, end]
        chunks.append({"chunk_id": digest(canonical(identity)), "source": source.source,
                       "source_type": source.source_type, "title": title, "section": section,
                       "strategy": strategy, "ordinal": len(chunks),
                       "start_line": source.text.count("\n", 0, start) + 1,
                       "end_line": source.text.count("\n", 0, end - 1) + 1,
                       "start_char": start, "end_char": end,
                       "token_count": token_count(text), "text_hash": digest(text),
                       "split_reason": reason, "text": text})
    return chunks
