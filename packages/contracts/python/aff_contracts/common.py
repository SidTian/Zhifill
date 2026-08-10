from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class FileRef(BaseModel):
    path: str
    filename: str
    mime: str
    sha256: str
    size: int = Field(ge=0)


class SourceRef(BaseModel):
    snippet: str
    doc_id: str | None = None
    score: float | None = None


class ErrorBody(BaseModel):
    code: str
    message: str
    detail: Any | None = None
