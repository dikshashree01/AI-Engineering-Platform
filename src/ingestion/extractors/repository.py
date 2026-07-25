"""Discover service repositories and emit Repository nodes with metadata."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from src.ingestion.models import (
    EdgeType,
    GraphEdge,
    GraphExport,
    GraphNode,
    NodeType,
    edge_id,
    repository_id,
    service_id,
)

logger = logging.getLogger(__name__)

DEFAULT_SERVICES_ROOT = Path("source-repo/services")


@dataclass(frozen=True)
class RepositoryMetadata:
    name: str
    path: str
    primary_language: str | None
    build_system: str | None
    has_dockerfile: bool
    has_readme: bool
    has_tests: bool


def _has_go_sources(repo_path: Path) -> bool:
    if list(repo_path.glob("*.go")):
        return True
    return any(repo_path.glob("cmd/**/*.go")) or any(repo_path.glob("**/*.go"))


def _detect_language(repo_path: Path) -> str | None:
    if (repo_path / "pom.xml").exists() or (repo_path / "build.gradle").exists():
        return "Java"
    if (repo_path / "go.mod").exists() or _has_go_sources(repo_path):
        return "Go"
    if (repo_path / "package.json").exists():
        if (repo_path / "tsconfig.json").exists():
            return "TypeScript"
        return "JavaScript"
    if (repo_path / "pyproject.toml").exists() or (repo_path / "requirements.txt").exists():
        return "Python"
    return None


def _detect_build_system(repo_path: Path) -> str | None:
    if (repo_path / "pom.xml").exists():
        return "Maven"
    if (repo_path / "build.gradle").exists() or (repo_path / "settings.gradle").exists():
        return "Gradle"
    if (repo_path / "package.json").exists():
        return "npm"
    if (repo_path / "pyproject.toml").exists():
        content = (repo_path / "pyproject.toml").read_text(encoding="utf-8", errors="ignore")
        if "[tool.poetry]" in content or "poetry-core" in content:
            return "Poetry"
        return "pip"
    if (repo_path / "requirements.txt").exists() or (repo_path / "setup.py").exists():
        return "pip"
    if (repo_path / "Makefile").exists():
        return "make"
    return None


def _has_dockerfile(repo_path: Path) -> bool:
    if (repo_path / "Dockerfile").exists():
        return True
    return any(repo_path.glob("docker/**/Dockerfile*"))


def _has_readme(repo_path: Path) -> bool:
    return (repo_path / "README.md").exists() or (repo_path / "readme.md").exists()


def _has_tests(repo_path: Path) -> bool:
    if (repo_path / "test").is_dir() and any((repo_path / "test").iterdir()):
        return True
    if (repo_path / "tests").is_dir() and any((repo_path / "tests").iterdir()):
        return True
    if any(repo_path.glob("**/*_test.go")):
        return True
    java_tests = repo_path / "src" / "test"
    return java_tests.is_dir() and any(java_tests.rglob("*"))


def infer_service_name(repo_name: str) -> str:
    """Map repository directory name to runtime service name."""
    return repo_name


def analyze_repository(repo_path: Path, project_root: Path | None = None) -> RepositoryMetadata | None:
    """Extract metadata from a single repository directory."""
    if not repo_path.is_dir():
        return None

    root = project_root or Path.cwd()
    try:
        relative_path = str(repo_path.resolve().relative_to(root.resolve()))
    except ValueError:
        relative_path = str(repo_path)

    return RepositoryMetadata(
        name=repo_path.name,
        path=relative_path,
        primary_language=_detect_language(repo_path),
        build_system=_detect_build_system(repo_path),
        has_dockerfile=_has_dockerfile(repo_path),
        has_readme=_has_readme(repo_path),
        has_tests=_has_tests(repo_path),
    )


def metadata_to_graph(metadata: RepositoryMetadata) -> GraphExport:
    """Convert repository metadata into graph nodes and CONTAINS edges."""
    export = GraphExport(source=f"repository:{metadata.name}")
    repo_node_id = repository_id(metadata.name)
    service_node_id = service_id(infer_service_name(metadata.name))

    export.nodes.append(
        GraphNode(
            id=repo_node_id,
            type=NodeType.REPOSITORY,
            name=metadata.name,
            properties={
                "path": metadata.path,
                "primary_language": metadata.primary_language,
                "build_system": metadata.build_system,
                "has_dockerfile": metadata.has_dockerfile,
                "has_readme": metadata.has_readme,
                "has_tests": metadata.has_tests,
            },
        )
    )
    export.edges.append(
        GraphEdge(
            id=edge_id(EdgeType.CONTAINS, repo_node_id, service_node_id),
            type=EdgeType.CONTAINS,
            from_id=repo_node_id,
            to_id=service_node_id,
            properties={"source": "repository-extractor"},
        )
    )
    return export


def parse_repositories(
    services_root: Path | None = None,
    project_root: Path | None = None,
) -> GraphExport:
    """
    Discover repositories under source-repo/services and return GraphExport.

    Args:
        services_root: Path to services directory (default: source-repo/services).
        project_root: Project root for relative paths (default: cwd).
    """
    root = project_root or Path.cwd()
    services_path = services_root or (root / DEFAULT_SERVICES_ROOT)
    combined = GraphExport(source="repositories-all")

    if not services_path.exists():
        logger.warning("Services root not found: %s", services_path)
        return combined

    for entry in sorted(services_path.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name.startswith("."):
            continue

        metadata = analyze_repository(entry, project_root=root)
        if metadata is None:
            continue

        combined.merge(metadata_to_graph(metadata))
        logger.info("Extracted repository metadata: %s", metadata.name)

    return combined
