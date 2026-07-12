# Sock Shop — System Analysis

> Evidence-based analysis of repositories present in this workspace.
> Last updated from source inspection of `source-repo/infrastructure/microservices-demo` and `source-repo/services/*`.

---

## 1. Workspace Inventory

### Repositories present locally

| Repository | Path | Source available |
|------------|------|------------------|
| Infrastructure | `source-repo/infrastructure/microservices-demo/` | Deploy configs, design docs, K8s manifests |
| Front-end | `source-repo/services/front-end/` | Full source (Node.js) |
| Catalogue | `source-repo/services/catalogue/` | Full source (Go) |
| Carts | `source-repo/services/carts/` | Full source (Java) |
| Orders | `source-repo/services/orders/` | Full source (Java) |
| Payment | `source-repo/services/payment/` | Full source (Go) |

### Services deployed but not cloned locally

These appear in `deploy/docker-compose/docker-compose.yml` as container images only. Dependencies are inferred from infrastructure manifests and cross-service call sites in cloned repos.

| Service | Image | Env evidence |
|---------|-------|--------------|
| user | `weaveworksdemos/user:0.4.4` | `MONGO_HOST=user-db:27017` |
| shipping | `weaveworksdemos/shipping:0.4.8` | Called by orders at `http://shipping/shipping` |
| queue-master | `weaveworksdemos/queue-master:0.3.1` | K8s netpol: connects to rabbitmq:5672 |

---

## 2. Architecture Summary

From `internal-docs/design.md`:

- Microservices map to e-commerce functions (catalogue, cart, orders, payment, etc.).
- **All services communicate using REST over HTTP.**
- Intentionally polyglot: Spring Boot, Go kit, Node.js (`README.md`).

From `deploy/docker-compose/docker-compose.yml`, the runtime stack includes **14 containers** (12 application/infrastructure + load-test simulator).

---

## 3. Service Catalog

| Service | Language / Framework | Hostname | Image (compose) | Database / Queue |
|---------|---------------------|----------|-----------------|------------------|
| edge-router | Nginx (image only) | edge-router | `weaveworksdemos/edge-router:0.1.1` | — |
| front-end | Node.js / Express | front-end | `weaveworksdemos/front-end:0.3.12` | Redis (`session-db`, K8s only) |
| catalogue | Go / Go kit | catalogue | `weaveworksdemos/catalogue:0.3.5` | MySQL (`catalogue-db`, db: `socksdb`) |
| carts | Java / Spring Boot | carts | `weaveworksdemos/carts:0.4.8` | MongoDB (`carts-db`, db: `data`) |
| orders | Java / Spring Boot | orders | `weaveworksdemos/orders:0.4.7` | MongoDB (`orders-db`, db: `data`) |
| payment | Go / Go kit | payment | `weaveworksdemos/payment:0.4.3` | — (stateless) |
| user | Node.js (image only) | user | `weaveworksdemos/user:0.4.4` | MongoDB (`user-db`) |
| shipping | Java / Spring Boot (image only) | shipping | `weaveworksdemos/shipping:0.4.8` | RabbitMQ |
| queue-master | Java / Spring Boot (image only) | queue-master | `weaveworksdemos/queue-master:0.3.1` | RabbitMQ |
| rabbitmq | RabbitMQ | rabbitmq | `rabbitmq:3.6.8` | — |
| user-sim | Load test | user-simulator | `weaveworksdemos/load-test:0.1.1` | — |

### Port references (from source)

| Service | Port | Source |
|---------|------|--------|
| front-end | 8079 | `server.js`: `process.env.PORT \|\| 8079` |
| edge-router | 80, 8080 | `docker-compose.yml` |
| catalogue | 80 (deploy), 8080 (local compose) | `catalogue/cmd/cataloguesvc/main.go`, `catalogue/docker-compose.yml` |
| carts | 8081 (local) | `carts/src/main/resources/application.properties` |
| orders | 8082 (local) | `orders/src/main/resources/application.properties` |
| payment | 8080 (local default) | `payment/cmd/paymentsvc/main.go` |

---

## 4. Databases & Messaging

