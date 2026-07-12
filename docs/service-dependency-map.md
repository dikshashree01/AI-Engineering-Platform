# Sock Shop — Service Dependency Map

> Dependency map derived from repository source code and Kubernetes network policies.
> Every edge cites its evidence. See `docs/system-analysis.md` for full API and failure analysis.

---

## 1. Dependency Legend

| Symbol | Meaning |
|--------|---------|
| `──HTTP──►` | Synchronous REST call (observed in source) |
| `──USES──►` | Data store or queue connection (config / netpol) |
| `[K8s]` | Relationship confirmed by Kubernetes network policy |
| `[code]` | Relationship confirmed by application source code |

---

## 2. System Topology

```
                              ┌─────────────┐
                              │   Browser   │
                              └──────┬──────┘
                                     │ HTTP
                              ┌──────▼──────┐
                              │ edge-router │  (ports 80, 8080)
                              └──────┬──────┘
                                     │
                              ┌──────▼──────┐
                              │  front-end  │  Node.js, port 8079
                              └──┬───┬───┬──┘
                    HTTP         │   │   │         HTTP
              ┌──────────────────┘   │   └──────────────────┐
              │                      │                      │
       ┌──────▼──────┐        ┌──────▼──────┐        ┌──────▼──────┐
       │  catalogue  │        │    carts    │        │    orders   │
       │    (Go)     │        │   (Java)    │        │   (Java)    │
       └──────┬──────┘        └──────┬──────┘        └──┬───┬───┬───┘
              │ USES                 │ USES             │   │   │
       ┌──────▼──────┐        ┌──────▼──────┐     HTTP  │   │   │ HTTP
       │ catalogue-db│        │   carts-db  │          │   │   │
       │   (MySQL)   │        │  (MongoDB)  │    ┌─────▼┐ ┌─▼────┐ ┌────▼─────┐
       └─────────────┘        └─────────────┘    │payment│ │user  │ │ shipping │
                                                 │ (Go)  │ │(Node)│ │  (Java)  │
                                                 └───────┘ └──┬───┘ └────┬─────┘
                                                              │ USES     │ USES
                                                       ┌──────▼──────┐  │
                                                       │   user-db   │  │
                                                       │  (MongoDB)  │  │
                                                       └─────────────┘  │
                                                                  ┌─────▼─────┐
                                                                  │  rabbitmq │
                                                                  └─────┬─────┘
                                                                        │ USES
                                                                  ┌─────▼───────┐
                                                                  │queue-master │
                                                                  └─────────────┘

  front-end ──USES──► session-db (Redis)   [K8s only: SESSION_REDIS=true]
  orders    ──USES──► orders-db (MongoDB)
```

---

## 3. Service-to-Service Dependencies

### 3.1 front-end

| Depends on | Relationship | Endpoint / Usage | Evidence |
|------------|--------------|------------------|----------|
| catalogue | HTTP GET | `/catalogue*`, `/tags`, `/catalogue/images*` | `api/catalogue/index.js`, `api/endpoints.js` [code] [K8s: netpol-catalogue-access] |
| carts | HTTP GET/POST/PATCH/DELETE | `/carts/{id}/items`, merge, delete | `api/cart/index.js`, `api/user/index.js` [code] [K8s: netpol-cart-access] |
| orders | HTTP GET/POST | `/orders`, `/orders/search/customerId` | `api/orders/index.js` [code] [K8s: netpol-orders-access] |
| user | HTTP GET/POST/DELETE | `/customers`, `/addresses`, `/cards`, `/login`, `/register` | `api/user/index.js`, `api/endpoints.js` [code] [K8s: netpol-user-access] |
| session-db | USES | Redis sessions when `SESSION_REDIS=true` | `server.js`, `09-front-end-dep.yaml` [K8s] |

### 3.2 catalogue

| Depends on | Relationship | Evidence |
|------------|--------------|----------|
| catalogue-db | USES (MySQL :3306) | `cmd/cataloguesvc/main.go` DSN; `netpol-catalogue-db-access.yaml` |

No outbound HTTP calls to other services (read-only catalog service).

### 3.3 carts

| Depends on | Relationship | Evidence |
|------------|--------------|----------|
| carts-db | USES (MongoDB :27017) | `application.properties`; `netpol-cart-db-access.yaml` |

No outbound HTTP calls to other services.

**Called by:** front-end, orders.

### 3.4 orders

