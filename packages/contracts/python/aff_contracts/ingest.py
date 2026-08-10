from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from aff_contracts.common import FileRef


class ChunkHint(BaseModel):
    text: str
    heading: str | None = None
    page: int | None = None
    sheet: str | None = None


class TableBlock(BaseModel):
    name: str | None = None
    headers: list[str]
    rows: list[list[str]]


class DocumentBundle(BaseModel):
    doc_id: str
    title: str
    media_type: str
    text: str = Field(min_length=1)
    chunks_hint: list[ChunkHint] | None = None
    tables: list[TableBlock] | None = None
    metadata: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)


class IngestRequest(BaseModel):
    doc_id: str
    file: FileRef
    source: Literal["knowledge"] = "knowledge"
    options: dict[str, Any] = Field(default_factory=lambda: {"language": "auto"})
