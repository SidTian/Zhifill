from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from aff_contracts.ingest import DocumentBundle


class UpsertDocumentRequest(BaseModel):
    bundle: DocumentBundle
    mode: Literal["insert", "reindex"] = "insert"


class UpsertDocumentResult(BaseModel):
    doc_id: str
    status: Literal["ready", "failed"]
    stats: dict[str, Any] | None = None
    error: str | None = None


class DeleteDocumentRequest(BaseModel):
    doc_id: str


class RagQueryRequest(BaseModel):
    query: str = Field(min_length=1)
    mode: Literal["mix", "hybrid", "local", "global", "naive"] = "mix"
    subject_hint: Literal["self"] = "self"
    response_format: Literal["text", "json_object"] = "text"


class RagContext(BaseModel):
    content: str
    doc_id: str | None = None
    score: float | None = None
    entities: list[str] | None = None


class RagQueryResult(BaseModel):
    answer: str
    contexts: list[RagContext] = Field(default_factory=list)
    raw: Any | None = None
