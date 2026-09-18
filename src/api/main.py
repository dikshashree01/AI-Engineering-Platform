"""FastAPI backend for the engineering copilot."""

from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.agents.workflow import run_copilot
from src.platform.health import platform_health
from src.platform.models import AskRequest, AskResponse, HealthResponse

app = FastAPI(
    title="AI Engineering Platform API",
    description="Graph + RAG copilot for Sock Shop engineering intelligence",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    checks = platform_health()
    ok = checks["neo4j"] and checks["qdrant"]
    return HealthResponse(
        status="ok" if ok else "degraded",
        neo4j=checks["neo4j"],
        qdrant=checks["qdrant"],
    )


@app.post("/ask", response_model=AskResponse)
def ask(body: AskRequest) -> AskResponse:
    checks = platform_health()
    if not checks["neo4j"] and not checks["qdrant"]:
        raise HTTPException(
            status_code=503,
            detail="Neo4j and Qdrant are unavailable. Run ./scripts/start-platform.sh",
        )
    result = run_copilot(body.query)
    return AskResponse(**result)


def run() -> None:
    import uvicorn

    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    uvicorn.run("src.api.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    run()
