from __future__ import annotations

from aff_contracts import ExportRequest, ExportResult

from app.core.errors import NotImplementedModule
from app.modules.export.port import ExportPort


class ExportService(ExportPort):
    def export(self, request: ExportRequest) -> ExportResult:
        raise NotImplementedModule("export", "export")


def get_export_service() -> ExportPort:
    return ExportService()
