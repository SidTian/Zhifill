from __future__ import annotations

from aff_contracts import (
    DeleteDocumentRequest,
    RagQueryRequest,
    RagQueryResult,
    UpsertDocumentRequest,
    UpsertDocumentResult,
)

from app.core.errors import NotImplementedModule
from app.modules.rag.port import RagPort


class RagService(RagPort):
    def upsert(self, request: UpsertDocumentRequest) -> UpsertDocumentResult:
        raise NotImplementedModule("rag", "upsert")

    def delete(self, request: DeleteDocumentRequest) -> None:
        raise NotImplementedModule("rag", "delete")

    def query(self, request: RagQueryRequest) -> RagQueryResult:
        raise NotImplementedModule("rag", "query")


def get_rag_service() -> RagPort:
    return RagService()