| Depends on | Relationship | Endpoint | Evidence |
|------------|--------------|----------|----------|
| user | HTTP GET | `{customer}`, `{address}`, `{card}` URIs from request | `OrdersController.java` [code] [K8s: netpol-user-access] |
| carts | HTTP GET | `{items}` URI from request | `OrdersController.java` [code] [K8s: netpol-cart-access] |
| payment | HTTP POST | `/paymentAuth` | `OrdersConfigurationProperties.java` [code] [K8s: netpol-payment-access] |
| shipping | HTTP POST | `/shipping` | `OrdersConfigurationProperties.java` [code] [K8s: netpol-shipping-access] |
| orders-db | USES (MongoDB :27017) | — | `application.properties`; `netpol-orders-db-access.yaml` |

**Called by:** front-end only (per K8s netpol).

### 3.5 payment

| Depends on | Relationship | Evidence |
|------------|--------------|----------|
| — | Stateless, no DB | `payment/service.go` |

**Called by:** orders only (per K8s netpol).

### 3.6 user *(deploy config only)*

| Depends on | Relationship | Evidence |
|------------|--------------|----------|
| user-db | USES (MongoDB :27017) | `docker-compose.yml` `MONGO_HOST`; `netpol-user-db-access.yaml` |

**Called by:** front-end, orders (per K8s netpol).

### 3.7 shipping *(deploy config only)*

| Depends on | Relationship | Evidence |
|------------|--------------|----------|
| rabbitmq | USES (AMQP :5672) | `netpol-rabbitmq-access.yaml` |

**Called by:** orders (per K8s netpol and `OrdersConfigurationProperties.java`).

### 3.8 queue-master *(deploy config only)*

| Depends on | Relationship | Evidence |
|------------|--------------|----------|
| rabbitmq | USES (AMQP :5672) | `netpol-rabbitmq-access.yaml` |

No inbound HTTP dependencies documented in cloned source.

---

## 4. Reverse Dependency Map (Who depends on X?)

| Service / Asset | Direct dependents | Transitive impact |
|-----------------|-------------------|-------------------|
| **payment** | orders | front-end checkout fails |
| **shipping** | orders | front-end checkout fails |
| **carts** | front-end, orders | Browse cart + checkout blocked |
| **user** | front-end, orders | Login/register + checkout blocked |
| **catalogue** | front-end | Product browse + add-to-cart blocked |
| **orders** | front-end | Checkout + order history blocked |
| **orders-db** | orders | Order persistence fails |
| **carts-db** | carts | All cart operations fail |
| **catalogue-db** | catalogue | Product catalog unavailable |
| **user-db** | user | Auth and profile data unavailable |
| **session-db** | front-end (K8s) | Session persistence fails |
| **rabbitmq** | shipping, queue-master | Async shipping pipeline affected |
| **front-end** | browser users | All user-facing functionality |

---

## 5. Dependency Matrix

Rows = caller, Columns = callee. `●` = confirmed by code and/or K8s netpol.

|  | catalogue | carts | orders | payment | shipping | user | catalogue-db | carts-db | orders-db | user-db | session-db | rabbitmq |
|--|:---------:|:-----:|:------:|:-------:|:--------:|:----:|:------------:|:--------:|:---------:|:-------:|:----------:|:--------:|
| **edge-router** | | | | | | | | | | | | |
| **front-end** | ● | ● | ● | | | ● | | | | | ● | |
| **catalogue** | | | | | | | ● | | | | | |
| **carts** | | | | | | | | ● | | | | |
| **orders** | | ● | | ● | ● | ● | | | ● | | | |
| **payment** | | | | | | | | | | | | |
| **user** | | | | | | | | | | ● | | |
| **shipping** | | | | | | | | | | | | ● |
| **queue-master** | | | | | | | | | | | | ● |

---

## 6. Critical Path: Checkout

The checkout dependency chain is the highest-risk path for latency and availability incidents.

```
front-end
  │
  ├─[1]─► user/customers/{id}          (sequential)
  ├─[2]─► user/addresses               (parallel with card)
  ├─[3]─► user/cards                   (parallel with address)
  │
  └─[4]─► orders POST /orders
            │
            ├─[5a]─► GET user/customer   ─┐
            ├─[5b]─► GET user/address      ─┤ parallel (5s timeout each)
            ├─[5c]─► GET user/card         ─┤
            └─[5d]─► GET carts/.../items   ─┘
            │
            ├─[6]─► POST payment/paymentAuth   (blocking)
            ├─[7]─► POST shipping/shipping     (blocking)
            └─[8]─► SAVE orders-db
```

**Depth:** 8 sequential/parallel steps from browser to persistence.
**Timeout:** 5 seconds per async call in orders (`http.timeout:5`).
**Failure isolation:** Payment decline returns 406; no order saved. Timeout throws `IllegalStateException`.

---

## 7. Critical Path: Add to Cart

```
front-end POST /cart
  ├─[1]─► catalogue GET /catalogue/{id}   (fetch price)
  └─[2]─► carts POST /carts/{customerId}/items
            └─ USES carts-db
```

---

## 8. Critical Path: Login + Cart Merge

