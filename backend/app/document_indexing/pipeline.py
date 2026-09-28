from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from .chunking import STRATEGIES
from .embedding import EMBEDDING_CONFIG, Embedder, validate_vectors
from .report import prepare
from .storage import DATABASE, save


def build(snapshot, embedder: Embedder, path=DATABASE, progress=lambda message: None):
    data = prepare(snapshot)
    data["config"]["embedding"] = dict(EMBEDDING_CONFIG)
    data["run_id"] = str(uuid4())
    data["created_at"] = datetime.now(timezone.utc).isoformat()
    observations = data["observations"]
    observations["embedding"] = {}
    for strategy in STRATEGIES:
        chunks = data["chunks"][strategy]
        if not chunks:
            raise ValueError("Cannot build an empty index")
        calls, usage = 0, 0
        started = perf_counter()
        for offset in range(0, len(chunks), 32):
            batch = chunks[offset:offset + 32]
            calls += 1
            progress(f"{strategy}: embedding call {calls}, chunks {offset + 1}-{offset + len(batch)}/{len(chunks)}")
            response = embedder.embed([c["text"] for c in batch])
            validate_vectors(response.vectors, len(batch))
            usage = usage + response.usage if usage is not None and response.usage is not None else None
            for chunk, vector in zip(batch, response.vectors, strict=True):
                chunk["embedding"] = vector
        observations["embedding"][strategy] = {"calls": calls, "provider_tokens": usage,
                                               "seconds": perf_counter() - started}
    # No database publication until both strategies have all their vectors.
    save(data, path)
    data["observations"]["sqlite_bytes_at_read"] = path.stat().st_size
    return data
