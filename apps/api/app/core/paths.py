from __future__ import annotations

from pathlib import Path

from app.core.config import get_config

# apps/api/app/core/paths.py → repo root = parents[4]
_REPO_ROOT = Path(__file__).resolve().parents[4]


def data_root() -> Path:
    cfg = get_config().data_dir
    if cfg.is_absolute():
        root = cfg
    else:
        # Prefer repo-root ./data so cwd (apps/api vs repo) does not matter
        root = (_REPO_ROOT / cfg).resolve()
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
