"""Unit tests for evaluation scoring (no live stores required)."""

from src.agents.eval import score_case
from src.agents.eval_cases import EVAL_CASES


def test_score_case_passes_when_keywords_in_evidence() -> None:
    case = EVAL_CASES[7]  # payment ownership
    answer = "Route: ownership"
    evidence = [
        {
            "source": "graph",
            "tool": "service_owner",
            "data": [{"team_name": "Payments Team", "team_id": "team:payments"}],
        }
    ]
    result = score_case(
        case,
        answer,
        evidence,
        {"intent": "ownership", "service": "payment", "evidence_count": 1},
    )
    assert result.passed


def test_score_case_fails_when_keywords_missing() -> None:
    case = EVAL_CASES[11]  # carts database
    result = score_case(
        case,
        "no useful content",
        [],
        {"intent": "general", "service": None, "evidence_count": 0},
    )
    assert not result.passed
    assert result.missing_groups
