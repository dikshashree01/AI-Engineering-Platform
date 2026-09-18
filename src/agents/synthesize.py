"""Format tool evidence into a user-facing answer."""

from __future__ import annotations

import json

from src.agents.config import AgentConfig
from src.agents.intent import ParsedQuery


def synthesize_answer(
    query: str,
    parsed: ParsedQuery,
    evidence: list[dict],
    config: AgentConfig | None = None,
) -> str:
    cfg = config or AgentConfig.from_env()

    if cfg.use_llm_synthesis and cfg.openai_api_key:
        return _llm_synthesize(query, parsed, evidence, cfg)

    return _template_synthesize(query, parsed, evidence)


def _tool_data(evidence: list[dict], tool: str) -> list[dict]:
    rows: list[dict] = []
    for block in evidence:
        if block.get("tool") == tool and not block.get("error"):
            rows.extend(block.get("data") or [])
    return rows


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def _join_names(rows: list[dict], key: str = "name") -> str:
    names = _unique(str(row.get(key, "")) for row in rows if row.get(key))
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + f", and {names[-1]}"


def _narrative_answer(parsed: ParsedQuery, evidence: list[dict]) -> str | None:
    service = parsed.service_name or "the service"
    intent = parsed.intent

    if intent == "ownership":
        owners = _tool_data(evidence, "service_owner")
        if not owners:
            return None
        team = owners[0].get("team_name", "Unknown team")
        slack = owners[0].get("slack")
        sentence = f"The **{service}** service is owned by the **{team}**."
        if slack:
            sentence += f" Reach them on Slack at **{slack}**."
        return sentence

    if intent == "database":
        dbs = _tool_data(evidence, "service_database")
        assets = _tool_data(evidence, "database_asset")
        if dbs:
            db = dbs[0]
            engine = db.get("engine") or "unknown engine"
            return (
                f"The **{service}** service stores data in **{db.get('name')}** "
                f"({engine})."
            )
        if assets:
            asset = assets[0]
            engine = asset.get("engine") or "unknown engine"
            used_by = _join_names([{"name": n} for n in asset.get("used_by") or []])
            sentence = f"**{asset.get('name')}** is a {engine} database asset."
            if used_by:
                sentence += f" It is used by **{used_by}**."
            return sentence
        # Fall back to RAG for session-db and similar when graph has no node
        docs = _tool_data(evidence, "search_docs")
        if docs:
            preview = (docs[0].get("text") or "").strip().split("\n")[0][:240]
            return f"Based on platform documentation: {preview}"

    if intent == "dependencies":
        deps = _tool_data(evidence, "service_dependencies")
        names = _join_names(deps)
        if names:
            return f"**{service}** depends on or calls: **{names}**."

    if intent in ("dependents", "impact", "failure"):
        deps = _tool_data(evidence, "service_dependents")
        names = _join_names(deps)
        if intent == "impact" and names:
            return (
                f"If **{service}** goes down, these callers are affected: **{names}**. "
                "Checkout or related flows may fail depending on the failure path."
            )
        if intent == "failure" and names:
            return (
                f"When **{service}** fails or errors, upstream services such as "
                f"**{names}** are impacted."
            )
        if names:
            return f"These services depend on **{service}**: **{names}**."

    if intent == "checkout":
        chains = _tool_data(evidence, "checkout_path")
        chain_strings = _unique(
            " → ".join(row.get("chain") or []) for row in chains if row.get("chain")
        )
        if chain_strings:
            lead = (
                "Checkout flows through the front-end into orders and its downstream "
                "services. Key paths from the graph:"
            )
            bullets = "\n".join(f"- {chain}" for chain in chain_strings[:6])
            return f"{lead}\n{bullets}"

    if intent == "availability":
        docs = _tool_data(evidence, "search_docs")
        fe_deps = _tool_data(evidence, "service_dependencies")
        catalogue_deps = [r for r in fe_deps if r.get("name") == "catalogue"]
        if docs:
            text = (docs[0].get("text") or "").lower()
            if "catalogue" in text and "user" in text:
                return (
                    "Customers can usually still browse the catalogue when the **user** "
                    "service is unavailable, because product browsing goes through "
                    "**catalogue** rather than **user**. Login, profile, and cart-merge "
                    "flows that need identity will fail."
                )
        return (
            "Browsing products typically uses **catalogue** via the front-end and does "
            "not require **user**. Authenticated flows (login, profile, cart merge) "
            "do require **user**."
        )

    if intent == "repository":
        docs = _tool_data(evidence, "search_docs")
        for row in docs:
            text = row.get("text") or ""
            if "source-repo" in text or "repository" in text.lower():
                for line in text.splitlines():
                    if "source-repo" in line or "repository" in line.lower():
                        return line.strip().lstrip("- ").strip()
        if parsed.service_name:
            return (
                f"Modify the **{parsed.service_name}** service repository under "
                f"`source-repo/services/{parsed.service_name}/`."
            )

    if intent == "incident":
        runbooks = _tool_data(evidence, "search_runbooks")
        incidents = _tool_data(evidence, "search_incidents")
        if runbooks:
            title = runbooks[0].get("section") or "runbook"
            preview = (runbooks[0].get("text") or "").replace("\n", " ")[:220]
            return f"Start with runbook **{title}**. {preview}..."
        if incidents:
            title = incidents[0].get("section") or "incident"
            return f"Review incident notes in **{title}** and check dependent services in the graph."

    if intent == "explain":
        docs = _tool_data(evidence, "search_docs")
        if docs:
            preview = (docs[0].get("text") or "").replace("\n", " ")[:320]
            return preview + ("..." if len(preview) >= 320 else "")

    return None


