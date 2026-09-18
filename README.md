# AI Engineering Intelligence Platform

An **AI Engineering Copilot** and **Crisis Command Center** built on the [Sock Shop](https://github.com/microservices-demo/microservices-demo) microservices ecosystem.

The platform ingests source code, service dependencies, architecture docs, ownership, incidents, and runbooks — then answers engineering and incident investigation questions via a **multi-agent system** backed by **Neo4j** (graph) and **Qdrant** (RAG).

## Status

| Phase | Description | Status |
|-------|-------------|--------|
| 0 | Architecture discovery | ✅ Complete |
| 1 | Git setup + seed engineering data | ✅ Complete |
| 2 | Ingestion pipeline | ✅ Complete |
| 3 | Neo4j knowledge graph | ✅ Complete |
| 4 | Qdrant RAG index | ✅ Complete |
| 5 | LangGraph agent layer | ✅ Complete |
| 6 | MCP + FastAPI + Streamlit UI | ✅ Complete |
| 7 | Evaluation suite (22 questions) | ✅ Complete — **22/22 (100%)** |

## Architecture

```
Repositories → Ingestion → Engineering Assets
                                  │
                    ┌─────────────┴─────────────┐
                    ▼                           ▼
              Knowledge Graph              Vector Store
                 (Neo4j)                    (Qdrant)
                    │                           │
                    └─────────────┬─────────────┘
                                  ▼
                    LangGraph Agents (supervisor → graph → rag → synthesize)
                                  │
                    ┌─────────────┼─────────────┐
                    ▼             ▼             ▼
                 CLI          FastAPI       MCP (Cursor)
                              Streamlit UI
```

## Quick Start

### 1. Clone and prepare data

```bash
git clone https://github.com/dikshashree01/AI-Engineering-Platform.git
cd AI-Engineering-Platform

chmod +x scripts/*.sh
./scripts/clone-sock-shop.sh   # populates source-repo/ (gitignored locally)
```

### 2. Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate

pip install pydantic pyyaml neo4j "qdrant-client>=1.13,<1.15" fastembed \
  langgraph langchain-core langchain-openai \
  fastapi uvicorn streamlit "mcp>=1.2,<2"
```

> **Note:** Pin MCP to `>=1.2,<2` — an unrelated `mcp` 2.x package exists on PyPI.

### 3. Configure environment

```bash
cp .env.example .env
# Optional: set OPENAI_API_KEY for LLM synthesis (template mode works without it)
```

### 4. Start infrastructure

```bash
open -a Docker   # macOS — start Docker Desktop first
./scripts/start-platform.sh
```

### 5. Load graph and RAG (first run or after volume reset)

```bash
python3 -m src.ingestion.run
python3 -m src.graph.run load --clear
python3 -m src.rag.run index --recreate
```

### 6. Ask questions

```bash
# CLI copilot
python3 -m src.agents.run status
python3 -m src.agents.run "Who owns the payment service?"
python3 -m src.agents.run eval --full

# Streamlit UI + API
./scripts/start-ui.sh
# UI:  http://localhost:8501
# API: http://localhost:8000/docs
```

## MCP (Cursor Integration)

Custom MCP servers are configured via JSON (not the Marketplace UI).

Copy or merge `config/cursor-mcp.example.json` into **`.cursor/mcp.json`** in this project:

```json
{
  "mcpServers": {
    "engineering-platform": {
      "type": "stdio",
      "command": "python3",
      "args": ["-m", "src.mcp.server"],
      "env": {
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "changeme",
        "QDRANT_URL": "http://localhost:6333",
        "QDRANT_COLLECTION": "engineering_rag",
        "EMBEDDING_PROVIDER": "fastembed"
      }
    }
  }
}
```

Reload Cursor, enable **engineering-platform** under **Customize → MCPs**, then ask:

> Use `graph_service_owner` for payment

Available MCP tools: `copilot_ask`, `graph_service_owner`, `graph_service_dependencies`, `graph_service_dependents`, `graph_service_database`, `graph_checkout_paths`, `rag_search`.

## Evaluation

22 questions from [`docs/evaluation_questions.md`](docs/evaluation_questions.md):

```bash
./scripts/run-eval.sh                    # writes output/eval_report.md
python3 -m src.agents.run eval --full    # print report
python3 -m src.agents.run eval --full --json
python3 -m src.agents.run eval           # quick 5-question smoke test
```

## Project Structure

```
AI-Engineering-Platform/
├── docs/                     # Architecture analysis + eval questions
├── engineering-data/         # Ownership, incidents, runbooks (seed data)
├── config/                   # MCP config example
├── scripts/                  # Setup, start, eval scripts
├── src/
│   ├── ingestion/            # Extract engineering assets from repos
│   ├── graph/                # Neo4j loader + Cypher queries
│   ├── rag/                  # Qdrant chunking, embedding, search
│   ├── agents/               # LangGraph workflow + eval suite
│   ├── mcp/                  # MCP server for Cursor
│   ├── api/                  # FastAPI REST backend
│   └── ui/                   # Streamlit Crisis Command Center
├── tests/
├── docker-compose.yml        # Neo4j + Qdrant
└── source-repo/              # Sock Shop clones (local, gitignored)
```

## Documentation

- [System Analysis](docs/system-analysis.md) — services, databases, APIs, checkout flow
- [Service Dependency Map](docs/service-dependency-map.md) — dependency graph and failure propagation
- [Engineering Knowledge Model](docs/engineering-knowledge-model.md) — graph schema, ingestion design
- [Evaluation Questions](docs/evaluation_questions.md) — 22-question test dataset

## Example Questions

**Engineering intelligence:**
- Who owns the payment service?
- What services depend on orders?
- What database does carts use? (MongoDB, not Redis)
- Explain the checkout flow

**Incident investigation:**
- Checkout latency increased — what runbook should I follow?
- What breaks if the payment service goes down?

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python, FastAPI |
| Agents | LangGraph |
| Knowledge Graph | Neo4j 5.x |
| Vector Store | Qdrant |
| Embeddings | FastEmbed (local) |
| MCP | Model Context Protocol (stdio) |
| Frontend | Streamlit |
| Deployment | Docker Compose |

## Daily Workflow (after Mac restart)

```bash
open -a Docker
./scripts/start-platform.sh
python3 -m src.agents.run status
# Re-load only if Docker volumes were wiped:
# python3 -m src.graph.run load --clear
# python3 -m src.rag.run index --recreate
```

## License

MIT
