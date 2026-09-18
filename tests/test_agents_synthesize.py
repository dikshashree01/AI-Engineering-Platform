"""Tests for template synthesis (no LLM or live stores)."""

from src.agents.intent import classify_query
from src.agents.synthesize import synthesize_answer


def test_ownership_narrative() -> None:
    parsed = classify_query("Who owns the payment service?")
    evidence = [
        {
            "source": "graph",
            "tool": "service_owner",
            "data": [
                {
                    "team_name": "Payments Team",
                    "team_id": "team:payments",
                    "slack": "#team-payments",
                }
            ],
        }
    ]
    answer = synthesize_answer("Who owns the payment service?", parsed, evidence)
    assert "Payments Team" in answer
    assert "#team-payments" in answer
    assert "payment" in answer
    assert "### GRAPH" not in answer


def test_database_narrative() -> None:
    parsed = classify_query("What database does carts use?")
    evidence = [
        {
            "source": "graph",
            "tool": "service_database",
            "data": [{"name": "carts-db", "engine": "mongodb"}],
        }
    ]
    answer = synthesize_answer("What database does carts use?", parsed, evidence)
    assert "carts-db" in answer
    assert "mongodb" in answer.lower()
