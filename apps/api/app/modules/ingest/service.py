from __future__ import annotations

from pathlib import Path
from docx import Document



from aff_contracts import DocumentBundle, IngestRequest
from app.core.errors import NotImplementedModule
from app.modules.ingest.port import IngestPort


class IngestService(IngestPort):
    def ingest(self, request: IngestRequest) -> DocumentBundle:
        path = Path(request.file.path)

        suffix = path.suffix.lower()

        if suffix in {".txt", ".md"}:
            text = path.read_text(encoding="utf-8").strip()

        elif suffix == ".docx":
            document = Document(path)

            paragraphs = [
                paragraph.text.strip()
                for paragraph in document.paragraphs
                if paragraph.text.strip()
            ]

            text = "\n".join(paragraphs).strip()

        else:
            raise NotImplementedModule(
                "ingest",
                f"unsupported file type: {path.suffix}",
            )


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
