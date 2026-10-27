from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from aff_contracts import (
    DeleteDocumentRequest,
    DocumentBundle,
    FileRef,
    IngestRequest,
    RagQueryRequest,
    UpsertDocumentRequest,
)

from app.core.errors import error_body
from app.core.paths import data_root
from app.modules.ingest.service import get_ingest_service
from app.modules.orchestrator import storage
from app.modules.rag.service import get_rag_service

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


def _apply_ingest(record: dict[str, Any]) -> dict[str, Any]:
    record_id = str(record["id"])
    path = data_root() / str(record.get("path") or "")
    request = IngestRequest(
        doc_id=record_id,
        file=FileRef(
            path=str(path),
            filename=str(record.get("filename") or path.name),
            mime=str(record.get("media_type") or "application/octet-stream"),
            sha256=str(record.get("sha256") or ""),
            size=int(record.get("size") or 0),
        ),
    )
    try:
        bundle = get_ingest_service().ingest(request)
    except Exception as exc:
        note = f"文件已保存，资料解析失败：{exc}"
        updated = storage.update_record(
            "knowledge",
            record_id,
            {
                "ingest_status": "failed",
                "bundle": None,
                "note": note,
            },
        )
        return updated or record
    updated = storage.update_record(
        "knowledge",
        record_id,
        {
            "ingest_status": "ready",
            "bundle": bundle.model_dump(mode="json"),
            "title": bundle.title or record.get("title"),
            "note": "已解析为 DocumentBundle，尚未写入图谱",
        },
    )
    return updated or record


async def _apply_graph(record: dict[str, Any], mode: str) -> dict[str, Any]:
    record_id = str(record["id"])
    try:
        bundle = DocumentBundle.model_validate(record.get("bundle"))
        result = await get_rag_service().aupsert(
            UpsertDocumentRequest(bundle=bundle, mode=mode),  # type: ignore[arg-type]
        )
    except Exception as exc:
        note = f"文件已解析，写入图谱失败：{exc}"
        updated = storage.update_record(
            "knowledge",
            record_id,
            {"graph_status": "failed", "note": note},
        )
        return updated or record
    if result.status != "ready":
        note = f"文件已解析，写入图谱失败：{result.error or '未知错误'}"
        updated = storage.update_record(
            "knowledge",
            record_id,
            {"graph_status": "failed", "note": note},
        )
        return updated or record
    updated = storage.update_record(
        "knowledge",
        record_id,
        {
            "graph_status": "ready",
            "graph_stats": result.stats,
            "note": "已写入图谱",
        },
    )
    return updated or record


@router.post("/upload")
async def upload_knowledge(
    file: UploadFile = File(...),
    doc_id: str | None = Form(default=None),
) -> JSONResponse:
    raw = await file.read()
    mode = "insert"
    if doc_id and doc_id.strip():
        previous = storage.get_record("knowledge", doc_id.strip())
        if previous and previous.get("graph_status") == "ready":
            mode = "reindex"
    try:
        record = await storage.save_upload_bytes(
            kind="knowledge",
            filename=file.filename or "upload.bin",
            content=raw,
            content_type=file.content_type,
            doc_id=doc_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=error_body("invalid_upload", str(e)),
        ) from e
    record = _apply_ingest(record)
    if record.get("ingest_status") == "ready" and record.get("bundle"):
        record = await _apply_graph(record, mode)
    return JSONResponse(status_code=201, content=storage.public_view(record))


@router.get("")
def list_knowledge() -> list[dict]:
    return [storage.public_view(x) for x in storage.list_records("knowledge")]


@router.get("/{doc_id}")
def get_knowledge(doc_id: str) -> dict:
    record = storage.get_record("knowledge", doc_id)
    if not record:
        raise HTTPException(
            status_code=404,
            detail=error_body("not_found", f"knowledge {doc_id} not found"),
        )
    return storage.public_view(record)


@router.delete("/{doc_id}")
async def delete_knowledge(doc_id: str) -> dict:
    record = storage.get_record("knowledge", doc_id)
    if not record:
        raise HTTPException(
            status_code=404,
            detail=error_body("not_found", f"knowledge {doc_id} not found"),
        )
    graph_deleted = False
    if record.get("graph_status") == "ready":
        try:
            await get_rag_service().adelete(DeleteDocumentRequest(doc_id=doc_id))
            graph_deleted = True
        except Exception:
            graph_deleted = False
    ok = storage.delete_record("knowledge", doc_id)
    if not ok:
        raise HTTPException(
            status_code=404,
            detail=error_body("not_found", f"knowledge {doc_id} not found"),
        )
    return {"ok": True, "id": doc_id, "graph_deleted": graph_deleted}


@router.get("/{doc_id}/status")
def knowledge_status(doc_id: str) -> dict:
    record = storage.get_record("knowledge", doc_id)
    if not record:
        raise HTTPException(
            status_code=404,
            detail=error_body("not_found", f"knowledge {doc_id} not found"),
        )
    return {
        "id": doc_id,
        "status": record.get("status", "stored"),
        "note": record.get("note"),
    }


@router.post("/query")
async def query_knowledge(body: RagQueryRequest) -> dict:
    try:
        result = await get_rag_service().aquery(body)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=error_body("query_failed", f"图谱查询失败：{exc}"),
        ) from exc
    return result.model_dump(mode="json")
