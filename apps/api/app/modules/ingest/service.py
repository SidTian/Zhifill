from __future__ import annotations

from aff_contracts import DocumentBundle, IngestRequest

from app.core.errors import NotImplementedModule
from app.modules.ingest.port import IngestPort


class IngestService(IngestPort):
    def ingest(self, request: IngestRequest) -> DocumentBundle:
        raise NotImplementedModule("ingest", "ingest")


def get_ingest_service() -> IngestPort:
    return IngestService()
