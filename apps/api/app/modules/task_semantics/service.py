from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from aff_contracts import TaskField, TaskSpec

from app.modules.task_semantics.port import TaskSemanticsPort

_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "rag" / "personal_kb.schema.json"
_GENERIC_LABELS = {"填写内容", "内容", "值", "填写", "请填写", "未命名", ""}
_CONTEXT_ALIASES = {"名称", "类别", "说明"}


def _norm(text: str) -> str:
    cleaned = text.replace("\u3000", "").replace(" ", "").strip()
    cleaned = re.sub(r"[：:]+$", "", cleaned)
    return cleaned


def _load_schema(path: Path | None = None) -> dict[str, Any]:
    raw = json.loads((path or _SCHEMA_PATH).read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


def _cell_text(structure: dict[str, Any], sheet: str, row: int, col: int) -> str:
    for item in structure.get("sheets") or []:
        if not isinstance(item, dict) or item.get("name") != sheet:
            continue
        for cell in item.get("cells") or []:
            if not isinstance(cell, dict):
                continue
            if cell.get("row") == row and cell.get("col") == col:
                return str(cell.get("text") or "").strip()
    return ""


def _resolve_label(field: dict[str, Any], structure: dict[str, Any]) -> str:
    name = str(field.get("name") or "").strip()
    locator = field.get("locator") if isinstance(field.get("locator"), dict) else {}
    if _norm(name) not in _GENERIC_LABELS:
        return name
    if locator.get("kind") != "excel_cell":
        return name
    sheet = str(locator.get("sheet") or "")
    row = locator.get("row")
    col = locator.get("col")
    if not isinstance(row, int) or not isinstance(col, int) or col <= 1:
        return name
    left = _cell_text(structure, sheet, row, col - 1)
    return left or name


class TaskSemanticsService(TaskSemanticsPort):
    def build_task_spec(
        self,
        structure: dict[str, Any],
        *,
        schema_ref: str | None = None,
    ) -> dict[str, Any]:
        schema = _load_schema()
        version = str(schema.get("version") or "0.1.0")
        ref = schema_ref or f"{schema.get('id') or 'personal_kb'}@{version}"
        unaligned = {_norm(str(item)) for item in schema.get("unaligned") or []}
        exact: dict[str, tuple[str, str]] = {}
        contextual: dict[str, tuple[str, str]] = {}
        for item in schema.get("attributes") or []:
            if not isinstance(item, dict):
                continue
            entity = str(item.get("entity") or "")
            attribute = str(item.get("name") or "")
            if not entity or not attribute:
                continue
            names = [attribute, *[str(alias) for alias in item.get("aliases") or []]]
            for label in names:
                key = _norm(label)
                if not key or key in unaligned:
                    continue
                if key in _CONTEXT_ALIASES:
                    contextual[key] = (entity, attribute)
                else:
                    exact[key] = (entity, attribute)
        fields: list[TaskField] = []
        for raw in structure.get("fields") or []:
            if not isinstance(raw, dict):
                continue
            label = _resolve_label(raw, structure)
            key = _norm(label)
            locator = raw.get("locator") if isinstance(raw.get("locator"), dict) else {}
            row = locator.get("row") if isinstance(locator.get("row"), int) else None
            sheet = str(locator.get("sheet") or "")
            matched = None if key in unaligned or key in _GENERIC_LABELS else exact.get(key)
            if matched is None and key in contextual and "证书" in sheet:
                matched = contextual[key]
            if matched is None:
                fields.append(
                    TaskField(
                        field_id=str(raw.get("id") or ""),
                        label=label or "未命名",
                        status="unaligned",
                        row_index=row,
                    )
                )
                continue
            entity, attribute = matched
            query = f"{entity}的{attribute}是什么"
            if row is not None:
                query = f"第{row}行{query}"
            fields.append(
                TaskField(
                    field_id=str(raw.get("id") or ""),
                    label=label,
                    entity=entity,
                    attribute=attribute,
                    query=query,
                    status="aligned",
                    row_index=row,
                )
            )
        return TaskSpec(schema_ref=ref, fields=fields).model_dump(mode="json")


def get_task_semantics_service() -> TaskSemanticsPort:
    return TaskSemanticsService()
