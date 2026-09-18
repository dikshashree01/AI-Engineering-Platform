# Evaluation Questions

> Day 1, Step 2: Questions the AI engineering platform should eventually answer correctly.
> These form the initial evaluation dataset for knowledge-base ingestion and retrieval quality.

## Running the evaluation

After Neo4j and Qdrant are running and indexed:

```bash
python3 -m src.agents.run eval --full
./scripts/run-eval.sh
```

Target accuracy: **≥ 90%** across all 22 questions.

---

## Architecture & Overview

1. Explain the architecture to a new engineer joining the team.
2. Which programming languages are used across the microservices?
3. How do services communicate with each other?

## Checkout & Order Flow

4. Explain the checkout flow from browser click to order confirmation.
5. Which services are involved in checkout?
6. What happens if the payment service fails or declines a transaction?
7. How does the orders service calculate the order total?

## Service Ownership & Dependencies

8. Which service owns payment processing?
9. Which service owns the shopping cart?
10. What services does the front-end call directly?
11. What services depend on the orders service?

## Data Storage

12. Which database stores shopping carts?
13. Where is catalogue information stored?
14. Does the carts service use Redis or MongoDB? Explain.
15. What is session-db used for?

## Failure & Impact Analysis

16. What breaks if the carts service goes down?
17. What breaks if the payment service goes down?
18. Can a customer browse products if the user service is unavailable?

## Code & Repository Navigation

19. Which repository should I modify to add discount support at checkout?
20. Which repository should I modify to change payment decline rules?
21. Where are the front-end's backend service URLs configured?

## API & Data Model

22. How does the front-end merge an anonymous cart into a logged-in user's cart after login?
