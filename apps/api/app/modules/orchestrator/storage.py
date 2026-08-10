"""Upload storage (统筹): save original files under data/, keep JSON indexes.

Does not run 1.1–2.2 business logic — only落盘 + 元数据.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.config import get_config
from app.core.paths import data_root, forms_raw_dir, knowledge_raw_dir


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_filename(name: str) -> str:
    base = Path(name).name
    base = base.replace("\x00", "")
    base = re.sub(r"[^\w.\- ()\u4e00-\u9fff]+", "_", base, flags=re.UNICODE)
    base = base.strip(" ._") or "upload.bin"
    return base[:180]


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _index_path(kind: str) -> Path:
    if kind == "knowledge":
        return knowledge_raw_dir().parent / "index.json"
    if kind == "forms":
        return forms_raw_dir().parent / "index.json"
    raise ValueError(kind)


def _load_index(kind: str) -> list[dict[str, Any]]:
    path = _index_path(kind)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _save_index(kind: str, items: list[dict[str, Any]]) -> None:
    path = _index_path(kind)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(items, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _guess_format(filename: str) -> str:
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext in {"xlsx", "xls"}:
        return "xlsx"
    if ext == "pdf":
        return "pdf"
    if ext in {"docx", "doc"}:
        return "docx"
    if ext in {"md", "markdown"}:
        return "md"
    if ext == "txt":
        return "txt"
    return ext or "bin"


def max_upload_bytes() -> int:
    return get_config().max_upload_mb * 1024 * 1024


async def save_upload_bytes(
    *,
    kind: str,
    filename: str,
    content: bytes,
    content_type: str | None,
    doc_id: str | None = None,
) -> dict[str, Any]:
    if not filename or not filename.strip():
        raise ValueError("filename is required")
    if len(content) == 0:
        raise ValueError("empty file")
    limit = max_upload_bytes()
    if len(content) > limit:
        raise ValueError(f"file exceeds limit ({get_config().max_upload_mb} MB)")

    safe = _safe_filename(filename)
    record_id = doc_id.strip() if doc_id and doc_id.strip() else str(uuid4())
    digest = _sha256_bytes(content)
    media = content_type or "application/octet-stream"
    fmt = _guess_format(safe)

    if kind == "knowledge":
        dest_dir = knowledge_raw_dir() / record_id
    elif kind == "forms":
        dest_dir = forms_raw_dir() / record_id
    else:
        raise ValueError(kind)

    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file = dest_dir / safe
    dest_file.write_bytes(content)

    rel = str(dest_file.relative_to(data_root())).replace("\\", "/")

    if kind == "knowledge":
        record: dict[str, Any] = {
            "id": record_id,
            "title": Path(safe).stem,
            "filename": safe,
            "media_type": media,
            "format": fmt,
            "status": "stored",
            "size": len(content),
            "sha256": digest,
            "path": rel,
            "created_at": _now(),
            "updated_at": _now(),
            "note": "original file stored; 1.1/2.1 not run yet",
        }
        items = [x for x in _load_index("knowledge") if x.get("id") != record_id]
        items.insert(0, record)
        _save_index("knowledge", items)
        return record

    record = {
        "id": record_id,
        "title": Path(safe).stem,
        "filename": safe,
        "media_type": media,
        "format": fmt if fmt in {"docx", "xlsx", "pdf"} else "docx",
        "status": "stored",
        "step": "uploaded",
        "size": len(content),
        "sha256": digest,
        "path": rel,
        "created_at": _now(),
        "updated_at": _now(),
        "fields": [],
        "note": "original file stored; 1.2/1.3/2.2 not run yet",
    }
    items = [x for x in _load_index("forms") if x.get("id") != record_id]
    items.insert(0, record)
    _save_index("forms", items)
    return record


def list_records(kind: str) -> list[dict[str, Any]]:
    return _load_index(kind)


def get_record(kind: str, record_id: str) -> dict[str, Any] | None:
    for item in _load_index(kind):
        if item.get("id") == record_id:
            return item
    return None


def delete_record(kind: str, record_id: str) -> bool:
    items = _load_index(kind)
    found = [x for x in items if x.get("id") == record_id]
    if not found:
        return False
    if kind == "knowledge":
        dest_dir = knowledge_raw_dir() / record_id
    else:
        dest_dir = forms_raw_dir() / record_id
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    _save_index(kind, [x for x in items if x.get("id") != record_id])
    return True


def public_view(record: dict[str, Any]) -> dict[str, Any]:
    """API response: relative path only (no machine-local abs_path)."""
    out = dict(record)
    out.pop("abs_path", None)
    return out
