"""Pydantic models for RAG document chunks."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DocumentChunk(BaseModel):
    """A searchable text chunk with graph-linking metadata."""

    chunk_id: str
    text: str
    doc_type: str  # runbook | incident | doc | api
    source_file: str
    section: str | None = None
    graph_node_id: str | None = None
    services: list[str] = Field(default_factory=list)
    title: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "doc_type": self.doc_type,
            "source_file": self.source_file,
            "section": self.section,
            "graph_node_id": self.graph_node_id,
            "services": self.services,
            "title": self.title,
            **self.properties,
        }


class IndexResult(BaseModel):
    chunks_indexed: int
    collection: str
    sources: list[str]
    embedding_provider: str
    vector_size: int


class SearchHit(BaseModel):
    score: float
    chunk: DocumentChunk
