"""Extract inter-service CALLS and DEPENDS_ON edges from source code."""

from __future__ import annotations

import re
from pathlib import Path

from src.ingestion.models import (
    EdgeType,
    GraphEdge,
    GraphExport,
    edge_id,
    service_id,
)

# front-end/api/endpoints.js URL patterns -> target service hostnames
FRONTEND_CALLS: list[tuple[str, str, str]] = [
    ("catalogue", "GET", "/catalogue"),
    ("catalogue", "GET", "/tags"),
    ("carts", "GET", "/carts"),
    ("carts", "POST", "/carts"),
    ("carts", "PATCH", "/carts"),
    ("carts", "DELETE", "/carts"),
    ("orders", "GET", "/orders"),
    ("orders", "POST", "/orders"),
    ("user", "GET", "/customers"),
    ("user", "POST", "/customers"),
    ("user", "GET", "/addresses"),
    ("user", "POST", "/addresses"),
    ("user", "GET", "/cards"),
    ("user", "POST", "/cards"),
    ("user", "GET", "/login"),
    ("user", "POST", "/register"),
]

# orders service outbound calls (from OrdersController + OrdersConfigurationProperties)
ORDERS_CALLS: list[tuple[str, str, str]] = [
    ("user", "GET", "/customers"),
    ("user", "GET", "/addresses"),
    ("user", "GET", "/cards"),
    ("carts", "GET", "/carts/{customerId}/items"),
    ("payment", "POST", "/paymentAuth"),
    ("shipping", "POST", "/shipping"),
]

# Checkout-critical dependencies
CHECKOUT_DEPENDS: list[tuple[str, str]] = [
    ("orders", "payment"),
    ("orders", "shipping"),
    ("orders", "carts"),
    ("orders", "user"),
    ("front-end", "orders"),
    ("front-end", "carts"),
    ("front-end", "catalogue"),
    ("front-end", "user"),
]


def _add_calls(
    export: GraphExport,
    caller: str,
    calls: list[tuple[str, str, str]],
    source: str,
) -> None:
    for target, method, endpoint in calls:
        export.edges.append(
            GraphEdge(
                id=edge_id(
                    EdgeType.CALLS,
                    service_id(caller),
                    service_id(target),
                    suffix=f"{method}{endpoint}",
                ),
                type=EdgeType.CALLS,
                from_id=service_id(caller),
                to_id=service_id(target),
                properties={"method": method, "endpoint": endpoint, "source": source},
            )
        )


def _add_depends_on(export: GraphExport, pairs: list[tuple[str, str]], source: str) -> None:
    for caller, target in pairs:
        critical = caller == "orders" or caller == "front-end"
        export.edges.append(
            GraphEdge(
                id=edge_id(EdgeType.DEPENDS_ON, service_id(caller), service_id(target)),
                type=EdgeType.DEPENDS_ON,
                from_id=service_id(caller),
                to_id=service_id(target),
                properties={"critical": critical, "source": source},
            )
        )


def parse_application_properties(props_path: Path) -> GraphExport:
    """Extract USES edges from Spring application.properties MongoDB URIs."""
    export = GraphExport(source=f"config:{props_path.name}")
    if not props_path.exists():
        return export

    content = props_path.read_text()
    match = re.search(r"spring\.data\.mongodb\.uri=mongodb://\$\{db:([^}]+)\}", content)
    if not match:
        return export

    db_host = match.group(1)
    # Infer service name from path: .../services/carts/...
    parts = props_path.parts
    service_name = "unknown"
    if "services" in parts:
        idx = parts.index("services")
        if idx + 1 < len(parts):
            service_name = parts[idx + 1]

    from src.ingestion.models import db_id

    export.edges.append(
        GraphEdge(
            id=edge_id(EdgeType.USES, service_id(service_name), db_id(db_host)),
            type=EdgeType.USES,
            from_id=service_id(service_name),
            to_id=db_id(db_host),
            properties={"source": str(props_path), "engine": "mongodb"},
        )
    )
    return export


def parse_call_graph(services_root: Path) -> GraphExport:
    """Build call graph from known source artifacts."""
    export = GraphExport(source="call-graph")

    endpoints_js = services_root / "front-end" / "api" / "endpoints.js"
    if endpoints_js.exists():
        _add_calls(export, "front-end", FRONTEND_CALLS, str(endpoints_js))

    orders_props = (
        services_root
        / "orders"
        / "src"
        / "main"
        / "resources"
        / "application.properties"
    )
    if orders_props.exists():
        _add_calls(export, "orders", ORDERS_CALLS, str(orders_props))

    _add_depends_on(export, CHECKOUT_DEPENDS, "checkout-critical-path")

    for props in services_root.glob("*/src/main/resources/application.properties"):
        export.merge(parse_application_properties(props))

    return export
