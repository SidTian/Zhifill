from aff_contracts import DocumentBundle

from app.modules.rag.service import answer_from_query_raw, bundle_to_text, contexts_from_query_raw


def test_bundle_to_text_prefixes_title() -> None:
    bundle = DocumentBundle(
        doc_id="doc-1",
        title="能力证书清单",
        media_type="text/plain",
        text="姓名：张三",
        metadata={"filename": "能力证书清单.txt"},
    )
    assert bundle_to_text(bundle) == "能力证书清单\n\n姓名：张三"


def test_query_raw_maps_answer_and_chunks() -> None:
    raw = {
        "status": "success",
        "message": "ok",
        "llm_response": {"content": "张三的手机号是 13800138000。"},
        "data": {
            "entities": [{"entity_name": "张三"}],
            "chunks": [
                {
                    "content": "姓名：张三　　编号联络：13800138000",
                    "file_path": "能力证书清单.docx",
                    "score": 0.91,
                }
            ],
        },
    }
    assert answer_from_query_raw(raw) == "张三的手机号是 13800138000。"
    contexts = contexts_from_query_raw(raw)
    assert contexts[0].doc_id == "能力证书清单.docx"
    assert contexts[0].entities == ["张三"]


def test_bundle_to_text_does_not_repeat_title() -> None:
    bundle = DocumentBundle(
        doc_id="doc-1",
        title="能力证书清单",
        media_type="text/plain",
        text="能力证书清单\n姓名：张三",
        metadata={},
    )
    assert bundle_to_text(bundle) == "能力证书清单\n姓名：张三"
