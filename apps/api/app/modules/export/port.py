from __future__ import annotations

from typing import Protocol, runtime_checkable

from aff_contracts import ExportRequest, ExportResult


@runtime_checkable
class ExportPort(Protocol):
    """P4: write confirmed field values back into original form files."""

    def export(self, request: ExportRequest) -> ExportResult:
        """Write by locator. Reject fields missing locator.

        Flat PDF may return side_files (JSON checklist) if overlay is weak.
        """
        ...
