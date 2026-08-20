from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
FIXTURES = ROOT / "packages" / "contracts" / "fixtures"
SCHEMAS = ROOT / "packages" / "contracts" / "jsonschema"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def validator_cls():
    jsonschema = pytest.importorskip("jsonschema")
    return jsonschema.Draft202012Validator


def test_success_document_bundle(validator_cls) -> None:
    schema = _load(SCHEMAS / "document_bundle.schema.json")
    data = _load(FIXTURES / "success" / "document_bundle.json")
    validator_cls(schema).validate(data)


def test_success_form_field(validator_cls) -> None:
    schema = _load(SCHEMAS / "form_field.schema.json")
    data = _load(FIXTURES / "success" / "form_field.json")
    validator_cls(schema).validate(data)


def test_failure_empty_text_invalid(validator_cls) -> None:
    schema = _load(SCHEMAS / "document_bundle.schema.json")
    data = _load(FIXTURES / "failure" / "document_bundle_empty_text.json")
    errors = list(validator_cls(schema).iter_errors(data))
    assert errors, "empty text fixture must fail schema validation"


def test_pydantic_document_bundle() -> None:
    from aff_contracts import DocumentBundle

    data = _load(FIXTURES / "success" / "document_bundle.json")
    bundle = DocumentBundle.model_validate(data)
    assert bundle.doc_id == "doc_resume_001"
    assert len(bundle.text) > 0


def test_pydantic_form_field() -> None:
    from aff_contracts import FormField

    data = _load(FIXTURES / "success" / "form_field.json")
    field = FormField.model_validate(data)
    assert field.locator.kind == "excel_cell"


def test_success_form_structure(validator_cls) -> None:
    schema = _load(SCHEMAS / "form_structure.schema.json")
    data = _load(FIXTURES / "success" / "form_structure.json")
    validator_cls(schema).validate(data)


def test_pydantic_form_structure() -> None:
    from aff_contracts import FormStructureResult

    data = _load(FIXTURES / "success" / "form_structure.json")
    result = FormStructureResult.model_validate(data)
    assert result.format == "docx"
    assert result.title == "暑期社会实践活动项目申报表"
    assert len(result.fields) == 8
    assert result.fields[0].locator.kind == "word_cell"
    # 验证 fill_kind 字段
    template_fields = [f for f in result.fields if f.fill_kind == "template"]
    empty_fields = [f for f in result.fields if f.fill_kind == "empty"]
    assert len(template_fields) == 3  # 活动时间 + 实践基地 + 辅导员意见
    assert len(empty_fields) == 5     # 项目名称 + 姓名/性别/政治面貌/联系方式


def test_health_endpoint() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_unimplemented_routes_are_501() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    assert client.get("/api/settings").status_code == 501
    assert client.post("/api/knowledge/query").status_code == 501
    # upload/list 已由统筹 storage 实现
    assert client.get("/api/knowledge").status_code == 200
    assert client.get("/api/forms/jobs").status_code == 200
    assert client.post("/api/forms/jobs/x/fill").status_code == 501
