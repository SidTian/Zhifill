from __future__ import annotations

from typing import Protocol, runtime_checkable

from aff_contracts import (
    DeleteDocumentRequest,
    RagQueryRequest,
    RagQueryResult,
    UpsertDocumentRequest,
    UpsertDocumentResult,
)


@runtime_checkable
class RagPort(Protocol):
    """P2: LightRAG index / delete / query with KG updates."""

    def upsert(self, request: UpsertDocumentRequest) -> UpsertDocumentResult:
        """Insert or reindex a DocumentBundle.

        - mode=insert: merge entities/relations into existing graph
        - mode=reindex (same doc_id): delete old contribution then insert
        """
        ...

    def delete(self, request: DeleteDocumentRequest) -> None:
        """Remove document and clean affected graph nodes/edges."""
        ...

    def query(self, request: RagQueryRequest) -> RagQueryResult:
        """Query knowledge graph + vectors. Default mode mix."""
        ...
