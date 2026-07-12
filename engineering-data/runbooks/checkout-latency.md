# Runbook: Checkout Latency Investigation

| Field | Value |
|-------|-------|
| **Trigger** | `checkout_latency_p99 > 3s`, user reports slow checkout, checkout timeout errors |
| **Severity** | SEV-2 (upgrade to SEV-1 if failure rate > 25%) |
| **Owner** | Cart & Orders Team — `#team-orders` |
| **Related services** | front-end, orders, payment, shipping, user, carts |

## Symptoms

- Users report checkout hanging or failing
- Front-end returns HTTP 500 or timeout errors on `POST /orders`
- Grafana dashboard shows elevated p99 on orders service
- Payment success rate may drop (orders never reaches payment, or payment times out)

## Dependency Chain (investigate in this order)

```
Browser
  → front-end POST /orders
      → user (customer, address, card)
      → orders POST /orders
           ├─ GET user resources    (parallel, 5s timeout each)
           ├─ GET carts/.../items   (parallel)
           ├─ POST payment/paymentAuth
           ├─ POST shipping/shipping
           └─ SAVE orders-db
```

## Investigation Steps

### 1. Confirm scope (5 min)

- [ ] Check checkout error rate in dashboards
- [ ] Identify time window of degradation
- [ ] Check recent deployments: `orders`, `payment`, `shipping`, `user`, `carts`, `front-end`

### 2. Check service health (5 min)

```bash
# Health endpoints (when Sock Shop is running locally)
curl http://orders/health
curl http://payment/health
curl http://carts/health
curl http://catalogue/health
```

- [ ] Any service reporting `"status": "err"` for its database?
- [ ] Any pod restarts or OOM kills in Kubernetes?

### 3. Trace the critical path (10 min)

| Service | What to check |
|---------|---------------|
| **orders** | Logs for `TimeoutException`, `Unable to create order due to timeout` |
| **payment** | Latency on `POST /paymentAuth`; decline rate spikes |
| **shipping** | Latency on `POST /shipping` |
| **user** | Latency on customer/address/card GET during checkout |
| **carts** | Latency on `GET /carts/{id}/items` |
| **orders-db** | MongoDB connection errors, disk I/O |

### 4. Check recent changes (10 min)

- [ ] Compare deployed image tags vs previous version (docker-compose / K8s manifests)
- [ ] Review config changes: `http.timeout`, `JAVA_OPTS`, resource limits
- [ ] Search incident history for similar patterns (see `engineering-data/incidents/`)

### 5. Mitigation options

| Action | When to use |
|--------|-------------|
| **Rollback orders** | Recent orders deployment correlates with spike |
| **Rollback payment** | Payment `/paymentAuth` latency elevated |
| **Scale orders replicas** | CPU/memory saturation on orders pods |
| **Restart carts-db / orders-db** | Database health check failing |
| **Increase orders timeout** | Confirmed timeout-related failures (config change) |

## Rollback Procedure

```bash
# Kubernetes example — revert orders deployment
kubectl set image deployment/orders orders=weaveworksdemos/orders:0.4.7 -n sock-shop
kubectl rollout status deployment/orders -n sock-shop
```

Verify checkout latency returns to baseline within 10 minutes.

## Escalation

| Condition | Escalate to |
|-----------|-------------|
| Failure rate > 25% for 15 min | SEV-1, page Cart & Orders lead |
| Database corruption suspected | Platform + DBA |
| Payment provider issue | Payments Team `#team-payments` |

## Post-Incident

- [ ] File postmortem in `engineering-data/incidents/`
- [ ] Update this runbook if new failure mode discovered
- [ ] Add regression test for checkout under load
