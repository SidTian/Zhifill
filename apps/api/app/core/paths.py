from __future__ import annotations

from pathlib import Path

from app.core.config import get_config


def data_root() -> Path:
    root = get_config().data_dir
    root.mkdir(parents=True, exist_ok=True)
    return root


def knowledge_raw_dir() -> Path:
    p = data_root() / "knowledge" / "raw"
    p.mkdir(parents=True, exist_ok=True)
    return p


def forms_raw_dir() -> Path:
    p = data_root() / "forms" / "raw"
    p.mkdir(parents=True, exist_ok=True)
    return p


def exports_dir() -> Path:
    p = data_root() / "exports"
    p.mkdir(parents=True, exist_ok=True)
    return p


def lightrag_dir() -> Path:
    p = data_root() / "lightrag"
    p.mkdir(parents=True, exist_ok=True)
    return p
