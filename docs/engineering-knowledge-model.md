# Engineering Knowledge Model — v0.1

> Architecture discovery artifact for the AI Engineering Intelligence & Incident Copilot.
> Ground truth: Sock Shop microservices ecosystem.
> Status: **Discovery complete — ready for ingestion design, not implementation.**

---

## 1. Executive Summary

Sock Shop is a polyglot e-commerce reference app (socks). It is an excellent **portfolio substrate** because it has:

- Real service boundaries and dependency chains
- Multiple databases and a message queue
- OpenAPI specs, K8s network policies, and deployment manifests
- A critical path (checkout) that spans 6+ services
- Gaps that mirror real companies (missing ownership data, sparse runbooks, no live incident feed yet)

Your platform should treat Sock Shop not as "files to embed" but as a **typed engineering graph** with documentation and incidents layered on top. That is how internal platforms at Datadog, Stripe, and Uber reason about systems — structured entities first, semantic search second, agents third.

---

## 2. System Boundary

```
┌─────────────────────────────────────────────────────────────────┐
│  AI Engineering Intelligence Platform                           │
│                                                                 │
│  Ingestion → Engineering Assets → Graph (Neo4j) + Vector (Qdrant) │
│                          ↓                                      │
│                   LangGraph Agents → Chat UI                    │
└─────────────────────────────────────────────────────────────────┘
                              ▲
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
   Service Repos        Infrastructure Repo    engineering-data/
   (5 cloned)            (deploy, k8s, helm)    (docs, incidents,
                                                  runbooks, ownership)
```

### In-scope repositories

| Repository | Path | What it contributes |
|------------|------|---------------------|
| front-end | `source-repo/services/front-end/` | BFF routes, session logic, downstream call map |
| catalogue | `source-repo/services/catalogue/` | Product API, MySQL schema, Go service |
| carts | `source-repo/services/carts/` | Cart API, MongoDB models, Java controllers |
| orders | `source-repo/services/orders/` | Checkout orchestration, dependency hub |
| payment | `source-repo/services/payment/` | Auth rules, stateless Go service |
| infrastructure | `source-repo/infrastructure/microservices-demo/` | Deploy topology, network policies, images |

### Known gaps (mirror real orgs)

| Missing locally | Impact on platform | Mitigation |
|-----------------|-------------------|------------|
| user service source | Cannot parse auth/card/address code | Infer from front-end calls + K8s manifests; stub ownership |
| shipping service source | Cannot parse queue consumer code | Infer from orders → shipping call + RabbitMQ policies |
| Live CI/CD events | No real deployment timeline | Synthetic deployment nodes from image tags in manifests |
| Ownership registry | "Who owns X?" unanswered | `engineering-data/ownership/` (to be created) |
| Incident history | "Has this happened before?" | `engineering-data/incidents/` (to be created) |

---

## 3. Ground Truth — Sock Shop Service Catalog

### 3.1 Runtime services

| Service | Repo | Language | Port | Stateful? |
|---------|------|----------|------|-----------|
| edge-router | infrastructure | Nginx | 80, 8080 | No |
| front-end | front-end | Node.js | 8079 | Sessions (Redis in K8s) |
| catalogue | catalogue | Go | 80 | No |
| carts | carts | Java/Spring Boot | 8081 (local), 80 (deploy) | No |
| orders | orders | Java/Spring Boot | 8082 (local), 80 (deploy) | No |
| payment | payment | Go | 8080 (local), 80 (deploy) | No |
| user | — (image only) | Node.js | 80 | No |
| shipping | — (image only) | Java/Spring Boot | 80 | No |
| queue-master | — (image only) | Java/Spring Boot | 80 | No |

### 3.2 Data stores & messaging

| Asset | Type | Engine | Database/Queue | Used by |
|-------|------|--------|----------------|---------|
| catalogue-db | Database | MySQL | `socksdb` | catalogue |
| carts-db | Database | MongoDB | `data` | carts |
| orders-db | Database | MongoDB | `data` | orders |
| user-db | Database | MongoDB | — | user |
| session-db | Database | Redis | — | front-end (K8s) |
| rabbitmq | Queue | RabbitMQ | AMQP 5672 | shipping, queue-master, orders |

> **Correction:** Carts uses **MongoDB**, not Redis. Redis is only for front-end browser sessions.

### 3.3 Dependency graph (runtime)

Derived from source code call sites + K8s network policies.

