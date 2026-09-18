"""Rule-based intent classification and entity extraction."""

from __future__ import annotations

import re
from dataclasses import dataclass

KNOWN_SERVICES = [
    "front-end",
    "edge-router",
    "catalogue",
    "carts",
    "orders",
    "payment",
    "shipping",
    "user",
    "queue-master",
    "user-sim",
]

KNOWN_DATABASES = [
    "session-db",
    "catalogue-db",
    "carts-db",
    "orders-db",
    "user-db",
    "rabbitmq",
]

SERVICE_ALIASES: dict[str, str] = {
    "frontend": "front-end",
    "front end": "front-end",
    "cart": "carts",
    "shopping cart": "carts",
    "order": "orders",
    "payments": "payment",
    "payment processing": "payment",
    "catalog": "catalogue",
    "session db": "session-db",
    "session-db": "session-db",
}


@dataclass(frozen=True)
class ParsedQuery:
    intent: str
    service_name: str | None
    secondary_service: str | None = None


def extract_service_name(query: str) -> str | None:
    lowered = query.lower()
    for alias, canonical in sorted(SERVICE_ALIASES.items(), key=lambda x: -len(x[0])):
        if alias in lowered:
            return canonical
    for db in KNOWN_DATABASES:
        if db in lowered:
            return db
    for service in KNOWN_SERVICES:
        if service in lowered:
            return service
        spaced = service.replace("-", " ")
        if spaced in lowered:
            return service
    return None


def classify_query(query: str) -> ParsedQuery:
    """Classify user query into intent + extracted service entity."""
    lowered = query.lower()
    service = extract_service_name(query)

    if any(p in lowered for p in ("which repository", "repository should", "modify to add", "modify to change")):
        return ParsedQuery(intent="repository", service_name=service)

    if "backend service url" in lowered or "urls configured" in lowered or "endpoints.js" in lowered:
        return ParsedQuery(intent="repository", service_name=service or "front-end")

    if any(p in lowered for p in ("who owns", "which team owns", "which service owns", "owner of", "oncall for")):
        return ParsedQuery(intent="ownership", service_name=service)

    if any(p in lowered for p in ("what breaks if", "blast radius", "impact if", "affected if")):
        return ParsedQuery(intent="impact", service_name=service)

    if any(p in lowered for p in ("can a customer", "can users", "can i browse", "if the user service is unavailable")):
        return ParsedQuery(intent="availability", service_name=service or "user")

    if any(p in lowered for p in ("what happens if", "fail or decline", "declines a transaction", "service fails")):
        return ParsedQuery(intent="failure", service_name=service)

    if "call directly" in lowered or "calls directly" in lowered:
        return ParsedQuery(intent="dependencies", service_name=service or "front-end")

    if "depend on" in lowered or "depends on" in lowered:
        if re.search(r"what\s+(services\s+)?depend(s)?\s+on", lowered):
            target = extract_service_after("depend on", lowered) or service
            return ParsedQuery(intent="dependents", service_name=target)
        return ParsedQuery(intent="dependencies", service_name=service)

    if any(p in lowered for p in ("where is", "where are", "stored", "session-db")):
        if service in KNOWN_DATABASES or "session-db" in lowered:
            return ParsedQuery(intent="database", service_name=service or "session-db")
        if any(p in lowered for p in ("catalogue", "catalog", "cart", "database", "mongodb", "mysql", "redis")):
            return ParsedQuery(intent="database", service_name=service)

    if any(p in lowered for p in ("database", "mongodb", "mysql", "redis", "db does", "db used")):
        return ParsedQuery(intent="database", service_name=service)

    if any(p in lowered for p in ("incident", "latency", "runbook", "sev-", "postmortem", "outage", "deployment")):
        return ParsedQuery(intent="incident", service_name=service)

    if any(p in lowered for p in ("checkout", "check out", "place order", "order flow", "order total", "discount")):
        return ParsedQuery(intent="checkout", service_name=service or "orders")

    if any(p in lowered for p in ("programming language", "languages are used", "polyglot")):
        return ParsedQuery(intent="explain", service_name=service)

    if any(p in lowered for p in ("merge", "anonymous cart", "after login")):
        return ParsedQuery(intent="explain", service_name=service or "carts")

    if any(p in lowered for p in ("explain", "architecture", "how does", "overview", "walk me through", "communicate")):
        return ParsedQuery(intent="explain", service_name=service)

    if service:
        return ParsedQuery(intent="service_lookup", service_name=service)

    return ParsedQuery(intent="general", service_name=None)


def extract_service_after(phrase: str, lowered: str) -> str | None:
    idx = lowered.find(phrase)
    if idx == -1:
        return None
    tail = lowered[idx + len(phrase) :].strip(" ?.")
    for service in KNOWN_SERVICES:
        if tail.startswith(service) or tail.startswith(service.replace("-", " ")):
            return service
    return None