def _compact_sources(evidence: list[dict]) -> list[str]:
    lines: list[str] = []
    for block in evidence:
        if block.get("error"):
            continue
        source = block.get("source", "")
        tool = block.get("tool", "")
        data = block.get("data") or []
        if not data:
            continue
        if source == "graph":
            lines.append(f"- Graph: `{tool}` ({len(data)} result{'s' if len(data) != 1 else ''})")
        elif tool.startswith("search_"):
            top = data[0]
            lines.append(
                f"- Docs: {top.get('section') or top.get('source_file') or tool} "
                f"(score {top.get('score')})"
            )
    return lines


def _template_synthesize(query: str, parsed: ParsedQuery, evidence: list[dict]) -> str:
    if not evidence:
        return (
            "I couldn't find evidence for that question. "
            "Ensure Neo4j and Qdrant are running and that graph/RAG indexes are loaded."
        )

    narrative = _narrative_answer(parsed, evidence)
    sources = _compact_sources(evidence)

    if narrative:
        lines = [narrative]
        if sources:
            lines.extend(["", "**Sources**", *sources])
        return "\n".join(lines)

    # Fallback: structured evidence dump for uncommon intents
    lines: list[str] = []
    for block in evidence:
        tool = block.get("tool", "unknown")
        source = block.get("source", "")
        if block.get("error"):
            lines.append(f"⚠️ {source}/{tool}: {block['error']}")
            continue
        data = block.get("data") or []
        if not data:
            continue
        if tool == "service_owner":
            for row in data:
                lines.append(
                    f"- **{row.get('team_name')}** owns `{parsed.service_name}` "
                    f"(Slack: {row.get('slack')})"
                )
        elif tool.startswith("search_"):
            row = data[0]
            preview = (row.get("text") or "").replace("\n", " ")[:240]
            lines.append(preview + "...")
        else:
            lines.append(f"```\n{json.dumps(data, indent=2)[:500]}\n```")

    if not lines:
        return "No matching evidence was found for that question."

    return "\n".join(lines)


def _llm_synthesize(query: str, parsed: ParsedQuery, evidence: list[dict], cfg: AgentConfig) -> str:
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(model=cfg.openai_model, api_key=cfg.openai_api_key, temperature=0)

    system = (
        "You are an AI Engineering Copilot for the Sock Shop microservices platform. "
        "Answer using ONLY the provided evidence from the knowledge graph (Neo4j) and "
        "document search (Qdrant). Prefer graph facts for ownership, dependencies, and databases. "
        "Write a clear, direct answer in 2-5 sentences. Cite sources briefly at the end. "
        "If evidence is insufficient, say so."
    )
    user = (
        f"Question: {query}\n"
        f"Intent: {parsed.intent}\n"
        f"Service: {parsed.service_name}\n\n"
        f"Evidence:\n{json.dumps(evidence, indent=2)[:12000]}"
    )

    response = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
    return str(response.content)
