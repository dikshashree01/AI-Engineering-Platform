"""LangGraph multi-agent workflow."""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, StateGraph

from src.agents.config import AgentConfig
from src.agents.graph_tools import gather_graph_evidence
from src.agents.intent import ParsedQuery, classify_query
from src.agents.rag_tools import gather_rag_evidence
from src.agents.synthesize import synthesize_answer

GRAPH_INTENTS = {
    "ownership",
    "dependencies",
    "dependents",
    "impact",
    "database",
    "service_lookup",
    "failure",
}
RAG_INTENTS = {"explain", "incident", "general", "repository", "availability", "failure"}
HYBRID_INTENTS = {"checkout", "ownership", "impact", "database", "dependencies", "dependents"}


class AgentState(TypedDict):
    query: str
    parsed: ParsedQuery | None
    evidence: list[dict]
    answer: str


def supervisor_node(state: AgentState) -> dict:
    parsed = classify_query(state["query"])
    return {"parsed": parsed, "evidence": []}


def graph_agent_node(state: AgentState) -> dict:
    parsed = state["parsed"]
    if not parsed:
        return {}
    if parsed.intent not in GRAPH_INTENTS | HYBRID_INTENTS | {"incident", "availability", "explain"}:
        return {}
    evidence = gather_graph_evidence(parsed.intent, parsed.service_name)
    return {"evidence": state.get("evidence", []) + evidence}


def rag_agent_node(state: AgentState) -> dict:
    parsed = state["parsed"]
    if not parsed:
        return {}
    evidence = gather_rag_evidence(parsed, state["query"])
    return {"evidence": state.get("evidence", []) + evidence}


def synthesize_node(state: AgentState) -> dict:
    parsed = state["parsed"]
    if not parsed:
        return {"answer": "Could not parse query."}
    answer = synthesize_answer(state["query"], parsed, state.get("evidence", []))
    return {"answer": answer}


def build_workflow():
    graph = StateGraph(AgentState)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("graph_agent", graph_agent_node)
    graph.add_node("rag_agent", rag_agent_node)
    graph.add_node("synthesize", synthesize_node)

    graph.set_entry_point("supervisor")
    graph.add_edge("supervisor", "graph_agent")
    graph.add_edge("graph_agent", "rag_agent")
    graph.add_edge("rag_agent", "synthesize")
    graph.add_edge("synthesize", END)

    return graph.compile()


def run_copilot(query: str, config: AgentConfig | None = None) -> dict:
    """Execute the full agent pipeline for one user query."""
    _ = config  # reserved for future LLM routing
    workflow = build_workflow()
    result = workflow.invoke({"query": query, "parsed": None, "evidence": [], "answer": ""})
    return {
        "query": query,
        "intent": result["parsed"].intent if result.get("parsed") else None,
        "service": result["parsed"].service_name if result.get("parsed") else None,
        "evidence_count": len(result.get("evidence", [])),
        "answer": result.get("answer", ""),
    }