```
front-end ──CALLS──► catalogue, carts, orders, user
front-end ──USES───► session-db (Redis, K8s only)

catalogue ──USES───► catalogue-db (MySQL)
carts     ──USES───► carts-db (MongoDB)
orders    ──USES───► orders-db (MongoDB)
orders    ──CALLS──► user, carts, payment, shipping
user      ──USES───► user-db (MongoDB)
shipping  ──USES───► rabbitmq
queue-master ──USES► rabbitmq

orders    ──DEPENDS_ON──► payment, shipping, carts, user  (checkout critical path)
front-end ──DEPENDS_ON──► catalogue, carts, orders, user  (user-facing path)
```

### 3.4 Blast radius map

| If this fails… | Direct impact | Downstream impact |
|----------------|---------------|-------------------|
| **payment** | Checkout fails (406) | Orders cannot complete; revenue path blocked |
| **carts** | Add/view cart fails | Checkout blocked (orders reads cart items) |
| **catalogue** | Browse/add-to-cart fails | Front-end enriches cart items from catalogue price |
| **user** | Login/register fails | Checkout blocked (needs address, card, customer) |
| **orders** | Checkout fails | Entire purchase flow blocked |
| **shipping** | Checkout fails | Orders calls shipping synchronously before save |
| **front-end** | All UI unavailable | External entry point down |
| **catalogue-db** | Product listing fails | Catalogue health degrades |
| **carts-db** | Cart persistence fails | Cart operations fail |
| **orders-db** | Order history/create fails | Orders cannot persist |
| **rabbitmq** | Async shipping pipeline stalls | May not block sync checkout path; affects shipping/queue-master |

---

## 4. API Surface (Machine-Extractable)

### 4.1 Exposed APIs by service

#### front-end (BFF — proxies to backends)

| Route | Method | Proxies to |
|-------|--------|------------|
| `/catalogue*` | GET | catalogue |
| `/tags` | GET | catalogue |
| `/cart` | GET/POST/DELETE | carts (+ catalogue for price on add) |
| `/cart/:id` | DELETE | carts |
| `/cart/update` | POST | carts (+ catalogue) |
| `/orders` | GET/POST | orders (+ user for checkout assembly) |
| `/register` | POST | user (+ carts merge) |
| `/login` | GET | user (+ carts merge) |
| `/customers`, `/addresses`, `/cards` | GET/POST/DELETE | user |

#### catalogue

| Endpoint | Method | Source |
|----------|--------|--------|
| `/catalogue` | GET | `api-spec/catalogue.json`, `service.go` |
| `/catalogue/{id}` | GET | same |
| `/catalogue/size` | GET | same |
| `/tags` | GET | same |
| `/health` | GET | same |

#### carts

| Endpoint | Method | Source |
|----------|--------|--------|
| `/carts/{customerId}` | GET, DELETE | `api-spec/carts.json`, `CartsController.java` |
| `/carts/{customerId}/merge` | GET | `CartsController.java` |
| `/carts/{customerId}/items` | GET, POST, PATCH | `ItemsController.java` |
| `/carts/{customerId}/items/{itemId}` | GET, DELETE | `ItemsController.java` |
| `/health` | GET | `HealthCheckController.java` |

#### orders

| Endpoint | Method | Source |
|----------|--------|--------|
| `/orders` | POST | `OrdersController.java`, `api-spec/orders.json` |
| `/orders` | GET | Spring Data REST |
| `/orders/search/customerId` | GET | Spring Data REST (used by front-end) |
| `/health` | GET | `HealthCheckController.java` |

**Internal calls during POST /orders:**

| Target | Endpoint | Purpose |
|--------|----------|---------|
| user | `{customer}`, `{address}`, `{card}` URIs | Fetch checkout entities |
| carts | `{items}` URI | Fetch cart line items |
| payment | `POST /paymentAuth` | Authorize payment |
| shipping | `POST /shipping` | Create shipment |

#### payment

| Endpoint | Method | Source |
|----------|--------|--------|
| `/paymentAuth` | POST | `api-spec/payment.json`, `service.go` |
| `/health` | GET | same |

**Business rule:** Declines amount > $105 (binary default) or > $200 (Helm chart override).

---

## 5. Domain Flows (Agent Reasoning Anchors)

These flows become **first-class graph traversals**, not RAG chunks.

### 5.1 Browse → Add to cart

