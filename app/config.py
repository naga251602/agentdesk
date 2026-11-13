"""Runtime configuration, all from environment variables (see .env.example)."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    # Confidence below this -> escalate to a human instead of answering.
    escalation_threshold: float = float(os.getenv("AGENTDESK_ESCALATION_THRESHOLD", "0.70"))
    # Chunking: approximate tokens per chunk (1 token ~ 1 word for English prose)
    # and the overlap carried into the next chunk.
    chunk_tokens: int = int(os.getenv("AGENTDESK_CHUNK_TOKENS", "512"))
    chunk_overlap: int = int(os.getenv("AGENTDESK_CHUNK_OVERLAP", "64"))
    top_k: int = int(os.getenv("AGENTDESK_TOP_K", "5"))
    # Optional OpenAI-compatible LLM endpoint (vLLM, llama.cpp server, OpenAI...).
    # When unset, AgentDesk answers extractively from the retrieved chunks, so the
    # whole system runs offline with zero API keys.
    llm_base_url: str = os.getenv("LLM_BASE_URL", "").rstrip("/")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "")
    # Optional JSON file used to persist documents / tickets between restarts.
    state_file: str = os.getenv("AGENTDESK_STATE_FILE", "")


settings = Settings()
