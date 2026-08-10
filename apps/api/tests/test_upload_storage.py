from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.orchestrator import storage


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("AFF_DATA_DIR", str(tmp_path))
    # reset cached settings if any — AppConfig reads env each get_config()
    return TestClient(app)


def test_knowledge_upload_list_delete(client: TestClient, tmp_path: Path) -> None:
    files = {"file": ("简历.pdf", b"%PDF-1.4 mock content", "application/pdf")}
    res = client.post("/api/knowledge/upload", files=files)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["filename"] == "简历.pdf"
    assert body["size"] == len(b"%PDF-1.4 mock content")
    assert body["status"] == "stored"
    assert body["sha256"]
    doc_id = body["id"]

    # file on disk under data/knowledge/raw/{id}/
    raw_dir = tmp_path / "knowledge" / "raw" / doc_id
    assert raw_dir.is_dir()
    assert (raw_dir / "简历.pdf").read_bytes().startswith(b"%PDF")

    listed = client.get("/api/knowledge")
    assert listed.status_code == 200
    assert any(x["id"] == doc_id for x in listed.json())

    got = client.get(f"/api/knowledge/{doc_id}")
    assert got.status_code == 200
    assert got.json()["path"].endswith(f"knowledge/raw/{doc_id}/简历.pdf") or "简历.pdf" in got.json()["path"]

    deleted = client.delete(f"/api/knowledge/{doc_id}")
    assert deleted.status_code == 200
    assert not raw_dir.exists()
    assert client.get(f"/api/knowledge/{doc_id}").status_code == 404


def test_forms_upload_keeps_original_bytes(client: TestClient, tmp_path: Path) -> None:
    payload = b"PK\x03\x04 fake-docx-bytes"
    files = {
        "file": (
            "入职表.docx",
            payload,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    }
    res = client.post("/api/forms/upload", files=files)
    assert res.status_code == 201, res.text
    body = res.json()
    job_id = body["id"]
    assert body["format"] == "docx"
    assert body["step"] == "uploaded"
    assert body["fields"] == []

    saved = tmp_path / "forms" / "raw" / job_id / "入职表.docx"
    assert saved.read_bytes() == payload

    jobs = client.get("/api/forms/jobs")
    assert any(j["id"] == job_id for j in jobs.json())


def test_reject_empty_file(client: TestClient) -> None:
    files = {"file": ("empty.txt", b"", "text/plain")}
    res = client.post("/api/knowledge/upload", files=files)
    assert res.status_code == 400


def test_index_json_written(client: TestClient, tmp_path: Path) -> None:
    files = {"file": ("a.txt", b"hello", "text/plain")}
    client.post("/api/knowledge/upload", files=files)
    index = tmp_path / "knowledge" / "index.json"
    assert index.is_file()
    data = json.loads(index.read_text(encoding="utf-8"))
    assert isinstance(data, list) and data[0]["filename"] == "a.txt"
