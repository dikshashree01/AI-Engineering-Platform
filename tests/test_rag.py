"""Tests for RAG chunking and indexing (no Qdrant required)."""

from pathlib import Path

import pytest

from src.rag.chunker import chunk_incident, chunk_runbook
from src.rag.embedder import HashEmbedder, _hash_vector
from src.rag.sources import collect_chunks


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENG_DATA = PROJECT_ROOT / "engineering-data"
DOCS = PROJECT_ROOT / "docs"
GRAPH_JSON = PROJECT_ROOT / "output" / "engineering_graph.json"


def test_chunk_runbook_has_sections() -> None:
    path = ENG_DATA / "runbooks" / "checkout-latency.md"
    chunks = chunk_runbook(path, project_root=PROJECT_ROOT)
    assert len(chunks) >= 5
    assert all(c.doc_type == "runbook" for c in chunks)
    assert chunks[0].graph_node_id == "runbook:checkout-latency"
    assert "orders" in chunks[0].services
    sections = {c.section for c in chunks}
    assert "Investigation Steps" in sections or "Symptoms" in sections


def test_chunk_incident_metadata() -> None:
    path = ENG_DATA / "incidents" / "INC-001-checkout-latency.md"
    chunks = chunk_incident(path, project_root=PROJECT_ROOT)
    assert len(chunks) >= 4
    assert chunks[0].graph_node_id == "incident:INC-001"
    assert chunks[0].properties.get("severity") == "SEV-2"
    assert "front-end" in chunks[0].services
    assert "payment" in chunks[0].services


def test_collect_chunks_includes_docs_and_apis() -> None:
    if not GRAPH_JSON.exists():
        pytest.skip("engineering_graph.json not generated")
    chunks, labels = collect_chunks(
        project_root=PROJECT_ROOT,
        engineering_data_path=ENG_DATA,
        docs_path=DOCS,
        graph_json_path=GRAPH_JSON,
    )
    types = {c.doc_type for c in chunks}
    assert "runbook" in types
    assert "incident" in types
    assert "doc" in types
    assert "api" in types
    assert len(chunks) > 20
    assert any("runbook:" in label for label in labels)


def test_hash_embedder_is_deterministic() -> None:
    emb = HashEmbedder()
    a = emb.embed(["checkout latency"])[0]
    b = emb.embed(["checkout latency"])[0]
    assert a == b
    assert len(a) == emb.vector_size


def test_hash_vector_normalized() -> None:
    vec = _hash_vector("test", 384)
    norm = sum(v * v for v in vec) ** 0.5
    assert abs(norm - 1.0) < 1e-6


def test_vector_search_uses_query_points_when_available() -> None:
    from src.rag.search import _vector_search

    class FakePoint:
        def __init__(self, score: float) -> None:
            self.score = score
            self.payload = {"chunk_id": "x", "text": "t", "doc_type": "doc", "source_file": "f"}

    class FakeResponse:
        points = [FakePoint(0.9)]

    class FakeClient:
        def query_points(self, **kwargs):
            assert kwargs["collection_name"] == "test"
            assert kwargs["limit"] == 1
            return FakeResponse()

    points = _vector_search(
        FakeClient(),
        collection_name="test",
        query_vector=[0.1, 0.2],
        query_filter=None,
        limit=1,
    )
    assert len(points) == 1
    assert points[0].score == 0.9

