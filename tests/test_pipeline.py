"""Tests for the ingestion pipeline."""

import json
from pathlib import Path

import yaml

from src.ingestion.pipeline import IngestionConfig, load_graph, run_ingestion


def _write_minimal_compose(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.dump(
            {
                "version": "2",
                "services": {
                    "orders": {"image": "weaveworksdemos/orders:0.4.7", "hostname": "orders"},
                    "orders-db": {"image": "mongo:3.4", "hostname": "orders-db"},
                },
            }
        )
    )


def _write_minimal_service(services_root: Path) -> None:
    repo = services_root / "orders"
    repo.mkdir(parents=True)
    (repo / "pom.xml").write_text("<project></project>")
    (repo / "README.md").write_text("# orders")
    api_dir = repo / "api-spec"
    api_dir.mkdir()
    (api_dir / "orders.json").write_text(
        json.dumps(
            {
                "swagger": "2.0",
                "host": "orders",
                "basePath": "/",
                "paths": {
                    "/orders": {
                        "post": {"description": "Create order", "operationId": "create"}
                    }
                },
            }
        )
    )
    props = repo / "src" / "main" / "resources"
    props.mkdir(parents=True)
    (props / "application.properties").write_text(
        "spring.data.mongodb.uri=mongodb://${db:orders-db}:27017/data"
    )
    (repo / "api" / "endpoints.js").mkdir(parents=True, exist_ok=True)


def _write_engineering_data(root: Path) -> None:
    ownership = root / "ownership"
    ownership.mkdir(parents=True)
    (ownership / "teams.yaml").write_text(
        yaml.dump(
            {
                "teams": [
                    {
                        "id": "team:cart-orders",
                        "name": "Cart & Orders",
                        "owns": ["service:orders"],
                    }
                ]
            }
        )
    )
    incidents = root / "incidents"
    incidents.mkdir()
    (incidents / "INC-001-test.md").write_text(
        "| **ID** | INC-001 |\n"
        "| **Severity** | SEV-2 |\n"
        "| **Status** | resolved |\n\n"
        "## Impact\n\n"
        "- **Affected services:** orders\n"
    )
    runbooks = root / "runbooks"
    runbooks.mkdir()
    (runbooks / "checkout-latency.md").write_text(
        "| **Related services** | orders, payment |\n"
        "| **Trigger** | latency |\n"
    )


def test_run_ingestion_produces_graph_json(tmp_path: Path) -> None:
    compose = tmp_path / "docker-compose.yml"
    services = tmp_path / "services"
    engineering = tmp_path / "engineering-data"
    output = tmp_path / "output" / "graph.json"

    _write_minimal_compose(compose)
    _write_minimal_service(services)
    _write_engineering_data(engineering)

    result = run_ingestion(
        IngestionConfig(
            project_root=tmp_path,
            docker_compose_path=compose,
            services_root=services,
            engineering_data_root=engineering,
            output_path=output,
        )
    )

    assert output.exists()
    assert "docker_compose" in result.extractors_run
    assert "repository" in result.extractors_run
    assert "openapi" in result.extractors_run
    assert "call_graph" in result.extractors_run
    assert "engineering_data" in result.extractors_run

    stats = result.graph.stats()
    assert stats["nodes_total"] > 0
    assert stats["edges_total"] > 0

    loaded = load_graph(output)
    assert loaded.version == "0.1"
    assert len(loaded.nodes) == stats["nodes_total"]


def test_run_ingestion_warns_on_missing_inputs(tmp_path: Path) -> None:
    output = tmp_path / "output" / "graph.json"
    result = run_ingestion(
        IngestionConfig(
            project_root=tmp_path,
            docker_compose_path=tmp_path / "missing-compose.yml",
            services_root=tmp_path / "missing-services",
            engineering_data_root=tmp_path / "missing-data",
            output_path=output,
        )
    )
    assert len(result.warnings) == 3
    assert output.exists()
    assert result.graph.stats()["nodes_total"] == 0


def test_integration_full_sock_shop_pipeline() -> None:
    compose = Path(
        "source-repo/infrastructure/microservices-demo/deploy/docker-compose/docker-compose.yml"
    )
    if not compose.exists():
        import pytest

        pytest.skip("Sock Shop source repos not cloned")

    result = run_ingestion(
        IngestionConfig(output_path=Path("output/test_engineering_graph.json"))
    )
    stats = result.graph.stats()
    assert stats["nodes_total"] > 20
    assert stats["edges_total"] > 20
    assert stats.get("nodes_Service", 0) >= 5