```
Browser → front-end GET /catalogue
       → catalogue GET /catalogue → catalogue-db

Browser → front-end POST /cart {id}
       → catalogue GET /catalogue/{id}  (fetch price)
       → carts POST /carts/{sessionId}/items → carts-db
```

### 5.2 Login → Cart merge

```
Browser → front-end GET /login
       → user GET /login
       → carts GET /carts/{customerId}/merge?sessionId={sessionId}
```

### 5.3 Checkout (critical path)

```
Browser → front-end POST /orders
       → user GET (customer, address, card links)
       → orders POST /orders
            ├─ GET user/customer, user/address, user/card  (parallel)
            ├─ GET carts/.../items                          (parallel)
            ├─ POST payment/paymentAuth
            ├─ POST shipping/shipping
            └─ SAVE orders-db
```

**Latency sensitivity:** Orders makes 4+ sequential/parallel HTTP calls. Any downstream slowdown affects checkout p99. This is the primary incident investigation anchor.

---

## 6. Engineering Asset Taxonomy

Production platforms distinguish **structural facts** (graph) from **narrative knowledge** (vector).

| Asset Type | Graph (Neo4j) | Vector (Qdrant) | Primary sources |
|------------|---------------|-----------------|-----------------|
| Repository | ✅ node | metadata only | repo paths, git remote |
| Service | ✅ node | description chunk | README, docker-compose, k8s labels |
| API Endpoint | ✅ node | OpenAPI description | `api-spec/*.json`, controllers |
| Function / Class | ✅ node (optional v1) | code chunk | tree-sitter AST |
| Database | ✅ node | — | application.properties, k8s manifests |
| Queue | ✅ node | — | docker-compose, netpol |
| Deployment | ✅ node | — | k8s Deployment, image:tag |
| Team | ✅ node | — | engineering-data/ownership |
| Document | ✅ node | full text chunks | docs/, README, design.md |
| Incident | ✅ node | timeline + summary | engineering-data/incidents |
| Runbook | ✅ node | procedural chunks | engineering-data/runbooks |

### What NOT to put only in vectors

- Service A calls Service B → must be a `CALLS` edge
- Service A uses MongoDB → must be a `USES` edge
- Team X owns Service Y → must be an `OWNS` edge
- Deployment v0.4.7 deployed orders → must be a `DEPLOYED_AS` edge

Vectors alone cannot reliably answer: "What breaks if payment changes?" or "What depends on orders?"

---

## 7. Knowledge Graph Schema — v0.1

### 7.1 Node types & key properties

```yaml
Repository:
  id: string          # e.g. "repo:orders"
  name: string
  path: string
  url: string | null
  language_primary: string | null

Service:
  id: string          # e.g. "service:orders"
  name: string
  slug: string        # k8s/docker hostname
  language: string
  framework: string | null
  port: int | null
  image: string | null
  health_endpoint: string  # "/health"
  criticality: enum [tier1, tier2, tier3]

API:
  id: string          # e.g. "api:orders:POST:/orders"
  method: string
  path: string
  service_id: string
  summary: string | null
  spec_source: string # file path to OpenAPI

Database:
  id: string          # e.g. "db:carts-db"
  name: string
  engine: enum [mongodb, mysql, redis, postgres]
  connection_uri_pattern: string | null

Queue:
  id: string
  name: string
  engine: enum [rabbitmq, kafka, sqs]
  port: int | null

Deployment:
  id: string
  environment: string  # docker-compose, k8s-sock-shop
  image_tag: string
  manifest_path: string
  replicas: int | null

Team:
  id: string
  name: string
  slack_channel: string | null
  oncall_rotation: string | null

Document:
  id: string
  title: string
  doc_type: enum [design, readme, runbook, analysis]
  path: string

Incident:
  id: string
  title: string
  severity: enum [sev1, sev2, sev3]
  status: enum [open, mitigated, resolved]
  started_at: datetime
  resolved_at: datetime | null
  summary: string

Runbook:
  id: string
  title: string
  triggers: list[string]   # e.g. ["checkout-latency", "payment-errors"]
  path: string
```

### 7.2 Relationship types

