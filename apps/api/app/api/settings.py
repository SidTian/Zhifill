from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.errors import not_implemented

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def get_settings() -> JSONResponse:
    return not_implemented("settings", "get")


@router.put("")
def put_settings() -> JSONResponse:
    return not_implemented("settings", "put")
