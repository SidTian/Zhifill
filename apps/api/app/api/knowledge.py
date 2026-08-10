from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.core.errors import error_body, not_implemented
from app.modules.orchestrator import storage

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.post("/upload")
async def upload_knowledge(
    file: UploadFile = File(...),
    doc_id: str | None = Form(default=None),
) -> JSONResponse:
    raw = await file.read()
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
def delete_knowledge(doc_id: str) -> dict:
    ok = storage.delete_record("knowledge", doc_id)
    if not ok:
        raise HTTPException(
            status_code=404,
            detail=error_body("not_found", f"knowledge {doc_id} not found"),
        )
    return {"ok": True, "id": doc_id}


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
def query_knowledge() -> JSONResponse:
    return not_implemented("knowledge", "query")