| Relationship | From → To | Properties | Example |
|--------------|-----------|------------|---------|
| `HOSTS` | Repository → Service | — | front-end repo HOSTS front-end service |
| `CALLS` | Service → Service | endpoint, sync/async | orders CALLS payment |
| `EXPOSES` | Service → API | — | orders EXPOSES POST /orders |
| `USES` | Service → Database | read/write | carts USES carts-db |
| `USES` | Service → Queue | role: producer/consumer | shipping USES rabbitmq |
| `DEPENDS_ON` | Service → Service | critical: bool | orders DEPENDS_ON payment |
| `DEPLOYED_AS` | Service → Deployment | — | orders DEPLOYED_AS k8s/orders-dep |
| `OWNS` | Team → Service | — | PaymentsTeam OWNS payment |
| `DOCUMENTED_IN` | Service → Document | — | orders DOCUMENTED_IN system-analysis.md |
| `IMPACTED_BY` | Service → Incident | — | orders IMPACTED_BY INC-001 |
| `REFERENCES` | Runbook → Service | — | checkout-latency-runbook REFERENCES orders |

> Use `DEPENDS_ON` for transitive/critical-path edges. Use `CALLS` for observed HTTP/RPC edges. A service can have both.

### 7.3 Example Cypher (reference, not for execution yet)

```cypher
// Checkout subgraph
(orders:Service {name: "orders"})
  -[:CALLS {endpoint: "POST /paymentAuth"}]-> (payment:Service {name: "payment"})
  -[:CALLS {endpoint: "POST /shipping"}]-> (shipping:Service {name: "shipping"})
  -[:CALLS {endpoint: "GET /carts/{id}/items"}]-> (carts:Service {name: "carts"})
  -[:USES]-> (orders-db:Database {engine: "mongodb"})

(carts:Service)-[:USES]->(carts-db:Database {engine: "mongodb"})
// NOT Redis — common misconfiguration in generic schemas
```

---

## 8. Vector Index Strategy

### 8.1 What gets embedded (Qdrant collections)

| Collection | Content | Metadata filters |
|------------|---------|------------------|
| `code_chunks` | Functions, classes (tree-sitter) | repo, service, language, file_path |
| `doc_chunks` | README, design.md, system-analysis | doc_type, service, path |
| `api_chunks` | OpenAPI paths + descriptions | service, method, path |
| `incident_chunks` | Incident timelines, postmortems | severity, services[], date |
| `runbook_chunks` | Runbook steps | triggers[], services[] |

### 8.2 Chunking principles (production-grade)

- **Code:** Function-level, preserve imports and call sites where possible
- **Docs:** Section-level (H2 boundaries), not whole-file
- **APIs:** One chunk per endpoint with request/response schema summary
- **Incidents:** Event-level chunks with timestamps for temporal retrieval

### 8.3 Hybrid retrieval pattern

```
User query
    │
    ├─► Graph Agent: entity lookup + 1-3 hop traversal
    │       "What depends on orders?" → CALLS/DEPENDS_ON traversal
    │
    └─► Docs Agent: vector search with service filter
            "Explain checkout" → doc_chunks WHERE service=orders
```

Do not rely on vector search alone for dependency questions.

---

## 9. Agent Layer — Routing Model

### 9.1 Supervisor routing rules

| Query pattern | Primary agent | Secondary | Example |
|---------------|---------------|-----------|---------|
| "Explain architecture/flow" | Docs + Graph | Code | Onboarding questions |
| "What depends on X?" | Graph | — | Dependency/blast radius |
| "What breaks if X changes?" | Graph | Docs | Impact analysis |
| "Which repo for feature Y?" | Graph + Code | Docs | Implementation navigation |
| "Who owns X?" | Graph | Docs | Ownership lookup |
| "Latency increased after deploy" | Incident | Graph + Code | Incident investigation |
| "Has this happened before?" | Incident | Graph | Historical pattern match |
| "Show me the payment auth code" | Code | — | Source navigation |

### 9.2 Agent responsibilities (MVP)

| Agent | Inputs | Tools | Output |
|-------|--------|-------|--------|
| **Supervisor** | user query | intent classifier | routing plan |
| **Graph** | entity names | Neo4j Cypher | subgraph + blast radius |
| **Code** | repo + symbol | tree-sitter, git | code snippets + call sites |
| **Docs** | semantic query | Qdrant + filters | grounded passages |
| **Incident** | symptoms + time | incidents + graph | timeline, affected services, remediation |

### 9.3 Incident copilot reasoning template

For: *"Checkout latency increased after deployment"*

1. **Graph:** Find checkout path → front-end → orders → {payment, shipping, carts, user}
2. **Incident:** Recent deployments (`DEPLOYED_AS`) in time window
3. **Code:** Diff or version change on critical path services
4. **Docs/Runbook:** Match trigger `checkout-latency` → runbook steps
5. **Synthesize:** Affected services, likely root cause candidates, recommended actions

