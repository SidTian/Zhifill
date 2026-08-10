from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Settings(BaseModel):
    llm_provider: Literal["openai_compatible", "ollama"] = "ollama"
    llm_api_base: str = "http://127.0.0.1:11434/v1"
    llm_api_key: str | None = None
    llm_model: str = "qwen2.5:7b"
    embedding_model: str = "nomic-embed-text"
    extract_model: str | None = None
    query_model: str | None = None
    max_table_rows: int = Field(default=50, ge=1)
    summary_language: str = "Chinese"
