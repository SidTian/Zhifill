"""P4: PDF writer — not implemented (Phase 0)."""

from app.core.errors import NotImplementedModule


def write_pdf(source_path: str, fields: list, output_path: str):  # type: ignore[no-untyped-def]
    raise NotImplementedModule("export.writers.pdf", "write_pdf")