```
front-end GET /login
  ├─[1]─► user GET /login
  └─[2]─► carts GET /carts/{customerId}/merge?sessionId={sessionId}
```

Same merge pattern on `POST /register` (`api/user/index.js`).

---

## 9. Failure Propagation Map

### If payment changes or fails

| Impact area | Reason |
|-------------|--------|
| orders checkout | Direct HTTP dependency on `POST /paymentAuth` |
| front-end checkout | Proxies to orders |
| orders-db | Unaffected until payment succeeds (order not saved on decline) |

### If carts fails

| Impact area | Reason |
|-------------|--------|
| front-end cart UI | Direct HTTP to carts |
| orders checkout | Fetches items URI during `POST /orders` |
| login/register | Cart merge calls carts (login continues even if merge fails) |

### If orders fails

| Impact area | Reason |
|-------------|--------|
| front-end checkout | `POST /orders` proxied to orders service |
| front-end order history | `GET /orders/search/customerId` |
| payment, shipping | Not called (orders is the orchestrator) |

### If catalogue-db fails

| Impact area | Reason |
|-------------|--------|
| catalogue `/health` | DB status = `err` |
| front-end product pages | catalogue returns errors |
| add-to-cart | Price lookup from catalogue fails |

---

## 10. Network Policy Validation

K8s network policies (`deploy/kubernetes/manifests-policy/`) enforce the following ingress rules. These align with code-derived dependencies:

| Target | Allowed callers | Port |
|--------|-----------------|------|
| catalogue | front-end | 80 |
| carts | front-end, orders | 80 |
| orders | front-end | 80 |
| payment | orders | 80 |
| shipping | orders | 80 |
| user | front-end, orders | 80 |
| catalogue-db | catalogue | 3306 |
| carts-db | carts | 27017 |
| orders-db | orders | 27017 |
| user-db | user | 27017 |
| rabbitmq | shipping, queue-master | 5672 |

Source: `netpol-*-access.yaml` files in infrastructure repo.

---

## 11. Neo4j Import Preview

Suggested node IDs and edges for future graph ingestion:

```cypher
// Services
(frontend:Service {id: "service:front-end", language: "nodejs"})
(catalogue:Service {id: "service:catalogue", language: "go"})
(carts:Service {id: "service:carts", language: "java"})
(orders:Service {id: "service:orders", language: "java"})
(payment:Service {id: "service:payment", language: "go"})
(user:Service {id: "service:user", language: "nodejs"})
(shipping:Service {id: "service:shipping", language: "java"})

// Databases
(catalogueDb:Database {id: "db:catalogue-db", engine: "mysql"})
(cartsDb:Database {id: "db:carts-db", engine: "mongodb"})
(ordersDb:Database {id: "db:orders-db", engine: "mongodb"})
(userDb:Database {id: "db:user-db", engine: "mongodb"})
(sessionDb:Database {id: "db:session-db", engine: "redis"})
(rabbitmq:Queue {id: "queue:rabbitmq", engine: "rabbitmq"})

// Service dependencies
(frontend)-[:CALLS]->(catalogue)
(frontend)-[:CALLS]->(carts)
(frontend)-[:CALLS]->(orders)
(frontend)-[:CALLS]->(user)
(frontend)-[:USES]->(sessionDb)
(orders)-[:CALLS {endpoint: "POST /paymentAuth"}]->(payment)
(orders)-[:CALLS {endpoint: "POST /shipping"}]->(shipping)
(orders)-[:CALLS]->(carts)
(orders)-[:CALLS]->(user)
(catalogue)-[:USES]->(catalogueDb)
(carts)-[:USES]->(cartsDb)
(orders)-[:USES]->(ordersDb)
(user)-[:USES]->(userDb)
(shipping)-[:USES]->(rabbitmq)
```

---

## 12. Source File Index

| Dependency | Source file |
|------------|-------------|
| Front-end → backend URLs | `services/front-end/api/endpoints.js` |
| Front-end → catalogue/carts/orders/user routes | `services/front-end/api/{catalogue,cart,orders,user}/index.js` |
| Orders → payment/shipping URIs | `services/orders/.../OrdersConfigurationProperties.java` |
| Orders → user/carts/payment/shipping calls | `services/orders/.../OrdersController.java` |
| Catalogue → MySQL | `services/catalogue/cmd/cataloguesvc/main.go` |
| Carts → MongoDB | `services/carts/src/main/resources/application.properties` |
| Orders → MongoDB | `services/orders/src/main/resources/application.properties` |
| User → MongoDB | `infrastructure/.../docker-compose.yml` |
| K8s ingress rules | `infrastructure/.../manifests-policy/netpol-*.yaml` |
| Full runtime service list | `infrastructure/.../docker-compose.yml` |
