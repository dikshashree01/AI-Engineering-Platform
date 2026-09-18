"""Evaluation runner — score copilot answers against the 22-question dataset."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from src.agents.eval_cases import EVAL_CASES, EvalCase
from src.agents.workflow import build_workflow


@dataclass
class EvalResult:
    case: EvalCase
    intent: str | None
    service: str | None
    evidence_count: int
    passed: bool
    missing_groups: list[list[str]]
    answer_preview: str


def _response_text(answer: str, evidence: list[dict], meta: dict) -> str:
    payload = {**meta, "answer": answer, "evidence": evidence}
    return json.dumps(payload, default=str).lower()


def score_case(case: EvalCase, answer: str, evidence: list[dict], meta: dict) -> EvalResult:
    text = _response_text(answer, evidence, meta)
    missing: list[list[str]] = []

    for group in case.must_contain_any:
        if not any(term.lower() in text for term in group):
            missing.append(group)

    passed = not missing
    preview = answer.replace("\n", " ")[:160]

    return EvalResult(
        case=case,
        intent=meta.get("intent"),
        service=meta.get("service"),
        evidence_count=meta.get("evidence_count", 0),
        passed=passed,
        missing_groups=missing,
        answer_preview=preview,
    )


def run_evaluation(cases: list[EvalCase] | None = None) -> tuple[list[EvalResult], dict]:
    cases = cases or EVAL_CASES
    results: list[EvalResult] = []
    workflow = build_workflow()

    for case in cases:
        raw = workflow.invoke({"query": case.question, "parsed": None, "evidence": [], "answer": ""})
        parsed = raw.get("parsed")
        meta = {
            "intent": parsed.intent if parsed else None,
            "service": parsed.service_name if parsed else None,
            "evidence_count": len(raw.get("evidence", [])),
        }
        results.append(
            score_case(case, raw.get("answer", ""), raw.get("evidence", []), meta)
        )

    passed = sum(1 for r in results if r.passed)
    total = len(results)
    summary = {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "accuracy_pct": round(100 * passed / total, 1) if total else 0.0,
        "target_pct": 90.0,
        "met_target": passed / total >= 0.9 if total else False,
    }
    return results, summary


def format_report(results: list[EvalResult], summary: dict) -> str:
    lines = [
        "# Evaluation Report",
        "",
        f"**Score: {summary['passed']}/{summary['total']} ({summary['accuracy_pct']}%)** "
        f"— target {summary['target_pct']}%",
        "",
    ]

    if summary["met_target"]:
        lines.append("✅ Target met.")
    else:
        lines.append("❌ Below target — review failed cases below.")
    lines.append("")

    by_category: dict[str, list[EvalResult]] = {}
    for r in results:
        by_category.setdefault(r.case.category, []).append(r)

    for category, cat_results in by_category.items():
        cat_pass = sum(1 for r in cat_results if r.passed)
        lines.append(f"## {category} ({cat_pass}/{len(cat_results)})")
        lines.append("")
        for r in cat_results:
            mark = "✅" if r.passed else "❌"
            lines.append(f"{mark} **Q{r.case.id}** — {r.case.question}")
            lines.append(
                f"   intent=`{r.intent}` service=`{r.service}` evidence={r.evidence_count}"
            )
            if not r.passed:
                for group in r.missing_groups:
                    lines.append(f"   missing one of: {', '.join(group)}")
            lines.append(f"   preview: {r.answer_preview}...")
            lines.append("")

    return "\n".join(lines)


def results_to_json(results: list[EvalResult], summary: dict) -> str:
    payload = {
        "summary": summary,
        "results": [
            {
                **asdict(r.case),
                "intent": r.intent,
                "service": r.service,
                "evidence_count": r.evidence_count,
                "passed": r.passed,
                "missing_groups": r.missing_groups,
                "answer_preview": r.answer_preview,
            }
            for r in results
        ],
    }
    return json.dumps(payload, indent=2)
