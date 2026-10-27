from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from urllib.parse import quote

from fastapi import APIRouter, Body, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from app.core.errors import error_body, not_implemented
from app.core.paths import data_root
from app.modules.export.service import filled_name, write_filled_copy
from app.modules.form_structure.service import get_form_structure_service
from app.modules.orchestrator import storage
from app.modules.rag.service import get_rag_service
from app.modules.task_semantics.service import get_task_semantics_service

_EMPTY_VALUES = {"无", "没有", "未知", "无法确定", "未找到", "没有相关信息", "无证据"}

router = APIRouter(prefix="/api/forms", tags=["forms"])

_PARSE_SUFFIXES = {".docx", ".xlsx"}
_FIELD_TYPES = {"text", "date", "number", "single_choice", "multi", "other"}


def _preview_field(raw: dict[str, Any]) -> dict[str, Any]:
    locator = raw.get("locator") if isinstance(raw.get("locator"), dict) else {}
    kind = raw.get("field_type")
    if kind == "select":
        field_type = "single_choice"
    elif kind in _FIELD_TYPES:
        field_type = kind
    else:
        field_type = "text"
    name = str(raw.get("name") or "").strip() or "未命名"
    return {
        "id": raw.get("id"),
        "name": name,
        "field_type": field_type,
        "value": None,
        "original_value": None,
        "required": False,
        "confidence": None,
        "sources": [],
        "status": "empty",
        "layout": "label_value",
        "row_group_id": None,
        "row_index": locator.get("row"),
        "column_key": None,
        "locator": locator,
        "notes": raw.get("fill_kind"),
    }


def _apply_structure(record: dict[str, Any]) -> dict[str, Any]:
    path = data_root() / str(record.get("path") or "")
    suffix = Path(str(record.get("filename") or path.name)).suffix.lower()
    record_id = str(record["id"])
    if suffix not in _PARSE_SUFFIXES:
        notes = ["当前只解析 .docx 和 .xlsx，此文件已保存，未识别字段"]
        updated = storage.update_record(
            "forms",
            record_id,
            {
                "step": "uploaded",
                "fields": [],
                "structure_notes": notes,
                "note": notes[0],
            },
        )
        return updated or record
    try:
        parsed = get_form_structure_service().parse_structure(
            str(path),
            filename=str(record.get("filename") or path.name),
        )
    except Exception as exc:
        notes = [f"文件已保存，结构解析失败：{exc}"]
        updated = storage.update_record(
            "forms",
            record_id,
            {
                "step": "uploaded",
                "fields": [],
                "structure_notes": notes,
                "note": notes[0],
            },
        )
        return updated or record
    task_spec = get_task_semantics_service().build_task_spec(parsed)
    by_id = {
        item.get("field_id"): item
        for item in task_spec.get("fields") or []
        if isinstance(item, dict)
    }
    fields = []
    for item in parsed.get("fields") or []:
        if not isinstance(item, dict):
            continue
        preview = _preview_field(item)
        aligned = by_id.get(item.get("id"))
        if aligned:
            label = str(aligned.get("label") or "").strip()
            if label and label != "未命名":
                preview["name"] = label
            if aligned.get("status") == "aligned":
                preview["notes"] = f"{aligned.get('entity')}.{aligned.get('attribute')}"
            else:
                preview["notes"] = "未对齐"
        fields.append(preview)
    notes = [str(item) for item in (parsed.get("structure_notes") or [])]
    aligned_count = sum(1 for item in by_id.values() if item.get("status") == "aligned")
    if not fields:
        notes.append("未识别到可填写位置。只把空格和模板填空栏当作字段。")
    else:
        notes.append(f"已对齐 {aligned_count}/{len(fields)} 个字段")
    title = str(parsed.get("title") or record.get("title") or "")
    updated = storage.update_record(
        "forms",
        record_id,
        {
            "step": "parsed",
            "fields": fields,
            "task_spec": task_spec,
            "structure_notes": notes,
            "title": title or record.get("title"),
            "note": "；".join(notes) if notes else "已解析填写位置",
        },
    )
    return updated or record


