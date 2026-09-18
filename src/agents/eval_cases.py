"""Evaluation dataset — 22 questions from docs/evaluation_questions.md."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EvalCase:
    id: int
    category: str
    question: str
    # Each inner list is an OR-group: at least one term must appear in the response.
    must_contain_any: list[list[str]] = field(default_factory=list)
    expected_intent: str | None = None


EVAL_CASES: list[EvalCase] = [
    EvalCase(
        1,
        "Architecture",
        "Explain the architecture to a new engineer joining the team.",
        [["microservice", "service"], ["front-end", "catalogue", "checkout"]],
        "explain",
    ),
    EvalCase(
        2,
        "Architecture",
        "Which programming languages are used across the microservices?",
        [["java", "go", "node"], ["spring", "polyglot"]],
        "explain",
    ),
    EvalCase(
        3,
        "Architecture",
        "How do services communicate with each other?",
        [["rest", "http"], ["communicat"]],
        "general",
    ),
    EvalCase(
        4,
        "Checkout",
        "Explain the checkout flow from browser click to order confirmation.",
        [["checkout", "order"], ["front-end", "payment", "orders"]],
        "checkout",
    ),
    EvalCase(
        5,
        "Checkout",
        "Which services are involved in checkout?",
        [["orders", "payment"], ["front-end", "carts", "shipping"]],
        "checkout",
    ),
    EvalCase(
        6,
        "Checkout",
        "What happens if the payment service fails or declines a transaction?",
        [["payment", "declin", "fail"], ["order", "checkout"]],
        "failure",
    ),
    EvalCase(
        7,
        "Checkout",
        "How does the orders service calculate the order total?",
        [["orders", "total"], ["cart", "shipping", "payment"]],
        "explain",
    ),
    EvalCase(
        8,
        "Ownership",
        "Which service owns payment processing?",
        [["payment"], ["payments team", "team:payments"]],
        "ownership",
    ),
    EvalCase(
        9,
        "Ownership",
        "Which service owns the shopping cart?",
        [["carts"], ["cart", "orders team", "team:cart"]],
        "ownership",
    ),
    EvalCase(
        10,
        "Dependencies",
        "What services does the front-end call directly?",
        [["front-end"], ["catalogue", "orders", "carts", "user"]],
        "dependencies",
    ),
    EvalCase(
        11,
        "Dependencies",
        "What services depend on the orders service?",
        [["front-end"], ["depend"]],
        "dependents",
    ),
    EvalCase(
        12,
        "Data Storage",
        "Which database stores shopping carts?",
        [["mongodb", "mongo"], ["carts-db", "carts"]],
        "database",
    ),
    EvalCase(
        13,
        "Data Storage",
        "Where is catalogue information stored?",
        [["mysql", "catalogue-db"], ["catalogue", "socksdb"]],
        "database",
    ),
    EvalCase(
        14,
        "Data Storage",
        "Does the carts service use Redis or MongoDB? Explain.",
        [["mongodb", "mongo"], ["not redis", "redis"]],
        "database",
    ),
    EvalCase(
        15,
        "Data Storage",
        "What is session-db used for?",
        [["session", "redis"], ["front-end", "session-db"]],
        "database",
    ),
    EvalCase(
        16,
        "Failure",
        "What breaks if the carts service goes down?",
        [["carts"], ["checkout", "cart", "front-end"]],
        "impact",
    ),
    EvalCase(
        17,
        "Failure",
        "What breaks if the payment service goes down?",
        [["payment"], ["checkout", "order"]],
        "impact",
    ),
    EvalCase(
        18,
        "Failure",
        "Can a customer browse products if the user service is unavailable?",
        [["catalogue", "browse", "product"], ["user"]],
        "availability",
    ),
    EvalCase(
        19,
        "Repository",
        "Which repository should I modify to add discount support at checkout?",
        [["orders", "repository", "repo"], ["source-repo", "services/orders"]],
        "repository",
    ),
    EvalCase(
        20,
        "Repository",
        "Which repository should I modify to change payment decline rules?",
        [["payment", "repository", "repo"], ["source-repo", "services/payment"]],
        "repository",
    ),
    EvalCase(
        21,
        "Repository",
        "Where are the front-end's backend service URLs configured?",
        [["endpoints", "front-end"], ["catalogue", "url", "http"]],
        "repository",
    ),
    EvalCase(
        22,
        "API",
        "How does the front-end merge an anonymous cart into a logged-in user's cart after login?",
        [["cart", "merge"], ["login", "anonymous", "carts"]],
        "explain",
    ),
]
