from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("AFF_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AFF_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("AFF_LLM_API_BASE", "http://127.0.0.1:11434/v1")
    monkeypatch.setenv("AFF_LLM_MODEL", "qwen2.5:7b")
    monkeypatch.setenv("AFF_EMBEDDING_MODEL", "nomic-embed-text")
    return TestClient(app)


def test_get_settings_defaults(client: TestClient) -> None:
    res = client.get("/api/settings")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["llm_provider"] == "ollama"
    assert body["llm_api_base"] == "http://127.0.0.1:11434/v1"
    assert body["llm_model"] == "qwen2.5:7b"
    assert body["embedding_model"] == "nomic-embed-text"
    assert body["max_table_rows"] == 50
    assert body["summary_language"] == "Chinese"


def test_put_and_get_persists(client: TestClient, tmp_path: Path) -> None:
    payload = {
        "llm_provider": "openai_compatible",
        "llm_api_base": "https://api.example.com/v1",
        "llm_api_key": "sk-test-key",
        "llm_model": "gpt-4o-mini",
        "embedding_model": "text-embedding-3-small",
        "extract_model": "gpt-4o-mini",
        "query_model": None,
        "max_table_rows": 20,
        "summary_language": "Chinese",
    }
    put = client.put("/api/settings", json=payload)
    assert put.status_code == 200, put.text
    assert put.json()["llm_model"] == "gpt-4o-mini"
    assert put.json()["llm_api_key"] == "sk-test-key"

    path = tmp_path / "settings.json"
    assert path.is_file()
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["llm_provider"] == "openai_compatible"
    assert stored["max_table_rows"] == 20

    got = client.get("/api/settings")
    assert got.status_code == 200
    assert got.json() == put.json()


def test_put_rejects_invalid_provider(client: TestClient) -> None:
    res = client.put(
        "/api/settings",
        json={
            "llm_provider": "not-a-provider",
            "llm_api_base": "http://x",
            "llm_model": "m",
            "embedding_model": "e",
        },
    )
    assert res.status_code == 422


def test_put_rejects_bad_max_rows(client: TestClient) -> None:
    res = client.put(
        "/api/settings",
        json={
            "llm_provider": "ollama",
            "llm_api_base": "http://127.0.0.1:11434/v1",
            "llm_model": "qwen2.5:7b",
            "embedding_model": "nomic-embed-text",
            "max_table_rows": 0,
        },
    )
    assert res.status_code == 422
