from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AFF_", env_file=".env", extra="ignore")

    env: str = "dev"
    data_dir: Path = Path("./data")
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    max_upload_mb: int = 50
    max_table_rows: int = 50

    llm_provider: str = "ollama"
    llm_api_base: str = "http://127.0.0.1:11434/v1"
    llm_api_key: str | None = None
    llm_model: str = "qwen2.5:7b"
    embedding_model: str = "nomic-embed-text"


def get_config() -> AppConfig:
    return AppConfig()
