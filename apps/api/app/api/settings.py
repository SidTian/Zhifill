from __future__ import annotations

from fastapi import APIRouter
from aff_contracts import Settings

from app.core import settings_store

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=Settings)
def get_settings() -> Settings:
    return settings_store.load_settings()


@router.put("", response_model=Settings)
def put_settings(body: Settings) -> Settings:
    return settings_store.save_settings(body)