| Asset | Engine | Connection / Config | Used by | Source |
|-------|--------|---------------------|---------|--------|
| catalogue-db | MySQL | `catalogue-db:3306/socksdb` | catalogue | `catalogue/cmd/cataloguesvc/main.go` DSN default; `docker-compose.yml` `MYSQL_DATABASE=socksdb` |
| carts-db | MongoDB | `mongodb://carts-db:27017/data` | carts | `carts/application.properties` |
| orders-db | MongoDB | `mongodb://orders-db:27017/data` | orders | `orders/application.properties` |
| user-db | MongoDB | `user-db:27017` | user | `docker-compose.yml` `MONGO_HOST=user-db:27017` |
| session-db | Redis | port 6379 | front-end | `manifests/21-session-db-dep.yaml` (`redis:alpine`); `09-front-end-dep.yaml` `SESSION_REDIS=true` |
| rabbitmq | RabbitMQ | port 5672 | shipping, queue-master | `netpol-rabbitmq-access.yaml` |

> **Note:** Carts uses **MongoDB**, not Redis. Redis is used by front-end for session storage in Kubernetes deployments.

---

## 5. API Surface

### 5.1 Front-end (BFF routes → backend services)

Source: `front-end/api/*.js`, `front-end/api/endpoints.js`

**Backend URL configuration** (`endpoints.js`):

| Config key | Target |
|------------|--------|
| `catalogueUrl` | `http://catalogue` |
| `tagsUrl` | `http://catalogue/tags` |
| `cartsUrl` | `http://carts/carts` |
| `ordersUrl` | `http://orders` |
| `customersUrl` | `http://user/customers` |
| `addressUrl` | `http://user/addresses` |
| `cardsUrl` | `http://user/cards` |
| `loginUrl` | `http://user/login` |
| `registerUrl` | `http://user/register` |

**Exposed BFF routes:**

| Route | Method | Calls |
|-------|--------|-------|
| `/catalogue*`, `/catalogue/images*` | GET | catalogue |
| `/tags` | GET | catalogue |
| `/cart` | GET | carts `GET /carts/{customerId}/items` |
| `/cart` | POST | catalogue `GET /catalogue/{id}`, then carts `POST /carts/{customerId}/items` |
| `/cart` | DELETE | carts `DELETE /carts/{customerId}` |
| `/cart/:id` | DELETE | carts `DELETE /carts/{customerId}/items/{itemId}` |
| `/cart/update` | POST | catalogue + carts `PATCH /carts/{customerId}/items` |
| `/orders` | GET | orders `GET /orders/search/customerId` |
| `/orders` | POST | user (customer, address, card) + orders `POST /orders` |
| `/orders/*` | GET | orders (proxy) |
| `/register` | POST | user + carts merge |
| `/login` | GET | user + carts merge |
| `/customers`, `/addresses`, `/cards` | GET/POST/DELETE | user |
| `/metrics` | GET | local Prometheus metrics |

### 5.2 Catalogue

Source: `catalogue/endpoints.go`, `catalogue/api-spec/catalogue.json`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/catalogue` | List products |
| GET | `/catalogue/{id}` | Get product by ID |
| GET | `/catalogue/size` | Product count |
| GET | `/tags` | List tags |
| GET | `/health` | Health check (includes catalogue-db ping) |

### 5.3 Carts

Source: `carts/controllers/CartsController.java`, `carts/controllers/ItemsController.java`, `carts/api-spec/carts.json`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/carts/{customerId}` | Get cart |
| DELETE | `/carts/{customerId}` | Delete cart |
| GET | `/carts/{customerId}/merge?sessionId=` | Merge session cart into customer cart |
| GET | `/carts/{customerId}/items` | List items |
| GET | `/carts/{customerId}/items/{itemId}` | Get item |
| POST | `/carts/{customerId}/items` | Add item |
| PATCH | `/carts/{customerId}/items` | Update item |
| DELETE | `/carts/{customerId}/items/{itemId}` | Remove item |
| GET | `/health` | Health check (includes carts-db ping) |

### 5.4 Orders

Source: `orders/controllers/OrdersController.java`, `orders/api-spec/orders.json`

| Method | Path | Description |
|--------|------|-------------|
| POST | `/orders` | Create order (orchestrates checkout) |
| GET | `/orders` | List orders (Spring Data REST) |
| GET | `/orders/search/customerId` | Search by customer (used by front-end) |
| GET | `/health` | Health check (includes orders-db ping) |

**Outbound calls during `POST /orders`** (from `OrdersController.java`, `OrdersConfigurationProperties.java`):

