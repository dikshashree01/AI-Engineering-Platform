"""Agent configuration from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AgentConfig:
    openai_api_key: str | None
    openai_model: str
    use_llm_synthesis: bool

    @classmethod
    def from_env(cls) -> AgentConfig:
        api_key = os.getenv("OPENAI_API_KEY") or None
        return cls(
            openai_api_key=api_key,
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            use_llm_synthesis=bool(api_key) and os.getenv("AGENT_USE_LLM", "true").lower() == "true",
        )
