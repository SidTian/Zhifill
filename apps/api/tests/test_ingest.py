from pathlib import Path

from aff_contracts import FileRef, IngestRequest
from docx import Document

from app.modules.ingest.service import IngestService


def make_request(path: Path, mime: str) -> IngestRequest:
    return IngestRequest(
        doc_id="doc_test_001",
        file=FileRef(
            path=str(path),
            filename=path.name,
            mime=mime,
            sha256="test",
            size=path.stat().st_size,
        ),
    )


def test_ingest_txt(tmp_path: Path) -> None:
    path = tmp_path / "sample.txt"
    path.write_text("这是 TXT 测试。", encoding="utf-8")

    request = make_request(path, "text/plain")
    bundle = IngestService().ingest(request)

    assert bundle.text == "这是 TXT 测试。"
    assert bundle.title == "sample"
    assert bundle.media_type == "text/plain"


def test_ingest_markdown(tmp_path: Path) -> None:
    path = tmp_path / "sample.md"
    path.write_text(
        "# 个人经历\n\n这是 Markdown 测试。",
        encoding="utf-8",
    )

    request = make_request(path, "text/markdown")
    bundle = IngestService().ingest(request)

    assert bundle.text == "# 个人经历\n\n这是 Markdown 测试。"
    assert bundle.title == "sample"
    assert bundle.media_type == "text/markdown"


def test_ingest_docx(tmp_path: Path) -> None:
    path = tmp_path / "sample.docx"

    document = Document()
    document.add_heading("个人经历", level=1)
    document.add_paragraph("赵洋帆就读于湖南大学。")
    document.add_paragraph("负责知识图谱相关项目研究。")
    document.save(path)

    request = make_request(
        path,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    bundle = IngestService().ingest(request)

    assert bundle.text == (
        "个人经历\n"
        "赵洋帆就读于湖南大学。\n"
        "负责知识图谱相关项目研究。"
    )
    assert bundle.title == "sample"