| Target | Method | Path | Purpose |
|--------|--------|------|---------|
| user | GET | URIs from request body (`customer`, `address`, `card`) | Fetch checkout entities |
| carts | GET | URI from request body (`items`) | Fetch cart line items |
| payment | POST | `/paymentAuth` | Authorize payment |
| shipping | POST | `/shipping` | Create shipment |

### 5.5 Payment

Source: `payment/service.go`, `payment/endpoints.go`, `payment/api-spec/payment.json`

| Method | Path | Description |
|--------|------|-------------|
| POST | `/paymentAuth` | Authorize payment amount |
| GET | `/health` | Health check |

**Authorization rule** (`payment/service.go`, `payment/cmd/paymentsvc/main.go`):
- Declines if amount is 0 or negative.
- Authorizes if `amount <= declineOverAmount`.
- Default `declineOverAmount`: **105** (binary flag `-decline`).
- Helm chart override: **200** (`deploy/kubernetes/helm-chart/values.yaml` `declinePaymentsOverAmount: 200`).

---

## 6. Service Dependencies

Derived from **source code call sites** and validated against **K8s network policies** (`deploy/kubernetes/manifests-policy/`).

| Caller | Callee | Evidence |
|--------|--------|----------|
| front-end | catalogue | `endpoints.js`, `api/cart/index.js`, `netpol-catalogue-access.yaml` |
| front-end | carts | `endpoints.js`, `api/cart/index.js`, `netpol-cart-access.yaml` |
| front-end | orders | `endpoints.js`, `api/orders/index.js`, `netpol-orders-access.yaml` |
| front-end | user | `endpoints.js`, `api/user/index.js`, `netpol-user-access.yaml` |
| orders | carts | `OrdersController.java` (items URI), `netpol-cart-access.yaml` |
| orders | user | `OrdersController.java` (customer/address/card URIs), `netpol-user-access.yaml` |
| orders | payment | `OrdersConfigurationProperties.getPaymentUri()`, `netpol-payment-access.yaml` |
| orders | shipping | `OrdersConfigurationProperties.getShippingUri()`, `netpol-shipping-access.yaml` |
| catalogue | catalogue-db | `main.go` DSN, `netpol-catalogue-db-access.yaml` (port 3306) |
| carts | carts-db | `application.properties`, `netpol-cart-db-access.yaml` (port 27017) |
| orders | orders-db | `application.properties`, `netpol-orders-db-access.yaml` (port 27017) |
| user | user-db | `docker-compose.yml`, `netpol-user-db-access.yaml` (port 27017) |
| shipping | rabbitmq | `netpol-rabbitmq-access.yaml` (port 5672) |
| queue-master | rabbitmq | `netpol-rabbitmq-access.yaml` (port 5672) |
| front-end | session-db | `09-front-end-dep.yaml` `SESSION_REDIS=true`; `21-session-db-dep.yaml` |

---

## 7. Checkout Flow

Step-by-step, traced from `front-end/api/orders/index.js` and `orders/controllers/OrdersController.java`.

```
1. Browser → front-end POST /orders
   └─ Requires logged_in cookie (front-end/api/orders/index.js)

2. front-end fetches user data:
   ├─ GET http://user/customers/{custId}
   ├─ GET address link from customer._links.addresses
   └─ GET card link from customer._links.cards
   └─ Builds payload:
      {
        "customer": "<user customer href>",
        "address":  "<user address href>",
        "card":     "<user card href>",
        "items":    "http://carts/carts/{custId}/items"
      }

3. front-end → orders POST /orders (above payload)

4. orders (parallel async fetches, 5s timeout each):
   ├─ GET customer URI
   ├─ GET address URI
   ├─ GET card URI
   └─ GET items URI (carts)

5. orders calculates total:
   sum(quantity × unitPrice) + 4.99 shipping
   (OrdersController.calculateTotal)

6. orders → payment POST /paymentAuth
   └─ If not authorised → PaymentDeclinedException → HTTP 406

7. orders → shipping POST /shipping
   └─ Body: Shipment(customerId)

8. orders saves CustomerOrder → orders-db
   └─ Returns HTTP 201 with saved order
```

---

## 8. Data Models (from source)

### Cart (`carts/entities/Cart.java`, `carts/entities/Item.java`)

- `Cart`: MongoDB `@Document`, keyed by `customerId`, contains `@DBRef` list of `Item`.
- `Item`: `itemId`, `quantity`, `unitPrice`.

### Order (`orders/entities/CustomerOrder.java`)

