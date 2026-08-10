from __future__ import annotations

from typing import Protocol, runtime_checkable

from aff_contracts import FillResult, ParseFormRequest, ParseFormResult
from aff_contracts.fill import FillFormRequest

from app.modules.rag.port import RagPort


@runtime_checkable
class FillPort(Protocol):
    """P3: parse blank forms + fill via RagPort queries."""

    def parse(self, request: ParseFormRequest) -> ParseFormResult:
        """Extract FormField[] including locators for export."""
        ...

    def fill(self, request: FillFormRequest, rag: RagPort) -> FillResult:
        """Query RAG for each field / multi-row table; no KG write-back.

        No evidence → value=null, confidence=0.
        """
        ...
