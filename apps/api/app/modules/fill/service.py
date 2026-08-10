from __future__ import annotations

from aff_contracts import FillResult, ParseFormRequest, ParseFormResult
from aff_contracts.fill import FillFormRequest

from app.core.errors import NotImplementedModule
from app.modules.fill.port import FillPort
from app.modules.rag.port import RagPort


class FillService(FillPort):
    def parse(self, request: ParseFormRequest) -> ParseFormResult:
        raise NotImplementedModule("fill", "parse")

    def fill(self, request: FillFormRequest, rag: RagPort) -> FillResult:
        raise NotImplementedModule("fill", "fill")


def get_fill_service() -> FillPort:
    return FillService()
