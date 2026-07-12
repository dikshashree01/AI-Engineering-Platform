# INC-001: Checkout Latency Spike After Orders Deployment

| Field | Value |
|-------|-------|
| **ID** | INC-001 |
| **Severity** | SEV-2 |
| **Status** | resolved |
| **Started** | 2026-03-15T14:22:00Z |
| **Resolved** | 2026-03-15T16:45:00Z |
| **Duration** | 2h 23m |

## Summary

Checkout p99 latency increased from ~800ms to ~6.2s after deploying `weaveworksdemos/orders:0.4.8`. Users experienced timeouts during payment submission. No data loss occurred; failed checkouts returned HTTP 500/408 from the front-end BFF.

## Impact

- **Affected services:** front-end, orders, payment (downstream latency)
- **User impact:** ~12% checkout failure rate during incident window
- **Revenue impact:** Estimated 340 abandoned carts

## Timeline

| Time (UTC) | Event |
|------------|-------|
| 14:22 | Alert: `checkout_latency_p99 > 5s` fires |
| 14:28 | On-call confirms spike correlates with orders deployment |
| 14:35 | Dependency graph shows orders → payment → shipping chain |
| 14:50 | Root cause identified: orders `http.timeout` reduced from 10s to 5s in new image |
| 15:10 | Mitigation: rollback orders to `0.4.7` |
| 16:45 | Latency returns to baseline; incident closed |

## Root Cause

Orders service `0.4.8` deployment changed the default `http.timeout` property from 10 seconds to 5 seconds. Under load, parallel fetches to user, carts, payment, and shipping occasionally exceeded 5s, triggering `TimeoutException` in `OrdersController.newOrder()`.

**Evidence:** `orders/src/main/java/works/weave/socks/orders/controllers/OrdersController.java` — `@Value("${http.timeout:5}")`

## Services Involved

```
front-end → orders → [user, carts, payment, shipping] → orders-db
```

## Remediation

1. Rolled back orders deployment to `0.4.7`
2. Added integration test for checkout under load (follow-up ticket ORD-142)
3. Updated runbook: [checkout-latency](../runbooks/checkout-latency.md)

## Action Items

- [ ] Add deployment checklist item: verify timeout configs
- [ ] Add distributed tracing on checkout path (Zipkin)
- [ ] Consider circuit breaker for payment/shipping calls

## Related

- Runbook: `engineering-data/runbooks/checkout-latency.md`
- Owner: Cart & Orders Team (`#team-orders`)
