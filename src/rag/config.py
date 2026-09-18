"""RAG and Qdrant settings from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class RagConfig:
    qdrant_url: str
    qdrant_api_key: str | None
    collection_name: str
    embedding_provider: str
    openai_api_key: str | None
    openai_embedding_model: str
    fastembed_model: str
    engineering_data_path: str
    docs_path: str
    graph_json_path: str

    @classmethod
    def from_env(cls) -> RagConfig:
        return cls(
            qdrant_url=os.getenv("QDRANT_URL", "http://localhost:6333"),
            qdrant_api_key=os.getenv("QDRANT_API_KEY") or None,
            collection_name=os.getenv("QDRANT_COLLECTION", "engineering_rag"),
            embedding_provider=os.getenv("EMBEDDING_PROVIDER", "fastembed"),
            openai_api_key=os.getenv("OPENAI_API_KEY") or None,
            openai_embedding_model=os.getenv(
                "OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"
            ),
            fastembed_model=os.getenv(
                "FASTEMBED_MODEL", "BAAI/bge-small-en-v1.5"
            ),
            engineering_data_path=os.getenv(
                "ENGINEERING_DATA_PATH", "./engineering-data"
            ),
            docs_path=os.getenv("DOCS_PATH", "./docs"),
            graph_json_path=os.getenv(
                "GRAPH_JSON_PATH", "./output/engineering_graph.json"
            ),
        )
