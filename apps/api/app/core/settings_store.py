"""Persist runtime Settings under data/settings.json (统筹)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aff_contracts import Settings

from app.core.config import get_config
from app.core.paths import data_root

_PROVIDERS = frozenset({"openai_compatible", "ollama"})


def settings_path() -> Path:
    return data_root() / "settings.json"


def default_settings() -> Settings:
    cfg = get_config()
    provider = cfg.llm_provider if cfg.llm_provider in _PROVIDERS else "ollama"
    return Settings(
        llm_provider=provider,  # type: ignore[arg-type]
        llm_api_base=cfg.llm_api_base,
        llm_api_key=cfg.llm_api_key,
        llm_model=cfg.llm_model,
        embedding_model=cfg.embedding_model,
        max_table_rows=cfg.max_table_rows,
    )


def load_settings() -> Settings:
    path = settings_path()
    if not path.is_file():
        return default_settings()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default_settings()
    if not isinstance(raw, dict):
        return default_settings()
    base = default_settings().model_dump()
    base.update({k: v for k, v in raw.items() if k in Settings.model_fields})
    return Settings.model_validate(base)


def save_settings(settings: Settings) -> Settings:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = settings.model_dump(mode="json")
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return settings
