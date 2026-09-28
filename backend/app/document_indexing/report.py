import json
import statistics
from dataclasses import asdict
from time import perf_counter

from .chunking import STRATEGIES, chunk_source, config
from .structure import headings, line_offsets, python_nodes


def locations(snapshot):
    sources = {s.source: s for s in snapshot.sources}
    result = []
    seen = set()
    for location in snapshot.manifest.get("locations", []):
        if location["id"] in seen:
            raise ValueError("Duplicate representative ID")
        seen.add(location["id"])
        source = sources[location["source"]]
        text, anchor, kind = source.text, location["anchor"], location["kind"]
        if kind == "python":
            found = [(a, b) for _, name, a, b in python_nodes(text) if name == anchor]
        else:
            lines, offsets = text.splitlines(), line_offsets(text)
            indexes = [i for i, line in enumerate(lines) if line == anchor]
            found = []
            for i in indexes:
                if kind == "line":
                    found.append((offsets[max(0, i - 3)], offsets[min(len(lines), i + 13)]))
                elif kind == "heading":
                    marks = headings(text)
                    level = next((level for pos, level, _ in marks if pos == offsets[i]), None)
                    if level is not None:
                        stop = next((pos for pos, depth, _ in marks if pos > offsets[i] and depth <= level), len(text))
                        found.append((offsets[i], stop))
                else:
                    raise ValueError("Invalid representative kind")
        if len(found) != 1:
            raise ValueError(f"Missing/ambiguous representative: {location['id']}")
        a, b = found[0]
        result.append({**location, "start_char": a, "end_char": b})
    return result


def prepare(snapshot):
    selected = locations(snapshot)  # Resolve before either strategy runs.
    chunks, timings = {}, {}
    for strategy in STRATEGIES:
        started = perf_counter()
        chunks[strategy] = [c for s in snapshot.sources for c in chunk_source(s, strategy)]
        timings[strategy] = perf_counter() - started
    return {"corpus_hash": snapshot.corpus_hash, "manifest": snapshot.manifest,
            "config": config(), "locations": selected,
            "sources": [{**asdict(s), "source_hash": s.source_hash} for s in snapshot.sources],
            "chunks": chunks, "observations": {"chunking_seconds": timings}}


def metrics(chunks):
    counts = [c["token_count"] for c in chunks]
    return {"chunks": len(counts), "min": min(counts, default=0),
            "median": statistics.median(counts) if counts else 0, "max": max(counts, default=0),
            "total_tokens": sum(counts),
            "fallbacks": sum(c["split_reason"].endswith("fallback") for c in chunks)}


def comparison(data, *, persisted=False):
    if set(data["chunks"]) != set(STRATEGIES):
        raise ValueError("Incomplete strategy pair")
    rows = [f"Corpus snapshot: {data['corpus_hash']}",
            "Token limit: 500; target overlap: 50 (structure-aware: fallback only)",
            "strategy           chunks  min  median  max  " + ("embedded" if persisted else "planned") + " tokens  fallback"]
    for strategy in STRATEGIES:
        m = metrics(data["chunks"][strategy])
        rows.append(f"{strategy:18} {m['chunks']:6} {m['min']:4} {m['median']:7g} {m['max']:4} {m['total_tokens']:16} {m['fallbacks']:9}")
    rows.append("structure-aware = structure-aware deterministic chunking; retrieval quality NOT TESTED.")
    if persisted:
        rows.append(f"Embedding config: {data['config']['embedding']}")
        rows.append(f"Run observations (not strategy quality/performance evidence): {data['observations']}")
    return "\n".join(rows)


def display_chunk(chunk, *, full_vector=False):
    metadata = {k: v for k, v in chunk.items() if k not in {"text", "embedding"}}
    lines = [json.dumps(metadata, ensure_ascii=False, indent=2), "--- chunk text ---", chunk["text"], "--- end chunk ---"]
    if "embedding" in chunk:
        vector = chunk["embedding"]
        lines.append(f"Embedding dimension={len(vector)}; " + str(vector if full_vector else vector[:6]))
    return "\n".join(lines)


def examples(data, selection=None, *, full_vector=False):
    selected = [p for p in data["locations"] if selection is None or p["id"] == selection]
    if not selected:
        raise ValueError("Unknown representative location")
    sources = {s["source"]: s["text"] for s in data["sources"]}
    output = []
    for place in selected:
        text = sources[place["source"]]
        a, b = place["start_char"], place["end_char"]
        line = text.count("\n", 0, a) + 1
        output.extend([f"\n=== {place['id']}: {place['source']} ===", "SOURCE LOCATION:"])
        output.extend(f"{i:4} | {s}" for i, s in enumerate(text[a:b].splitlines(), line))
        for strategy in STRATEGIES:
            name = "structure-aware deterministic chunking" if strategy == "structure-aware" else strategy
            output.append(f"\n{name}:")
            for chunk in data["chunks"][strategy]:
                if chunk["source"] == place["source"] and chunk["start_char"] < b and chunk["end_char"] > a:
                    output.append(display_chunk(chunk, full_vector=full_vector))
    return "\n".join(output)
