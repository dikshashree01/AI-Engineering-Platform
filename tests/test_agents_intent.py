"""Tests for agent intent routing (no Neo4j/Qdrant/LLM required)."""

from src.agents.intent import classify_query, extract_service_name


def test_extract_service_name_aliases() -> None:
    assert extract_service_name("who owns payment processing") == "payment"
    assert extract_service_name("front end calls orders") == "front-end"
    assert extract_service_name("shopping cart database") == "carts"


def test_classify_ownership() -> None:
    parsed = classify_query("Who owns the payment service?")
    assert parsed.intent == "ownership"
    assert parsed.service_name == "payment"


def test_classify_dependents() -> None:
    parsed = classify_query("What services depend on orders?")
    assert parsed.intent == "dependents"
    assert parsed.service_name == "orders"


def test_classify_dependencies() -> None:
    parsed = classify_query("What does orders depend on?")
    assert parsed.intent == "dependencies"
    assert parsed.service_name == "orders"


def test_classify_database() -> None:
    parsed = classify_query("What database does carts use?")
    assert parsed.intent == "database"
    assert parsed.service_name == "carts"


def test_classify_checkout() -> None:
    parsed = classify_query("Explain the checkout flow")
    assert parsed.intent == "checkout"


def test_classify_incident() -> None:
    parsed = classify_query("Checkout latency increased after deployment")
    assert parsed.intent == "incident"


def test_classify_ownership_service_phrasing() -> None:
    parsed = classify_query("Which service owns payment processing?")
    assert parsed.intent == "ownership"
    assert parsed.service_name == "payment"


def test_classify_repository() -> None:
    parsed = classify_query("Which repository should I modify to change payment decline rules?")
    assert parsed.intent == "repository"
    assert parsed.service_name == "payment"


def test_classify_failure() -> None:
    parsed = classify_query("What happens if the payment service fails or declines a transaction?")
    assert parsed.intent == "failure"
    assert parsed.service_name == "payment"


def test_classify_session_db() -> None:
    parsed = classify_query("What is session-db used for?")
    assert parsed.intent == "database"
    assert parsed.service_name == "session-db"


def test_classify_availability() -> None:
    parsed = classify_query("Can a customer browse products if the user service is unavailable?")
    assert parsed.intent == "availability"
    assert parsed.service_name == "user"


def test_classify_front_end_calls() -> None:
    parsed = classify_query("What services does the front-end call directly?")
    assert parsed.intent == "dependencies"
    assert parsed.service_name == "front-end"


def test_classify_impact() -> None:
    parsed = classify_query("What breaks if payment service goes down?")
    assert parsed.intent == "impact"
    assert parsed.service_name == "payment"
