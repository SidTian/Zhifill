from __future__ import annotations

from typing import Protocol, runtime_checkable

from aff_contracts import DocumentBundle, IngestRequest


@runtime_checkable
class IngestPort(Protocol):
    """P1: knowledge file -> DocumentBundle for RAG."""

    def ingest(self, request: IngestRequest) -> DocumentBundle:
        """Parse and normalize a knowledge file into DocumentBundle.

        Guarantees:
        - bundle.text is non-empty on success
        - Does not call LLM or write to the knowledge graph
        """
        ...
