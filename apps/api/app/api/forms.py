from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.core.errors import error_body, not_implemented
from app.modules.orchestrator import storage

router = APIRouter(prefix="/api/forms", tags=["forms"])


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


@router.post("/jobs/{job_id}/fill")
def fill_job(job_id: str) -> JSONResponse:
    _ = job_id
    return not_implemented("forms", "fill")


@router.patch("/jobs/{job_id}/fields")
def patch_fields(job_id: str) -> JSONResponse:
    _ = job_id
    return not_implemented("forms", "patch_fields")


@router.post("/jobs/{job_id}/export")
def export_job(job_id: str) -> JSONResponse:
    _ = job_id
    return not_implemented("forms", "export")


@router.get("/jobs/{job_id}/download")
def download_job(job_id: str) -> JSONResponse:
    _ = job_id
    return not_implemented("forms", "download")
