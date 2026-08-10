from __future__ import annotations

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse

from app.core.errors import not_implemented

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.post("/upload")
async def upload_knowledge(
    file: UploadFile = File(...),
    doc_id: str | None = None,
) -> JSONResponse:
    _ = (file, doc_id)
    return not_implemented("knowledge", "upload")


@router.get("")
def list_knowledge() -> JSONResponse:
    return not_implemented("knowledge", "list")


@router.get("/{doc_id}")
def get_knowledge(doc_id: str) -> JSONResponse:
    _ = doc_id
    return not_implemented("knowledge", "get")


@router.delete("/{doc_id}")
def delete_knowledge(doc_id: str) -> JSONResponse:
    _ = doc_id
    return not_implemented("knowledge", "delete")


@router.get("/{doc_id}/status")
def knowledge_status(doc_id: str) -> JSONResponse:
    _ = doc_id
    return not_implemented("knowledge", "status")


@router.post("/query")
def query_knowledge() -> JSONResponse:
    return not_implemented("knowledge", "query")
