"""Text embedding providers for Qdrant indexing."""

from __future__ import annotations

import hashlib
import logging
from typing import Protocol

from src.rag.config import RagConfig

logger = logging.getLogger(__name__)

HASH_VECTOR_SIZE = 384


class Embedder(Protocol):
    vector_size: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class HashEmbedder:
    """Deterministic local embedder for tests — not for production search quality."""

    vector_size = HASH_VECTOR_SIZE

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [_hash_vector(text, self.vector_size) for text in texts]


class FastEmbedEmbedder:
    vector_size: int

    def __init__(self, model_name: str) -> None:
        try:
            from fastembed import TextEmbedding
        except ImportError as exc:
            raise ImportError(
                "fastembed not installed. Run: pip install fastembed"
            ) from exc
        self._model = TextEmbedding(model_name=model_name)
        sample = list(self._model.embed(["dimension probe"]))
        self.vector_size = len(sample[0])

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [vec.tolist() for vec in self._model.embed(texts)]


class OpenAIEmbedder:
    vector_size: int

    def __init__(self, api_key: str, model: str) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ImportError(
                "openai not installed. Run: pip install openai"
            ) from exc
        self._client = OpenAI(api_key=api_key)
        self._model = model
        probe = self.embed(["dimension probe"])
        self.vector_size = len(probe[0])

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self._client.embeddings.create(model=self._model, input=texts)
        ordered = sorted(response.data, key=lambda item: item.index)
        return [item.embedding for item in ordered]


def create_embedder(config: RagConfig) -> Embedder:
    provider = config.embedding_provider.lower()
    if provider == "openai":
        if not config.openai_api_key:
            raise ValueError(
                "EMBEDDING_PROVIDER=openai requires OPENAI_API_KEY"
            )
        return OpenAIEmbedder(config.openai_api_key, config.openai_embedding_model)
    if provider == "fastembed":
        return FastEmbedEmbedder(config.fastembed_model)
    if provider == "hash":
        return HashEmbedder()
    raise ValueError(
        f"Unknown EMBEDDING_PROVIDER: {config.embedding_provider}. "
        "Use fastembed, openai, or hash."
    )


def _hash_vector(text: str, size: int) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values: list[float] = []
    while len(values) < size:
        for byte in digest:
            values.append((byte / 127.5) - 1.0)
            if len(values) >= size:
                break
        digest = hashlib.sha256(digest).digest()
    norm = sum(v * v for v in values) ** 0.5 or 1.0
    return [v / norm for v in values]
