from __future__ import annotations

from pathlib import Path

from docx import Document
from openpyxl import load_workbook
from pypdf import PdfReader

from aff_contracts import DocumentBundle, IngestRequest
from aff_contracts.ingest import TableBlock
from app.core.errors import NotImplementedModule
from app.modules.ingest.port import IngestPort


class IngestService(IngestPort):
    def ingest(self, request: IngestRequest) -> DocumentBundle:
        path = Path(request.file.path)
        suffix = path.suffix.lower()

        # 默认情况下没有结构化表格
        tables: list[TableBlock] | None = None

        # TXT / Markdown
        if suffix in {".txt", ".md"}:
            text = path.read_text(encoding="utf-8").strip()

        # Word
        elif suffix == ".docx":
            document = Document(path)

            paragraphs = [
                paragraph.text.strip()
                for paragraph in document.paragraphs
                if paragraph.text.strip()
            ]

            text = "\n".join(paragraphs).strip()

        # Excel
        elif suffix == ".xlsx":
            workbook = load_workbook(
                path,
                data_only=False,
                read_only=True,
            )

            sheet_texts = []
            tables = []

            try:
                for sheet in workbook.worksheets:
                    sheet_rows: list[list[str]] = []

                    for row in sheet.iter_rows(values_only=True):
                        values = [
                            str(value).strip() if value is not None else ""
                            for value in row
                        ]

                        if any(values):
                            sheet_rows.append(values)

                    if sheet_rows:
                        # 生成文本视图
                        rows_as_text = [
                            "\t".join(row)
                            for row in sheet_rows
                        ]

                        sheet_texts.append(
                            f"[Sheet: {sheet.title}]\n"
                            + "\n".join(rows_as_text)
                        )

                        # 生成结构化表格
                        tables.append(
                            TableBlock(
                                name=sheet.title,
                                headers=sheet_rows[0],
                                rows=sheet_rows[1:],
                            )
                        )

                text = "\n\n".join(sheet_texts).strip()

            finally:
                workbook.close()

        # PDF
        elif suffix == ".pdf":
            reader = PdfReader(path)

            pages = []

            for page in reader.pages:
                page_text = page.extract_text()

                if page_text:
                    page_text = page_text.strip()

                    if page_text:
                        pages.append(page_text)

            text = "\n\n".join(pages).strip()

        # 暂未支持的文件类型
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
            tables=tables,
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