@router.post("/upload")
async def upload_form(file: UploadFile = File(...)) -> JSONResponse:
    raw = await file.read()
    try:
        record = await storage.save_upload_bytes(
            kind="forms",
            filename=file.filename or "form.bin",
            content=raw,
            content_type=file.content_type,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=error_body("invalid_upload", str(e)),
        ) from e
    record = _apply_structure(record)
    return JSONResponse(status_code=201, content=storage.public_view(record))


@router.get("/jobs")
def list_jobs() -> list[dict]:
    return [storage.public_view(x) for x in storage.list_records("forms")]


@router.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    record = storage.get_record("forms", job_id)
    if not record:
        raise HTTPException(
            status_code=404,
            detail=error_body("not_found", f"job {job_id} not found"),
        )
    return storage.public_view(record)


@router.delete("/jobs/{job_id}")
def delete_job(job_id: str) -> dict:
    ok = storage.delete_record("forms", job_id)
    if not ok:
        raise HTTPException(
            status_code=404,
            detail=error_body("not_found", f"job {job_id} not found"),
        )
    return {"ok": True, "id": job_id}


_CITE = re.compile(r"\s*\[\d+\]")
_AFTER_VALUE = re.compile(r"(?:是|为)\s*[:：]?\s*(.+)$")


def _cell_value(answer: str, has_context: bool) -> str | None:
    if not has_context:
        return None
    text = answer.replace("**", "").replace("*", "")
    text = re.split(r"#{2,}|References", text, maxsplit=1, flags=re.I)[0]
    text = _CITE.sub("", text)
    lines = [line.strip(" -\t") for line in text.splitlines() if line.strip()]
    text = lines[0] if lines else ""
    found = list(_AFTER_VALUE.finditer(text))
    if found:
        text = found[-1].group(1)
    text = text.strip(" \"'“”：:。.,，#")
    text = re.sub(r"（[^）]*）", "", text).strip()
    if not text or text in _EMPTY_VALUES:
        return None
    if text.startswith("无法") or "未找到" in text or "没有相关" in text:
        return None
    if "根据" in text or "材料" in text:
        phone = re.search(r"1\d{10}", text)
        if phone:
            return phone.group(0)
        return None
    return text[:200]


def _apply_suggestion(item: dict[str, Any], result: Any) -> dict[str, Any]:
    value = _cell_value(result.answer, bool(result.contexts))
    if value is None:
        item["value"] = None
        item["status"] = "empty"
        item["confidence"] = None
        item["sources"] = []
        return item
    item["value"] = value
    item["status"] = "suggested"
    item["confidence"] = result.contexts[0].score
    item["sources"] = [
        {"doc_id": ctx.doc_id, "snippet": ctx.content, "score": ctx.score}
        for ctx in result.contexts
    ]
    return item


@router.post("/jobs/{job_id}/fill")
async def fill_job(job_id: str, field_id: str = Query(...)) -> dict:
    record = storage.get_record("forms", job_id)
    if not record:
        raise HTTPException(
            status_code=404,
            detail=error_body("not_found", f"job {job_id} not found"),
        )
    spec_fields = (record.get("task_spec") or {}).get("fields") or []
    spec = next(
        (item for item in spec_fields if isinstance(item, dict) and item.get("field_id") == field_id),
        None,
    )
    fields = [dict(item) for item in record.get("fields") or [] if isinstance(item, dict)]
    index = next((i for i, item in enumerate(fields) if item.get("id") == field_id), None)
    if index is None:
        raise HTTPException(
            status_code=404,
            detail=error_body("not_found", f"field {field_id} not found"),
        )
    item = fields[index]
    query = str(spec.get("query")) if spec and spec.get("status") == "aligned" and spec.get("query") else ""
    if not query:
        label = str(item.get("name") or "该字段").strip() or "该字段"
        query = f"{label}是什么"
    attribute = str(spec.get("attribute") or item.get("name") or "") if spec else str(item.get("name") or "")
    try:
        result = await get_rag_service().aquery_value(query, attribute=attribute)
    except Exception as exc:
        item["value"] = None
        item["status"] = "empty"
        item["confidence"] = None
        item["sources"] = []
        item["notes"] = f"查询失败：{exc}"
        result = None
    if result is not None:
        item = _apply_suggestion(item, result)
    fields[index] = item
    aligned_ids = {
        entry.get("field_id")
        for entry in spec_fields
        if isinstance(entry, dict) and entry.get("status") == "aligned"
    }
    done = all(
        field.get("status") in {"suggested", "confirmed", "manual"} or field.get("id") not in aligned_ids
        for field in fields
    )
    updated = storage.update_record(
        "forms",
        job_id,
        {
            "fields": fields,
            "step": "filled" if done else record.get("step") or "parsed",
            "note": "已生成填写建议" if item.get("value") else record.get("note"),
        },
    )
    view = storage.public_view(updated or record)
    view["field"] = item
    return view


