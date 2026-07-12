# AI Engineering Intelligence Platform

An **AI Engineering Copilot** and **Crisis Command Center** built on the [Sock Shop](https://github.com/microservices-demo/microservices-demo) microservices ecosystem.

The platform understands source code, service dependencies, architecture, ownership, deployments, documentation, incidents, and runbooks — then answers engineering and incident investigation questions via a multi-agent system.

## Status

| Phase | Description | Status |
|-------|-------------|--------|
| 0 | Architecture discovery | ✅ Complete |
| 1 | Git setup + seed engineering data | ✅ In progress |
| 2 | Ingestion pipeline | ⏳ Planned |
| 3 | Neo4j + Qdrant | ⏳ Planned |
| 4 | LangGraph agents | ⏳ Planned |
| 5 | FastAPI + Streamlit UI | ⏳ Planned |
| 6 | Evaluation + portfolio polish | ⏳ Planned |

## Architecture

```
Repositories → Code Ingestion → Engineering Assets
                                      │
                    ┌─────────────────┴─────────────────┐
                    ▼                                   ▼
              Knowledge Graph                      Vector Database
                 (Neo4j)                            (Qdrant)
                    │                                   │
                    └─────────────┬─────────────────────┘
                                  ▼
                           Agent Layer (LangGraph)
                                  ▼
                            Chat Interface
```

## Documentation

- [System Analysis](docs/system-analysis.md) — services, databases, APIs, checkout flow
- [Service Dependency Map](docs/service-dependency-map.md) — dependency graph and failure propagation
- [Engineering Knowledge Model](docs/engineering-knowledge-model.md) — graph schema, ingestion design
- [Evaluation Questions](docs/evaluation_questions.md) — AI copilot test dataset

## Project Structure

```
AI-Engineering-Platform/
├── docs/                  # Architecture & analysis documents
├── engineering-data/      # Ownership, incidents, runbooks (seed data)
├── scripts/               # Utility scripts (clone Sock Shop, etc.)
├── src/                   # Platform code (Phase 2+)
├── tests/
└── source-repo/           # Sock Shop clones (local only, gitignored)
```

## Getting Started

### 1. Clone this repository

```bash
git clone https://github.com/dikshashree01/AI-Engineering-Platform.git
cd AI-Engineering-Platform
```

### 2. Clone Sock Shop source repos (local only)

```bash
chmod +x scripts/clone-sock-shop.sh
./scripts/clone-sock-shop.sh
```

This populates `source-repo/` with the infrastructure and service repositories used for ingestion.

### 3. Environment setup (Phase 2+)

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
# pip install -r requirements.txt  (added in Phase 2)
```

## Example Questions the Platform Will Answer

**Engineering Intelligence:**
- Explain the checkout architecture.
- What services depend on Orders?
- Which repository should I modify to change payment decline rules?

**Incident Investigation:**
- Checkout latency increased after deployment — what changed?
- What services are affected?
- Recommend remediation steps.

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python, FastAPI |
| Agents | LangGraph |
| Knowledge Graph | Neo4j |
| Vector Store | Qdrant |
| Code Parsing | tree-sitter |
| Frontend | Streamlit |
| Deployment | Docker Compose |

## License

MIT
