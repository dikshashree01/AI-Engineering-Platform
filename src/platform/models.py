"""Shared response models for API and MCP."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Natural language engineering question")


class AskResponse(BaseModel):
    query: str
    intent: str | None
    service: str | None
    evidence_count: int
    answer: str


class HealthResponse(BaseModel):
    status: str
    neo4j: bool
    qdrant: bool
