"""Streamlit Crisis Command Center — chat UI for the engineering copilot."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Streamlit runs this file as a script; ensure project root is on sys.path.
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from src.agents.workflow import run_copilot
from src.platform.health import platform_health

st.set_page_config(
    page_title="Engineering Crisis Command Center",
    page_icon="🛠️",
    layout="wide",
)

st.title("Engineering Crisis Command Center")
st.caption("Sock Shop engineering intelligence — Graph (Neo4j) + RAG (Qdrant) + Agents")

checks = platform_health()
col1, col2, col3 = st.columns(3)
col1.metric("Neo4j", "✅ up" if checks["neo4j"] else "❌ down")
col2.metric("Qdrant", "✅ up" if checks["qdrant"] else "❌ down")
col3.metric("LLM synthesis", "✅ on" if os.getenv("OPENAI_API_KEY") else "template mode")

if not checks["neo4j"] or not checks["qdrant"]:
    st.warning(
        "Stores are down. Run `./scripts/start-platform.sh` then reload graph and RAG indexes."
    )

SAMPLES = [
    "Who owns the payment service?",
    "What services depend on orders?",
    "What database does carts use?",
    "Explain the checkout flow",
    "Checkout latency increased — what runbook should I follow?",
]

with st.sidebar:
    st.header("Quick prompts")
    for sample in SAMPLES:
        if st.button(sample, use_container_width=True):
            st.session_state["pending_query"] = sample

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

pending = st.session_state.pop("pending_query", None)
user_input = st.chat_input("Ask about architecture, ownership, incidents, runbooks...")
query = pending or user_input

if query:
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        with st.spinner("Querying graph + RAG..."):
            result = run_copilot(query)
        answer = result["answer"]
        st.markdown(answer)
        with st.expander("Debug metadata"):
            st.json(
                {
                    "intent": result.get("intent"),
                    "service": result.get("service"),
                    "evidence_count": result.get("evidence_count"),
                }
            )

    st.session_state.messages.append({"role": "assistant", "content": answer})
