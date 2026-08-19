from __future__ import annotations

from pathlib import Path

from aff_contracts import DocumentBundle, IngestRequest
from app.core.errors import NotImplementedModule
from app.modules.ingest.port import IngestPort


class IngestService(IngestPort):
    def ingest(self, request: IngestRequest) -> DocumentBundle:
        path = Path(request.file.path)

        if path.suffix.lower() != ".txt":
            raise NotImplementedModule("ingest", f"unsupported file type: {path.suffix}")

        text = path.read_text(encoding="utf-8").strip()

        return DocumentBundle(
            doc_id=request.doc_id,
            title=path.stem,
            media_type=request.file.mime,
            text=text,
            metadata={
                "filename": request.file.filename,
                "mime": request.file.mime,
                "sha256": request.file.sha256,
                "size": request.file.size,
            },
            warnings=[],
        )


def get_ingest_service() -> IngestPort:
    return IngestService()
