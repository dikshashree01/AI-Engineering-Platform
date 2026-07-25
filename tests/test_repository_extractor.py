"""Tests for repository metadata extraction."""

from pathlib import Path

import pytest

from src.ingestion.extractors.repository import (
    analyze_repository,
    infer_service_name,
    parse_repositories,
)
from src.ingestion.models import EdgeType, NodeType, repository_id, service_id


@pytest.fixture
def java_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "orders"
    repo.mkdir()
    (repo / "pom.xml").write_text("<project></project>")
    (repo / "README.md").write_text("# Orders")
    (repo / "Dockerfile").write_text("FROM openjdk")
    test_dir = repo / "src" / "test" / "java"
    test_dir.mkdir(parents=True)
    (test_dir / "SampleTest.java").write_text("class SampleTest {}")
    return repo


@pytest.fixture
def go_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "payment"
    repo.mkdir()
    (repo / "service.go").write_text("package payment")
    (repo / "service_test.go").write_text("package payment")
    (repo / "README.md").write_text("# Payment")
    docker_dir = repo / "docker" / "payment"
    docker_dir.mkdir(parents=True)
    (docker_dir / "Dockerfile").write_text("FROM golang")
    return repo


@pytest.fixture
def node_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "front-end"
    repo.mkdir()
    (repo / "package.json").write_text("{}")
    (repo / "server.js").write_text("console.log('ok')")
    test_dir = repo / "test"
    test_dir.mkdir()
    (test_dir / "app_test.js").write_text("test()")
    return repo


def test_analyze_java_repository(java_repo: Path, tmp_path: Path) -> None:
    meta = analyze_repository(java_repo, project_root=tmp_path)
    assert meta is not None
    assert meta.name == "orders"
    assert meta.primary_language == "Java"
    assert meta.build_system == "Maven"
    assert meta.has_dockerfile is True
    assert meta.has_readme is True
    assert meta.has_tests is True


def test_analyze_go_repository(go_repo: Path, tmp_path: Path) -> None:
    meta = analyze_repository(go_repo, project_root=tmp_path)
    assert meta is not None
    assert meta.name == "payment"
    assert meta.primary_language == "Go"
    assert meta.has_dockerfile is True
    assert meta.has_tests is True


def test_analyze_node_repository(node_repo: Path, tmp_path: Path) -> None:
    meta = analyze_repository(node_repo, project_root=tmp_path)
    assert meta is not None
    assert meta.primary_language == "JavaScript"
    assert meta.build_system == "npm"
    assert meta.has_tests is True


def test_parse_repositories_emits_nodes_and_edges(
    java_repo: Path, go_repo: Path, node_repo: Path, tmp_path: Path
) -> None:
    services_root = tmp_path
    export = parse_repositories(services_root=services_root, project_root=tmp_path)

    assert export.stats()["nodes_Repository"] == 3
    assert export.stats()["edges_CONTAINS"] == 3

    repo_ids = {n.id for n in export.nodes if n.type == NodeType.REPOSITORY}
    assert repository_id("orders") in repo_ids
    assert repository_id("payment") in repo_ids
    assert repository_id("front-end") in repo_ids

    contains = [e for e in export.edges if e.type == EdgeType.CONTAINS]
    assert any(
        e.from_id == repository_id("orders") and e.to_id == service_id("orders")
        for e in contains
    )


def test_parse_repositories_missing_root(tmp_path: Path) -> None:
    export = parse_repositories(
        services_root=tmp_path / "does-not-exist",
        project_root=tmp_path,
    )
    assert export.nodes == []
    assert export.edges == []


def test_infer_service_name_matches_repo() -> None:
    assert infer_service_name("front-end") == "front-end"
    assert infer_service_name("orders") == "orders"


@pytest.mark.integration
def test_parse_real_sock_shop_services() -> None:
    """Run against cloned Sock Shop repos when present locally."""
    services_root = Path("source-repo/services")
    if not services_root.exists():
        pytest.skip("source-repo/services not cloned")

    export = parse_repositories(services_root=services_root)
    names = {n.name for n in export.nodes if n.type == NodeType.REPOSITORY}

    assert "orders" in names
    assert "carts" in names
    assert "catalogue" in names
    assert "payment" in names
    assert "front-end" in names
