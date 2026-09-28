from dataclasses import dataclass
from typing import Protocol


MODEL = "text-embedding-3-small"
DIMENSION = 1536
EMBEDDING_CONFIG = {"provider": "openai", "model": MODEL, "dimension": DIMENSION, "encoding_format": "float"}


@dataclass
class Embeddings:
    vectors: list[list[float]]
    usage: int | None


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> Embeddings: ...


def validate_vectors(vectors, expected):
    if len(vectors) != expected or any(len(v) != DIMENSION for v in vectors):
        raise ValueError("Embedding count/dimension mismatch; build not saved")


class OpenAIEmbedder:
    def __init__(self, client=None):
        if client is None:
            from openai import OpenAI
            client = OpenAI(timeout=60.0, max_retries=0)
        self.client = client

    def embed(self, texts):
        from openai import OpenAIError
        try:
            response = self.client.embeddings.create(model=MODEL, dimensions=DIMENSION,
                                                     encoding_format="float", input=texts)
        except OpenAIError as error:
            # Never echo upstream bodies or credentials into CLI output.
            raise ValueError(f"Embedding request failed: {type(error).__name__}; build not saved") from None
        items = sorted(response.data, key=lambda item: item.index)
        if [item.index for item in items] != list(range(len(texts))):
            raise ValueError("Embedding response indexes mismatch; build not saved")
        vectors = [item.embedding for item in items]
        validate_vectors(vectors, len(texts))
        return Embeddings(vectors, getattr(response.usage, "total_tokens", None))

    def close(self):
        self.client.close()