- Fields: `id`, `customerId`, `customer`, `address`, `card`, `items`, `shipment`, `date`, `total`.
- Persisted as MongoDB `@Document`.

### Product (`catalogue/service.go` — `Sock` struct)

- Fields: `id`, `name`, `description`, `imageUrl`, `price`, `count`, `tag`.
- SQL tables: `sock`, `tag`, `sock_tag` (from `service.go` queries).

---

## 9. Potential Failure Points

All items below are directly supported by source code or deploy configs.

### 9.1 Checkout path (highest impact)

| Failure | Effect | Source |
|---------|--------|--------|
| user service down | front-end cannot fetch customer/address/card; checkout blocked | `front-end/api/orders/index.js` |
| carts service down | orders cannot fetch items; checkout blocked | `OrdersController.java` line 71–76 |
| payment service down / slow | orders timeout or 406; order not saved | `OrdersController.java` lines 85–97, 121–122 |
| payment declines (amount > threshold) | HTTP 406, order not saved | `payment/service.go`, `OrdersController.java` line 95–96 |
| shipping service down / slow | orders timeout; order not saved | `OrdersController.java` lines 101–103, 121–122 |
| orders-db down | order cannot persist after successful payment/shipping | `OrdersController.java` line 117 |
| Any parallel fetch exceeds 5s | `TimeoutException` → checkout fails | `OrdersController.java` `@Value("${http.timeout:5}")` |

### 9.2 Browse / cart path

| Failure | Effect | Source |
|---------|--------|--------|
| catalogue down | Product listing and add-to-cart fail (price lookup) | `front-end/api/cart/index.js` lines 77–80 |
| catalogue-db down | catalogue `/health` reports DB error | `catalogue/service.go` Health() |
| carts-db down | cart read/write fails; health reports error | `carts/HealthCheckController.java` |
| front-end down | All UI and BFF routes unavailable | `server.js` |

### 9.3 Auth / session path

| Failure | Effect | Source |
|---------|--------|--------|
| user login/register fails | Cannot authenticate; checkout requires login | `front-end/api/orders/index.js` lines 50–54 |
| session-db down (K8s) | Session persistence fails when `SESSION_REDIS=true` | `server.js` lines 22–24, `09-front-end-dep.yaml` |
| user-db down | user service cannot serve customer data | `docker-compose.yml`, `netpol-user-db-access.yaml` |

### 9.4 Async / messaging path

| Failure | Effect | Source |
|---------|--------|--------|
| rabbitmq down | shipping and queue-master lose queue connectivity | `netpol-rabbitmq-access.yaml` |
| queue-master down | Queue monitoring/autoscaling demo affected | `docker-compose.yml` (mounts docker.sock) |

> **Note:** Checkout calls shipping **synchronously** over HTTP before saving the order. RabbitMQ failure impact on checkout depends on shipping service implementation (source not cloned).

---

## 10. Repository → Change Map

| Change | Repository | Key files |
|--------|------------|-----------|
| UI / BFF routing | `services/front-end/` | `server.js`, `api/*` |
| Product catalog | `services/catalogue/` | `service.go`, `endpoints.go` |
| Cart logic | `services/carts/` | `controllers/`, `entities/` |
| Checkout orchestration | `services/orders/` | `OrdersController.java` |
| Payment rules | `services/payment/` | `service.go`, `cmd/paymentsvc/main.go` |
| Deployment / networking | `infrastructure/microservices-demo/` | `deploy/docker-compose/`, `deploy/kubernetes/` |

---

## 11. Evidence Index

| Claim | Primary source file |
|-------|---------------------|
| Service list & images | `infrastructure/.../docker-compose.yml` |
| REST over HTTP | `infrastructure/.../internal-docs/design.md` |
| Front-end backend URLs | `services/front-end/api/endpoints.js` |
| Checkout orchestration | `services/orders/.../OrdersController.java` |
| Payment/shipping URIs | `services/orders/.../OrdersConfigurationProperties.java` |
| Payment decline threshold | `services/payment/service.go`, `payment/cmd/paymentsvc/main.go` |
| MongoDB for carts/orders | `services/carts/application.properties`, `services/orders/application.properties` |
| MySQL for catalogue | `services/catalogue/cmd/cataloguesvc/main.go` |
| K8s allowed traffic | `infrastructure/.../manifests-policy/netpol-*.yaml` |
| Redis sessions (K8s) | `infrastructure/.../manifests/09-front-end-dep.yaml`, `21-session-db-dep.yaml` |