---

## 10. Ingestion Source Mapping

| Source file/pattern | Extract | Target |
|--------------------|---------|--------|
| `*/README.md` | Service description | Service node + doc chunk |
| `*/api-spec/*.json` | API endpoints | API nodes + EXPOSES edges |
| `*/api/endpoints.js` | BFF call map | CALLS edges from front-end |
| `*Controller.java`, `*service.go` | Route handlers | API nodes, CALLS edges |
| `application.properties` | DB URI | USES edges |
| `docker-compose.yml` | Services, images, hostnames | Service + Deployment nodes |
| `manifests/*.yaml` | K8s deployments, env | Deployment nodes |
| `manifests-policy/*.yaml` | Allowed ingress | CALLS edges (validation) |
| `internal-docs/design.md` | Architecture narrative | Document chunks |
| `docs/system-analysis.md` | Curated analysis | Document + pre-built edges |
| `engineering-data/ownership/*` | Team → Service | OWNS edges |
| `engineering-data/incidents/*` | Incident records | Incident nodes + IMPACTED_BY |
| `engineering-data/runbooks/*` | Procedures | Runbook nodes + REFERENCES |

### Ingestion priority (Phase 1)

1. Infrastructure topology (services, DBs, queues, deployments)
2. API specs + controller route extraction
3. Call graph from orders + front-end (highest-value paths)
4. Documentation corpus
5. Code AST (tree-sitter) — start with orders, payment, carts
6. Synthetic ownership + sample incidents (for copilot demo realism)

---

## 11. Architecture Decisions (Recommended)

| Decision | Recommendation | Rationale |
|----------|----------------|-----------|
| Graph vs Vector split | Structural in Neo4j, narrative in Qdrant | Matches Datadog/Stripe internal tooling patterns |
| Entity IDs | Stable URNs: `service:orders`, `api:orders:POST:/orders` | Enables idempotent re-ingestion |
| Dependency edges | Extract from code + validate with netpol | Code is source of truth; netpol confirms runtime |
| Missing repos | Create stub Service nodes from infra | Graph completeness > waiting for all clones |
| Ownership | Synthetic YAML until real data | Unblocks "who owns X?" evaluation questions |
| Agent framework | LangGraph with explicit tool boundaries | Testable, observable, not a monolithic prompt |
| Code parsing | tree-sitter → function chunks with metadata | Better than raw file embedding |
| Re-ingestion | Versioned ingestion runs, upsert not delete-all | Production pipelines are incremental |

---

## 12. Open Questions (Resolve Before Implementation)

1. **Synthetic vs live deployment data** — Will you simulate deploy events or connect to git tags only?
2. **User/shipping repos** — Clone remaining service repos or accept infra-only nodes?
3. **Ownership model** — Team per service or shared platform team?
4. **Incident format** — JSON? Markdown postmortems? PagerDuty export shape?
5. **Evaluation bar** — Use `docs/evaluation_questions.md` as golden set; target 90%+ before adding features?

---

## 13. Discovery Checklist — Status

| Item | Status |
|------|--------|
| Identify all runtime services | ✅ 10 components (8 app + edge-router + queue-master) |
| Map databases and queues | ✅ 5 DBs + RabbitMQ |
| Extract API surfaces | ✅ OpenAPI + controller analysis |
| Map service dependencies | ✅ Code + K8s netpol validated |
| Define checkout critical path | ✅ Documented |
| Define graph schema v0.1 | ✅ This document |
| Define vector strategy | ✅ This document |
| Define agent routing | ✅ This document |
| Create evaluation questions | ✅ `docs/evaluation_questions.md` |
| Ownership / incidents / runbooks | ⏳ Planned under `engineering-data/` |

---

## 14. Recommended Next Step (Still Pre-Implementation)

**Create `engineering-data/` seed artifacts** before writing ingestion code:

```
engineering-data/
├── ownership/
│   └── teams.yaml          # Team → Service mapping
├── incidents/
│   └── INC-001-checkout-latency.md
└── runbooks/
    └── checkout-latency.md
```

Then design the **ingestion contract** (Pydantic models matching Section 7) as the interface between parsers and Neo4j/Qdrant writers.

Only after the contract is stable should you implement parsers.

---

*This model is the canonical reference for graph population, agent tool design, and evaluation dataset grounding.*