def _sync_field_notes(fields: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    structure = {
        "fields": [
            {
                "id": item.get("id"),
                "name": item.get("name") or "",
                "locator": item.get("locator") or {},
            }
            for item in fields
        ]
    }
    spec = get_task_semantics_service().build_task_spec(structure)
    by_id = {
        item.get("field_id"): item
        for item in spec.get("fields") or []
        if isinstance(item, dict)
    }
    synced: list[dict[str, Any]] = []
    for item in fields:
        next_item = dict(item)
        aligned = by_id.get(item.get("id"))
        if aligned and aligned.get("status") == "aligned":
            next_item["notes"] = f"{aligned.get('entity')}.{aligned.get('attribute')}"
        elif aligned:
            next_item["notes"] = "未对齐"
        synced.append(next_item)
    return synced, spec


@router.patch("/jobs/{job_id}/fields")
def patch_fields(job_id: str, body: dict[str, Any] = Body(...)) -> dict:
    record = storage.get_record("forms", job_id)
    if not record:
        raise HTTPException(
            status_code=404,
            detail=error_body("not_found", f"job {job_id} not found"),
        )
    raw_fields = body.get("fields")
    if not isinstance(raw_fields, list):
        raise HTTPException(
            status_code=400,
            detail=error_body("invalid_fields", "fields 必须是数组"),
        )
    fields = [item for item in raw_fields if isinstance(item, dict) and item.get("id")]
    synced, spec = _sync_field_notes(fields)
    updated = storage.update_record(
        "forms",
        job_id,
        {"fields": synced, "task_spec": spec},
    )
    return storage.public_view(updated or record)


@router.post("/jobs/{job_id}/export")
def export_job(job_id: str) -> dict:
    record = storage.get_record("forms", job_id)
    if not record:
        raise HTTPException(
            status_code=404,
            detail=error_body("not_found", f"job {job_id} not found"),
        )
    source = data_root() / str(record.get("path") or "")
    if not source.is_file():
        raise HTTPException(
            status_code=404,
            detail=error_body("not_found", "原始表格不存在"),
        )
    filename = str(record.get("filename") or source.name)
    if source.suffix.lower() not in {".docx", ".xlsx"}:
        raise HTTPException(
            status_code=400,
            detail=error_body("unsupported_format", "当前只回填 .docx 和 .xlsx"),
        )
    try:
        dest, written = write_filled_copy(source, filename, list(record.get("fields") or []))
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=error_body("export_failed", f"回填失败：{exc}"),
        ) from exc
    output_name = filled_name(filename)
    updated = storage.update_record(
        "forms",
        job_id,
        {
            "step": "exported",
            "export_path": str(dest.relative_to(data_root())),
            "note": f"已回填 {written} 个字段",
        },
    )
    view = storage.public_view(updated or record)
    view["download_name"] = output_name
    view["written"] = written
    return view


@router.get("/jobs/{job_id}/download")
def download_job(job_id: str) -> FileResponse:
    record = storage.get_record("forms", job_id)
    if not record:
        raise HTTPException(
            status_code=404,
            detail=error_body("not_found", f"job {job_id} not found"),
        )
    rel = str(record.get("export_path") or "")
    path = data_root() / rel if rel else None
    if path is None or not path.is_file():
        raise HTTPException(
            status_code=404,
            detail=error_body("not_found", "还没有可下载的回填文件"),
        )
    filename = filled_name(str(record.get("filename") or path.name))
    return FileResponse(
        path,
        filename=filename,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )
