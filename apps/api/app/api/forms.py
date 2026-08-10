from __future__ import annotations

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse

from app.core.errors import not_implemented

router = APIRouter(prefix="/api/forms", tags=["forms"])


@router.post("/upload")
async def upload_form(file: UploadFile = File(...)) -> JSONResponse:
    _ = file
    return not_implemented("forms", "upload")


@router.get("/jobs")
def list_jobs() -> JSONResponse:
    return not_implemented("forms", "list_jobs")


@router.get("/jobs/{job_id}")
def get_job(job_id: str) -> JSONResponse:
    _ = job_id
    return not_implemented("forms", "get_job")


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
