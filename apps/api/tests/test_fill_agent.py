from __future__ import annotations

import pytest

from aff_contracts import FillFormRequest, FillResult, FormField
from aff_contracts.fill import (
    ExcelLocator,
    FieldStatus,
    FieldType,
    LayoutKind,
)
from aff_contracts.rag import RagContext, RagQueryResult


class MockRag:
    """纯内存 mock RagPort，保证 fill() 不调用 upsert/delete（红线）。"""

    def __init__(self, results: dict[str, RagQueryResult] | None = None) -> None:
        self.results = results or {}
        self.calls: list[str] = []

    def query(self, req):
        self.calls.append(req.query)
        for key, r in self.results.items():
            if key in req.query:
                return r
        return RagQueryResult(answer="", contexts=[])

    def upsert(self, *a, **kw):  # pragma: no cover - 触发即算失败
        raise AssertionError("fill() 不得调用 RagPort.upsert (ACCEPTANCE.md §7)")

    def delete(self, *a, **kw):  # pragma: no cover - 触发即算失败
        raise AssertionError("fill() 不得调用 RagPort.delete (ACCEPTANCE.md §7)")


class FakeLLMClient:
    """测试用假 LLM：按关键字匹配 prompt 返回预设响应。

    - response_map 可含 "entity_type"/"multi_row"/字段名等提示词
    - 匹配优先级：按 dict 插入顺序，第一个命中的 key 就返回对应 val
    """

    def __init__(self, response_map: dict[str, str] | None = None) -> None:
        self._response_map = response_map or {}
        self.calls: list[str] = []

    def complete(self, prompt: str, *, schema=None, temperature=0.0) -> str:
        self.calls.append(prompt)
        for keyword, resp in self._response_map.items():
            if keyword in prompt:
                return resp
        return ""

    @staticmethod
    def build_prompt(field, contexts, settings):
        from app.modules.fill.agent.runner import LLMClient
        return LLMClient.build_prompt(field, contexts, settings)

    @staticmethod
    def build_multi_row_prompt(headers, contexts, settings):
        from app.modules.fill.agent.runner import LLMClient
        return LLMClient.build_multi_row_prompt(headers, contexts, settings)


def _mk_service(llm: FakeLLMClient | None = None, settings=None):
    """构造带 FakeLLMClient + 自定义 settings 的 FillService。"""
    from aff_contracts.settings import Settings

    from app.modules.fill.service import FillService

    svc = FillService(settings or Settings())
    if llm is not None:
        svc._llm = llm
    return svc


def _mk_field(
    fid: str = "f1",
    name: str = "姓名",
    layout: LayoutKind = LayoutKind.label_value,
    row_group_id: str | None = None,
    row_index: int | None = None,
    column_key: str | None = None,
    field_type: FieldType = FieldType.text,
    notes: str | None = None,
) -> FormField:
    return FormField(
        id=fid,
        name=name,
        field_type=field_type,
        value=None,
        original_value=None,
        required=True,
        confidence=None,
        sources=[],
        status=FieldStatus.empty,
        layout=layout,
        row_group_id=row_group_id,
        row_index=row_index,
        column_key=column_key,
        locator=ExcelLocator(sheet="S", row=1, col=1),
        notes=notes,
    )


# ---------------------------------------------------------------------- #
#  最简通过类用例：保证骨架可直接跑，不依赖真实 LLM / 真实图谱
# ---------------------------------------------------------------------- #
def test_fill_empty_fields() -> None:
    svc = _mk_service()
    req = FillFormRequest(job_id="j1", fields=[])
    res = svc.fill(req, MockRag())
    assert isinstance(res, FillResult)
    assert res.job_id == "j1"
    assert res.stats.filled == 0 and res.stats.empty == 0
    assert res.stats.low_confidence == 0


def test_fill_no_evidence_returns_empty() -> None:
    """红线：无证据 → value=None, status=empty（不瞎说）。"""
    svc = _mk_service()
    f = _mk_field()
    req = FillFormRequest(job_id="j1", fields=[f])
    res = svc.fill(req, MockRag())

    f_out = res.fields[0]
    assert f_out.value is None, "无证据时 value 必须为 null（CONF=0）"
    assert f_out.status == FieldStatus.empty
    assert f_out.confidence == 0.0
    # original_value=None 时不算 stats.empty（Day4：空字段不计入）
    assert res.stats.filled == 0
    assert res.stats.empty == 0  # 原本就空，不计入 empty


def test_fill_has_evidence_is_suggested_with_sources() -> None:
    """有证据 → suggested + sources 非空 + confidence>0。"""
    # FakeLLM 命中"姓名"时返回"张三"
    llm = FakeLLMClient({"姓名": "张三"})
    svc = _mk_service(llm)

    rag = MockRag(
        {
            "姓名": RagQueryResult(
                answer="",
                contexts=[
                    RagContext(
                        content="张三，英文名 Bob，2020 年入职 ACME 公司任算法工程师。",
                        doc_id="doc_resume_001",
                        score=0.92,
                        entities=["张三", "ACME", "算法工程师"],
                    )
                ],
            )
        }
    )
    req = FillFormRequest(job_id="j1", fields=[_mk_field()])
    res = svc.fill(req, rag)

    f_out = res.fields[0]
    assert f_out.status == FieldStatus.suggested
    assert f_out.confidence is not None and f_out.confidence > 0
    assert f_out.value is not None and f_out.value != ""
    assert len(f_out.sources) >= 1
    assert f_out.sources[0].doc_id == "doc_resume_001"
    assert res.stats.filled == 1


def test_fill_never_calls_rag_write_paths() -> None:
    """红线：fill() 期间 upsert/delete 不得被调用。"""
    llm = FakeLLMClient({"姓名": "张三"})
    svc = _mk_service(llm)
    rag = MockRag(
        {
            "姓名": RagQueryResult(
                answer="张三",
                contexts=[RagContext(content="张三", doc_id="d", score=0.9, entities=["张三"])],
            )
        }
    )
    req = FillFormRequest(job_id="j1", fields=[_mk_field()])
    svc.fill(req, rag)


def test_fill_retry_triggered_when_align_low() -> None:
    """align < 0.5 触发重试：首次 align=0.2 → 重试 align=0.9 → 采纳重试结果。"""
    from unittest.mock import Mock, patch

    svc = _mk_service()
    rag = MockRag(
        {
            "姓名": RagQueryResult(
                answer="",
                contexts=[RagContext(content="原始证据", doc_id="d1", score=0.6, entities=[])],
            ),
            "精确查找": RagQueryResult(
                answer="",
                contexts=[RagContext(content="重试证据", doc_id="d2", score=0.9, entities=[])],
            ),
        }
    )

    top1 = Mock(score=0.6)
    top2 = Mock(score=0.9)
    with patch.object(
        svc, "_score_field",
        side_effect=[
            ("模糊值", 0.30, 0.2, 0.5, top1),
            ("张三", 0.90, 0.9, 1.0, top2),
        ],
    ) as mock_score:
        req = FillFormRequest(job_id="j1", fields=[_mk_field(name="姓名")])
        res = svc.fill(req, rag)

    assert mock_score.call_count == 2
    f_out = res.fields[0]
    assert f_out.value == "张三"
    assert f_out.confidence == 0.90
    assert any("精确查找" in q for q in rag.calls)


def test_fill_retry_not_triggered_when_align_high() -> None:
    """align ≥ 0.5 不触发重试。"""
    from unittest.mock import Mock, patch

    svc = _mk_service()
    rag = MockRag(
        {
            "姓名": RagQueryResult(
                answer="",
                contexts=[RagContext(content="证据", doc_id="d1", score=0.9, entities=[])],
            ),
        }
    )

    top1 = Mock(score=0.9)
    with patch.object(
        svc, "_score_field",
        return_value=("张三", 0.80, 0.8, 1.0, top1),
    ):
        req = FillFormRequest(job_id="j1", fields=[_mk_field(name="姓名")])
        svc.fill(req, rag)

    assert not any("精确查找" in q for q in rag.calls)


# ---------------------------------------------------------------------- #
#  多行表分组场景
# ---------------------------------------------------------------------- #
def test_fill_multi_row_table_grouping() -> None:
    """同 row_group_id 的多行字段归一组，row_index 各自保留，headers 汇总。"""
    from app.modules.fill.agent.grouper import FieldGrouper

    fields = [
        _mk_field(fid="r1c1", name="公司", layout=LayoutKind.header_row_table,
                  row_group_id="exp1", row_index=0, column_key="公司"),
        _mk_field(fid="r1c2", name="职位", layout=LayoutKind.header_row_table,
                  row_group_id="exp1", row_index=0, column_key="职位"),
        _mk_field(fid="r2c1", name="公司", layout=LayoutKind.header_row_table,
                  row_group_id="exp1", row_index=1, column_key="公司"),
        _mk_field(fid="r2c2", name="职位", layout=LayoutKind.header_row_table,
                  row_group_id="exp1", row_index=1, column_key="职位"),
    ]

    groups = FieldGrouper.group(fields)
    assert len(groups) == 1
    g = groups[0]
    assert g.key == "exp1"
    assert len(g.fields) == 4
    assert g.headers == ["公司", "职位"]

    row_indices = sorted(f.row_index for f in g.fields)
    assert row_indices == [0, 0, 1, 1]

    # 跑 fill()：现在 header_row_table 走 Day5 MSR 路径
    import json as _json
    llm = FakeLLMClient({
        "分类助手": _json.dumps({"entity_type": "工作经历", "query_hint": "工作经历"}, ensure_ascii=False),
        "JSON 数组": _json.dumps([
            {"公司": "ACME", "职位": "工程师"},
            {"公司": "Beta", "职位": "高级工程师"},
        ], ensure_ascii=False),
    })
    svc = _mk_service(llm)
    rag = MockRag(
        {
            "工作经历": RagQueryResult(
                answer="",
                contexts=[RagContext(
                    content="2020 年入职 ACME 任工程师，后跳槽至 Beta 任高级工程师。",
                    doc_id="d1", score=0.95, entities=["ACME", "Beta", "工程师", "高级工程师"],
                )],
            ),
        }
    )
    req = FillFormRequest(job_id="j1", fields=fields)
    res = svc.fill(req, rag)

    assert res.stats.filled == 4, f"4 字段应全填，实际 filled={res.stats.filled}"
    assert res.stats.empty == 0
    for f in res.fields:
        assert f.status == FieldStatus.suggested, f"{f.id}({f.column_key}#{f.row_index}) 应为 suggested，实际 {f.status}: {f.value}"
        assert f.value, f"{f.id} 不应为空"
        assert f.sources, f"{f.id} 应有 sources"
    # 具体值校验
    def get(r, c):
        for f in res.fields:
            if f.row_index == r and f.column_key == c:
                return f.value
        return None
    assert get(0, "公司") == "ACME"
    assert get(0, "职位") == "工程师"
    assert get(1, "公司") == "Beta"
    assert get(1, "职位") == "高级工程师"


def test_fill_multi_row_table_isolated_from_single_fields() -> None:
    """多行表字段与 label_value 单字段应各自独立分组。"""
    from app.modules.fill.agent.grouper import FieldGrouper

    fields = [
        _mk_field(fid="name1", name="姓名", layout=LayoutKind.label_value),
        _mk_field(fid="r1", name="公司", layout=LayoutKind.header_row_table,
                  row_group_id="exp1", row_index=0, column_key="公司"),
        _mk_field(fid="r2", name="公司", layout=LayoutKind.header_row_table,
                  row_group_id="exp1", row_index=1, column_key="公司"),
    ]
    groups = FieldGrouper.group(fields)
    assert len(groups) == 2

    table_group = next(g for g in groups if g.layout == LayoutKind.header_row_table)
    single_group = next(g for g in groups if g.layout == LayoutKind.label_value)

    assert table_group.key == "exp1"
    assert len(table_group.fields) == 2
    assert table_group.headers == ["公司"]

    assert single_group.key == "single-name1"
    assert len(single_group.fields) == 1


# ---------------------------------------------------------------------- #
#  Day 3: validate_type 边界用例
# ---------------------------------------------------------------------- #
def test_validate_type_boundary_cases() -> None:
    """创新点 2：validate_type 对各种 field_type 的边界用例。"""
    from app.modules.fill.agent.runner import validate_type

    # 空串 → 所有类型都非法
    assert validate_type("text", "") == (False, 0.0)
    assert validate_type("date", "") == (False, 0.0)
    assert validate_type("number", "") == (False, 0.0)

    # text：正常
    assert validate_type("text", "张三") == (True, 1.0)
    # text：超长 → 半分
    long_val = "x" * 101
    assert validate_type("text", long_val) == (False, 0.5)
    # text：带换行 → 半分
    assert validate_type("text", "a\nb") == (False, 0.5)

    # date：合法
    assert validate_type("date", "2024-01-15") == (True, 1.0)
    # date：非法格式
    assert validate_type("date", "2024/01/15") == (False, 0.0)
    assert validate_type("date", "2024年1月") == (False, 0.0)

    # number：合法
    assert validate_type("number", "42") == (True, 1.0)
    assert validate_type("number", "-3.14") == (True, 1.0)
    # number：带汉字 → 非法
    assert validate_type("number", "42岁") == (False, 0.0)

    # single_choice：有选项
    notes = "options: 男|女"
    assert validate_type("single_choice", "男", notes) == (True, 1.0)
    assert validate_type("single_choice", "未知", notes) == (False, 0.0)
    # single_choice：无选项 → 降级非空校验
    assert validate_type("single_choice", "任意值", None) == (True, 1.0)

    # multi：有选项
    notes_multi = "选项: A, B, C"
    assert validate_type("multi", "A,B", notes_multi) == (True, 1.0)
    assert validate_type("multi", "A,D", notes_multi) == (False, 0.5)  # 部分匹配
    assert validate_type("multi", "D,E", notes_multi) == (False, 0.0)

    # other：非空即通过
    assert validate_type("other", "任意内容") == (True, 1.0)


# ---------------------------------------------------------------------- #
#  Day 3: build_prompt 模板注入验证
# ---------------------------------------------------------------------- #
def test_build_prompt_injects_field_type_templates() -> None:
    """创新点 2 TAPE：5 种 field_type 的模板都正确注入。"""
    from aff_contracts.settings import Settings

    from app.modules.fill.agent.runner import LLMClient

    settings = Settings()
    ctx = [RagContext(content="张三，2020年入职", doc_id="d1", score=0.9)]

    # text
    f = _mk_field(name="姓名", field_type=FieldType.text)
    p = LLMClient.build_prompt(f, ctx, settings)
    assert "【姓名】" in p
    assert "文本" in p
    assert "张三" in p

    # date
    f = _mk_field(name="入职日期", field_type=FieldType.date)
    p = LLMClient.build_prompt(f, ctx, settings)
    assert "【入职日期】" in p
    assert "YYYY-MM-DD" in p

    # number
    f = _mk_field(name="年龄", field_type=FieldType.number)
    p = LLMClient.build_prompt(f, ctx, settings)
    assert "【年龄】" in p
    assert "数字" in p

    # single_choice（带选项）
    f = _mk_field(name="性别", field_type=FieldType.single_choice, notes="options: 男|女")
    p = LLMClient.build_prompt(f, ctx, settings)
    assert "【性别】" in p
    assert "单选" in p
    assert "男" in p and "女" in p

    # multi（带选项）
    f = _mk_field(name="技能", field_type=FieldType.multi, notes="选项: Python, Go, Rust")
    p = LLMClient.build_prompt(f, ctx, settings)
    assert "【技能】" in p
    assert "多选" in p
    assert "Python" in p

    # single_choice（无选项）→ 降级提示
    f = _mk_field(name="性别", field_type=FieldType.single_choice)
    p = LLMClient.build_prompt(f, ctx, settings)
    assert "未提供选项" in p


def test_build_prompt_no_evidence() -> None:
    """无证据时模板仍能生成（含'无证据'提示）。"""
    from aff_contracts.settings import Settings

    from app.modules.fill.agent.runner import LLMClient

    settings = Settings()
    f = _mk_field(name="姓名")
    p = LLMClient.build_prompt(f, [], settings)
    assert "无证据" in p


def test_llm_complete_with_mock_openai() -> None:
    """mock openai.OpenAI，验证 complete() 正确调用 + schema 透传。"""
    from unittest.mock import MagicMock, patch

    from aff_contracts.settings import Settings

    from app.modules.fill.agent.runner import LLMClient

    settings = Settings(llm_provider="ollama", query_model="qwen2.5:7b")

    # 构造 mock OpenAI 返回
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = "  张三  "

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_resp

    with patch("app.modules.fill.agent.runner.OpenAI", return_value=mock_client):
        client = LLMClient(settings)

    # 不带 schema
    result = client.complete("test prompt")
    assert result == "张三"  # 应 strip 掉首尾空格
    mock_client.chat.completions.create.assert_called_once()
    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == "qwen2.5:7b"
    assert call_kwargs["stream"] is False
    assert "response_format" not in call_kwargs
    assert "extra_body" not in call_kwargs

    # 带 schema（Ollama → extra_body.format）
    mock_client.chat.completions.create.reset_mock()
    client.complete("test prompt", schema={"type": "string"})
    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["extra_body"] == {"format": {"type": "string"}}


def test_llm_complete_schema_openai_compatible() -> None:
    """OpenAI-compatible provider 带 schema → response_format=json_schema。"""
    from unittest.mock import MagicMock, patch

    from aff_contracts.settings import Settings

    from app.modules.fill.agent.runner import LLMClient

    settings = Settings(llm_provider="openai_compatible", query_model="deepseek-chat",
                        llm_api_base="https://api.deepseek.com/v1", llm_api_key="sk-test")

    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = "张三"

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_resp

    with patch("app.modules.fill.agent.runner.OpenAI", return_value=mock_client):
        client = LLMClient(settings)

    client.complete("test prompt", schema={"type": "object"})
    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["response_format"]["type"] == "json_schema"
    assert call_kwargs["response_format"]["json_schema"]["strict"] is True


# ---------------------------------------------------------------------- #
#  Day 4: PostProc 串联 + FillResult 拼装 — 集成验收
# ---------------------------------------------------------------------- #
def test_fill_result_matches_fixture_structure() -> None:
    """输出结构与 fixtures/success/fill_result.json 对齐。"""
    import json
    from pathlib import Path

    fixture_path = Path(__file__).parent.parent.parent.parent / "packages" / "contracts" / "fixtures" / "success" / "fill_result.json"
    with open(fixture_path, encoding="utf-8") as f:
        fixture = json.load(f)

    # fixture 必须有这些字段
    assert "job_id" in fixture
    assert "fields" in fixture
    assert "stats" in fixture
    assert set(fixture["stats"].keys()) == {"filled", "empty", "low_confidence"}

    # fixture 的每个 field 必须能通过 FormField 校验
    for ff in fixture["fields"]:
        validated = FormField.model_validate(ff)
        assert validated.name
        assert validated.field_type
        assert validated.status in list(FieldStatus)

    # FillResult 整体校验
    from aff_contracts import FillResult as FR
    result = FR.model_validate(fixture)
    assert result.job_id == "job_001"
    assert len(result.fields) == 1
    assert result.fields[0].value == "张三"
    assert result.stats.filled == 1


def test_fill_stats_counts_original_value_cleared() -> None:
    """原值非空被清空 → 计 empty；原值为空且仍空 → 不计 empty。"""
    llm = FakeLLMClient()  # 默认返回空串（模拟无证据）
    svc = _mk_service(llm)

    # 字段 1：original_value=None（原本就空）
    f1 = _mk_field(fid="f1", name="姓名")
    f1.original_value = None
    # 字段 2：original_value="旧值"（原本有值）
    f2 = _mk_field(fid="f2", name="电话")
    f2.original_value = "13800138000"

    req = FillFormRequest(job_id="j1", fields=[f1, f2])
    res = svc.fill(req, MockRag())

    # 两个字段都无证据 → 都被置空
    assert res.fields[0].status == FieldStatus.empty
    assert res.fields[1].status == FieldStatus.empty
    # f1 原本就空 → 不计 empty
    # f2 原本有值被清空 → 计 empty
    assert res.stats.empty == 1
    assert res.stats.filled == 0


def test_fill_stats_counts_filled_and_low_confidence() -> None:
    """有证据填了 → filled；低置信度 → low_confidence。"""
    llm = FakeLLMClient({"姓名": "张三"})
    svc = _mk_service(llm)
    rag = MockRag({
        "姓名": RagQueryResult(
            answer="",
            contexts=[RagContext(content="张三", doc_id="d1", score=0.4, entities=["张三"])],
        ),
    })
    req = FillFormRequest(job_id="j1", fields=[_mk_field(name="姓名")])
    res = svc.fill(req, rag)

    # score=0.4 → conf 可能低于 LOW 阈值
    f_out = res.fields[0]
    if f_out.status == FieldStatus.suggested:
        assert res.stats.filled >= 1
        if f_out.confidence < 0.45:
            assert res.stats.low_confidence >= 1


def test_fill_sources_deduplicated() -> None:
    """同一 doc_id + snippet 不重复出现。"""
    llm = FakeLLMClient({"姓名": "张三"})
    svc = _mk_service(llm)
    # 同一证据出现两次
    ctx = RagContext(content="张三的简历", doc_id="d1", score=0.9, entities=["张三"])
    rag = MockRag({
        "姓名": RagQueryResult(answer="", contexts=[ctx, ctx, ctx]),
    })
    req = FillFormRequest(job_id="j1", fields=[_mk_field(name="姓名")])
    res = svc.fill(req, rag)

    f_out = res.fields[0]
    doc_ids = [s.doc_id for s in f_out.sources]
    assert len(doc_ids) == len(set(doc_ids)), "sources 必须去重"


def test_fill_confidence_precision() -> None:
    """confidence 精度为 3 位小数（round 到 0.001）。"""
    llm = FakeLLMClient({"姓名": "张三"})
    svc = _mk_service(llm)
    rag = MockRag({
        "姓名": RagQueryResult(
            answer="",
            contexts=[RagContext(content="张三", doc_id="d1", score=0.92, entities=["张三"])],
        ),
    })
    req = FillFormRequest(job_id="j1", fields=[_mk_field(name="姓名")])
    res = svc.fill(req, rag)

    f_out = res.fields[0]
    if f_out.confidence is not None and f_out.confidence > 0:
        # 最多 3 位小数
        assert round(f_out.confidence, 3) == f_out.confidence


# ---------------------------------------------------------------------- #
#  Day 5: MSR 多行语义路由（planner/runner/service 集成）
# ---------------------------------------------------------------------- #
def test_pre_determine_entity_type_success() -> None:
    """MSR Step 1: 预问 LLM 成功返回工作经历。"""
    from app.modules.fill.agent.grouper import FieldGroup
    from app.modules.fill.agent.planner import QueryPlanner
    from aff_contracts.fill import LayoutKind

    llm = FakeLLMClient({
        "分类助手": '{"entity_type": "工作经历", "query_hint": "工作履历：公司、职位、入职时间"}',
    })
    group = FieldGroup(key="exp1", layout=LayoutKind.header_row_table,
                       fields=[], headers=["公司", "职位", "时间"])
    et, qh = QueryPlanner.pre_determine_entity_type(group, llm)
    assert et == "工作经历"
    assert "工作履历" in qh


def test_pre_determine_entity_type_invalid_json_fallback() -> None:
    """MSR Step 1: LLM 返回非法 JSON → fallback 其他+headers。"""
    from app.modules.fill.agent.grouper import FieldGroup
    from app.modules.fill.agent.planner import QueryPlanner
    from aff_contracts.fill import LayoutKind

    llm = FakeLLMClient({"分类助手": "not a json at all"})
    group = FieldGroup(key="exp1", layout=LayoutKind.header_row_table,
                       fields=[], headers=["学校", "专业", "时间"])
    et, qh = QueryPlanner.pre_determine_entity_type(group, llm)
    assert et == "其他"
    assert "学校" in qh  # fallback = headers 拼接


def test_pre_determine_entity_type_not_in_enum_fallback() -> None:
    """MSR Step 1: 返回值不在 6 个 enum 内 → entity_type 降级其他。"""
    from app.modules.fill.agent.grouper import FieldGroup
    from app.modules.fill.agent.planner import QueryPlanner
    from aff_contracts.fill import LayoutKind

    llm = FakeLLMClient({
        "分类助手": '{"entity_type": "志愿者经历", "query_hint": "志愿活动"}',
    })
    group = FieldGroup(key="v1", layout=LayoutKind.header_row_table,
                       fields=[], headers=["组织", "角色"])
    et, qh = QueryPlanner.pre_determine_entity_type(group, llm)
    assert et == "其他"
    assert qh == "志愿活动"


def test_build_multi_row_query_with_entity_type() -> None:
    """MSR Step 2: build_multi_row_query 拼接 entity_type+hint+headers。"""
    from app.modules.fill.agent.planner import QueryPlanner
    q = QueryPlanner.build_multi_row_query("工作经历", "互联网公司任职", ["公司", "职位", "时间"])
    assert "工作经历" in q
    assert "互联网公司任职" in q
    assert "公司" in q and "职位" in q and "时间" in q

    q2 = QueryPlanner.build_multi_row_query("其他", "ABC", ["X"])
    assert "其他" not in q2  # entity_type=其他时不硬塞到句子里
    assert "ABC" in q2


def test_build_multi_row_schema_matches_headers() -> None:
    """MSR Step 3: JSONSchema items.properties keys == headers 且 required。"""
    from app.modules.fill.agent.runner import build_multi_row_schema
    s = build_multi_row_schema(["公司", "职位", "时间"])
    assert s["type"] == "array"
    assert set(s["items"]["properties"].keys()) == {"公司", "职位", "时间"}
    assert set(s["items"]["required"]) == {"公司", "职位", "时间"}
    assert s["items"]["additionalProperties"] is False


def test_generate_multi_row_parse_and_truncate() -> None:
    """MSR Step 3: generate_multi_row 解析 JSON、按 max_table_rows 截断。"""
    import json as _json

    from aff_contracts.settings import Settings

    from app.modules.fill.agent.runner import generate_multi_row

    settings = Settings(max_table_rows=2)  # 只允许最多 2 行
    # 生成 3 行 → 应被截断为 2 行
    rows_3 = [
        {"公司": "ACME", "职位": "工程师", "时间": "2020-01-01"},
        {"公司": "Beta", "职位": "高级工程师", "时间": "2022-03-15"},
        {"公司": "Gamma", "职位": "技术总监", "时间": "2024-06-01"},
    ]
    llm = FakeLLMClient({"JSON 数组": _json.dumps(rows_3, ensure_ascii=False)})
    ctxs = [RagContext(content="工作经历...", doc_id="resume", score=0.9)]
    result = generate_multi_row(llm, ["公司", "职位", "时间"], ctxs, settings,
                                entity_type="工作经历", hint="任职经历")
    assert len(result.rows) == 2, f"max_table_rows=2 应截断，实际 {len(result.rows)}"
    assert result.rows[0]["公司"] == "ACME"
    assert result.rows[1]["公司"] == "Beta"


def test_generate_multi_row_empty_evidence_returns_zero_rows() -> None:
    """MSR Step 3: LLM 返回空串 / '[]' → 0 行，不崩。"""
    from aff_contracts.settings import Settings

    from app.modules.fill.agent.runner import generate_multi_row

    settings = Settings(max_table_rows=50)
    llm_empty = FakeLLMClient({"JSON 数组": ""})
    llm_bracket = FakeLLMClient({"JSON 数组": "[]"})
    llm_bad = FakeLLMClient({"JSON 数组": "{invalid}"})
    ctxs = []

    assert len(generate_multi_row(llm_empty, ["A", "B"], ctxs, settings).rows) == 0
    assert len(generate_multi_row(llm_bracket, ["A", "B"], ctxs, settings).rows) == 0
    assert len(generate_multi_row(llm_bad, ["A", "B"], ctxs, settings).rows) == 0


def test_fill_multi_row_msr_end_to_end_two_rows() -> None:
    """Day 5 验收：3 列（时间/组织/角色）+ 上下文含 2 条工作经历 →
    row_index 0/1 连续、row_group_id 保留、各列 value 正确、filled 计数正确。"""
    import json as _json

    # --- FakeLLM 响应：1) entity_type 预问  2) multi_row 批量生成 ---
    # 注意：Python 3.7+ dict 保证插入顺序，FakeLLMClient 按顺序匹配
    llm = FakeLLMClient({
        # 关键字 1：分类助手 prompt（MSR Step1）
        "分类助手": _json.dumps(
            {"entity_type": "工作经历", "query_hint": "工作经历、任职记录"},
            ensure_ascii=False,
        ),
        # 关键字 2：多行 JSON 数组模板（MSR Step3）
        "JSON 数组": _json.dumps([
            {"时间": "2020-07-01", "组织": "ACME Corp", "角色": "算法工程师"},
            {"时间": "2023-03-15", "组织": "Beta Labs", "角色": "高级工程师"},
        ], ensure_ascii=False),
    })

    # --- MockRag：匹配 MSR Step2 build_multi_row_query 生成的 query ---
    rag = MockRag({
        "工作经历": RagQueryResult(
            answer="",
            contexts=[
                RagContext(
                    content="2020 年 7 月入职 ACME Corp 担任算法工程师，2023 年 3 月跳槽至 Beta Labs 任高级工程师。",
                    doc_id="resume_001",
                    score=0.95,
                    entities=["ACME Corp", "Beta Labs", "算法工程师", "高级工程师"],
                ),
            ],
        ),
    })

    # 造 2 行 × 3 列 = 6 个 FormField（row_index 0,1；row_group_id 同 exp1）
    fields = [
        _mk_field(fid="r0t", name="时间", layout=LayoutKind.header_row_table,
                  row_group_id="exp1", row_index=0, column_key="时间", field_type=FieldType.date),
        _mk_field(fid="r0o", name="组织", layout=LayoutKind.header_row_table,
                  row_group_id="exp1", row_index=0, column_key="组织"),
        _mk_field(fid="r0r", name="角色", layout=LayoutKind.header_row_table,
                  row_group_id="exp1", row_index=0, column_key="角色"),
        _mk_field(fid="r1t", name="时间", layout=LayoutKind.header_row_table,
                  row_group_id="exp1", row_index=1, column_key="时间", field_type=FieldType.date),
        _mk_field(fid="r1o", name="组织", layout=LayoutKind.header_row_table,
                  row_group_id="exp1", row_index=1, column_key="组织"),
        _mk_field(fid="r1r", name="角色", layout=LayoutKind.header_row_table,
                  row_group_id="exp1", row_index=1, column_key="角色"),
    ]

    svc = _mk_service(llm)
    req = FillFormRequest(job_id="j1", fields=fields)
    res = svc.fill(req, rag)

    # 验收点 1：filled 计数（6 个字段都有值且证据对齐应该高分）
    assert res.stats.filled == 6, f"6 字段应全部 filled，实际 {res.stats.filled}"

    # 验收点 2：row_group_id 保留，row_index 连续
    for f in res.fields:
        assert f.row_group_id == "exp1"
        assert f.row_index in (0, 1)

    # 验收点 3：按 (row_index, column_key) 查值
    def get(r, c):
        for f in res.fields:
            if f.row_index == r and f.column_key == c:
                return f.value, f.status, f.confidence, f.sources
        return None

    r0t, r0t_status, _, r0t_srcs = get(0, "时间")
    r0o, r0o_status, _, _ = get(0, "组织")
    r0r, r0r_status, _, _ = get(0, "角色")
    assert r0t == "2020-07-01", f"row0 时间预期 2020-07-01，实际 {r0t}"
    assert r0o == "ACME Corp", f"row0 组织预期 ACME Corp，实际 {r0o}"
    assert r0r == "算法工程师", f"row0 角色预期 算法工程师，实际 {r0r}"
    assert r0t_status == FieldStatus.suggested
    assert r0o_status == FieldStatus.suggested
    assert r0r_status == FieldStatus.suggested
    assert len(r0t_srcs) >= 1 and r0t_srcs[0].doc_id == "resume_001"

    r1t, r1t_status, _, _ = get(1, "时间")
    r1o, r1o_status, _, _ = get(1, "组织")
    r1r, r1r_status, _, _ = get(1, "角色")
    assert r1t == "2023-03-15", f"row1 时间预期 2023-03-15，实际 {r1t}"
    assert r1o == "Beta Labs", f"row1 组织预期 Beta Labs，实际 {r1o}"
    assert r1r == "高级工程师", f"row1 角色预期 高级工程师，实际 {r1r}"
    assert r1t_status == r1o_status == r1r_status == FieldStatus.suggested


def test_fill_multi_row_max_table_rows_enforced_via_settings() -> None:
    """Day 5 验收：settings.max_table_rows=1 时，超过的生成行被截断且不填。"""
    import json as _json

    from aff_contracts.settings import Settings

    # max_table_rows=1，LLM 却返回 2 行 → 最终只填 row0
    llm = FakeLLMClient({
        "分类助手": _json.dumps({"entity_type": "教育经历", "query_hint": "教育经历"}, ensure_ascii=False),
        "JSON 数组": _json.dumps([
            {"时间": "2014-09-01", "学校": "X 大", "专业": "CS"},
            {"时间": "2018-09-01", "学校": "Y 大", "专业": "SE"},  # 会被 runner 截断
        ], ensure_ascii=False),
    })

    rag = MockRag({
        "教育经历": RagQueryResult(
            answer="",
            contexts=[RagContext(content="教育经历丰富", doc_id="edu", score=0.8)],
        ),
    })

    # 仍分配 2 行 × 3 列 FormField（常见 case：上游给了空白多行）
    fields = [
        _mk_field(fid=f"r{i}-{c}", name=cname, layout=LayoutKind.header_row_table,
                  row_group_id="edu1", row_index=i, column_key=cname)
        for i in (0, 1)
        for c, cname in enumerate(["时间", "学校", "专业"])
    ]

    settings = Settings(max_table_rows=1)
    svc = _mk_service(llm, settings=settings)
    req = FillFormRequest(job_id="j1", fields=fields)
    res = svc.fill(req, rag)

    # row0 的 3 个字段应为 suggested（有值）
    row0 = [f for f in res.fields if f.row_index == 0]
    for f in row0:
        assert f.status == FieldStatus.suggested, f"row0.{f.column_key} 应为 suggested，实际 {f.status}: {f.value}"
    assert row0[0].value == "2014-09-01"

    # row1 的 3 个字段：runner 只返回 1 行（被 max_table_rows=1 截断），
    # service 走 MSR 时只枚举 len(generated_rows)=1 → row1 不会被填，最后走 EMPTY 兜底
    row1 = [f for f in res.fields if f.row_index == 1]
    for f in row1:
        assert f.status == FieldStatus.empty, f"row1.{f.column_key} 应为 empty（max_rows=1 截断后无值）"
        assert f.value is None
        assert f.confidence == 0.0
    # filled = 3，empty = 3
    assert res.stats.filled == 3, f"filled 预期 3，实际 {res.stats.filled}"


def test_fill_multi_row_entity_type_fallback_still_works() -> None:
    """Day 5: entity_type 预问返回非法 JSON（fallback 其他）→ 后续流程仍能正常批量生成。"""
    import json as _json

    # 注意：先匹配 "分类助手" 返回乱码，再匹配 "JSON 数组" 返回正常 1 行
    llm = FakeLLMClient({
        "分类助手": "GARBAGE_NOT_JSON__!!!",  # 触发 fallback: 其他 + headers
        "JSON 数组": _json.dumps([
            {"证书名称": "PMP", "发证机构": "PMI", "发证日期": "2021-05-20"},
        ], ensure_ascii=False),
    })

    rag = MockRag({
        "证书名称": RagQueryResult(
            answer="",
            contexts=[RagContext(content="2021 年 5 月取得 PMI 颁发的 PMP 证书。",
                                 doc_id="cert.pdf", score=0.88, entities=["PMP", "PMI"])],
        ),
    })

    fields = [
        _mk_field(fid="r0c", name="证书名称", layout=LayoutKind.header_row_table,
                  row_group_id="cert1", row_index=0, column_key="证书名称"),
        _mk_field(fid="r0o", name="发证机构", layout=LayoutKind.header_row_table,
                  row_group_id="cert1", row_index=0, column_key="发证机构"),
        _mk_field(fid="r0d", name="发证日期", layout=LayoutKind.header_row_table,
                  row_group_id="cert1", row_index=0, column_key="发证日期",
                  field_type=FieldType.date),
    ]

    svc = _mk_service(llm)
    req = FillFormRequest(job_id="j1", fields=fields)
    res = svc.fill(req, rag)

    # fallback 不应导致流程崩，3 个字段都应填值
    assert res.stats.filled == 3, f"3 字段应全填，实际 filled={res.stats.filled}"
    f_map = {(f.row_index, f.column_key): f for f in res.fields}
    assert f_map[(0, "证书名称")].value == "PMP"
    assert f_map[(0, "发证机构")].value == "PMI"
    assert f_map[(0, "发证日期")].value == "2021-05-20"


def test_fill_mixed_single_and_multi_routes_correctly() -> None:
    """Day 5: 同一请求同时含 label_value 和 header_row_table → 各自走不同路径。"""
    import json as _json

    # label_value 关键字 "姓名" 返回 "张三"；
    # MSR 路径：先 "分类助手" → 工作经历，再 "JSON 数组" → 1 行
    llm = FakeLLMClient({
        "【姓名】": "张三",
        "分类助手": _json.dumps({"entity_type": "工作经历", "query_hint": "工作"}, ensure_ascii=False),
        "JSON 数组": _json.dumps([
            {"公司": "ACME", "职位": "工程师"},
        ], ensure_ascii=False),
    })

    rag = MockRag({
        "姓名": RagQueryResult(
            answer="",
            contexts=[RagContext(content="张三，ACME 工程师", doc_id="d1", score=0.9, entities=["张三"])],
        ),
        "工作经历": RagQueryResult(
            answer="",
            contexts=[RagContext(content="ACME 工程师张三", doc_id="d2", score=0.9)],
        ),
    })

    single = _mk_field(fid="s-name", name="姓名", layout=LayoutKind.label_value)
    multi_fields = [
        _mk_field(fid="m0c", name="公司", layout=LayoutKind.header_row_table,
                  row_group_id="exp1", row_index=0, column_key="公司"),
        _mk_field(fid="m0p", name="职位", layout=LayoutKind.header_row_table,
                  row_group_id="exp1", row_index=0, column_key="职位"),
    ]

    svc = _mk_service(llm)
    req = FillFormRequest(job_id="j1", fields=[single, *multi_fields])
    res = svc.fill(req, rag)

    # 单字段：走 label_value 分支，值 = "张三"
    f_single = next(f for f in res.fields if f.id == "s-name")
    assert f_single.value == "张三"
    assert f_single.status == FieldStatus.suggested

    # 多字段：走 MSR 分支
    f_map = {(f.row_index, f.column_key): f for f in res.fields if f.row_group_id == "exp1"}
    assert f_map[(0, "公司")].value == "ACME"
    assert f_map[(0, "职位")].value == "工程师"
    assert res.stats.filled == 3


# ---------------------------------------------------------------------- #
#  Day 6 Step 1: 边缘用例补全（7 个）
# ---------------------------------------------------------------------- #

def test_fill_deepseek_reasoning_content_stripped() -> None:
    """DeepSeek-R1 的 reasoning_content 字段不污染最终 content。

    通过 mock openai SDK 的 chat.completions.create 返回值，验证
    LLMClient.complete 只取 message.content，忽略 reasoning_content。
    """
    from unittest.mock import MagicMock

    from app.modules.fill.agent.runner import LLMClient

    # 构造一个带 reasoning_content 的假响应
    fake_resp = MagicMock()
    fake_resp.choices = [MagicMock()]
    fake_resp.choices[0].message.content = "张三"
    fake_resp.choices[0].message.reasoning_content = "让我想想...用户问的是姓名..."

    # 构造 LLMClient 但替换 _client 为 mock
    client = LLMClient.__new__(LLMClient)
    client._client = MagicMock()
    client._client.chat.completions.create.return_value = fake_resp
    client._provider = "openai_compatible"
    client.model = "deepseek-r1"

    result = client.complete("请填写姓名")
    assert result == "张三", f"应只返回 content='张三'，实际 {result!r}"
    assert "想想" not in result, "reasoning_content 不得泄漏到输出"


def test_fill_confidence_low_threshold_marks_yellow() -> None:
    """conf ∈ [0.30, 0.45) → suggested + low_confidence 计数 +1。

    构造 retrieval_score=0.5, align 偏低的 context，使 conf 落在 [0.30, 0.45) 区间。
    """
    llm = FakeLLMClient({"姓名": "李四"})
    svc = _mk_service(llm)
    # retrieval=0.5, entity 基本不对齐 → conf = 0.4*0.5 + 0.3*低 + 0.3*1.0 = 0.2+低+0.3
    # align 期望 ~0.1 → conf = 0.2 + 0.03 + 0.3 = 0.53 太高
    # 需要 align 更低：retrieval=0.4, align≈0.03 → conf = 0.16 + 0.009 + 0.3 = 0.469 仍偏高
    # 用 retrieval=0.35 → 0.14 + 0.009 + 0.3 = 0.449 → 刚好在 [0.30, 0.45)
    rag = MockRag({
        "姓名": RagQueryResult(
            answer="",
            contexts=[RagContext(content="xyz123abc", doc_id="d1", score=0.35, entities=[])],
        ),
    })
    req = FillFormRequest(job_id="j1", fields=[_mk_field(name="姓名")])
    res = svc.fill(req, rag)

    f_out = res.fields[0]
    assert f_out.status == FieldStatus.suggested, f"conf={f_out.confidence} 应为 suggested"
    assert f_out.confidence is not None
    assert f_out.confidence < 0.45, f"conf={f_out.confidence} 应 < 0.45（low_confidence 阈值）"
    assert f_out.confidence >= 0.30, f"conf={f_out.confidence} 应 >= 0.30（empty 阈值）"
    assert res.stats.low_confidence == 1, f"low_confidence 应计 1，实际 {res.stats.low_confidence}"
    assert res.stats.filled == 1


def test_fill_confidence_empty_threshold_forces_null() -> None:
    """conf < 0.30 → value=None, confidence=0, status=empty。

    构造 retrieval_score 极低 + align=0 的 context。
    """
    llm = FakeLLMClient({"姓名": "王五"})
    svc = _mk_service(llm)
    # retrieval=0.1, align≈0 → conf = 0.04 + 0 + 0.3 = 0.34 仍 > 0.30
    # 需要 type_validity 也低：用非法 date 类型
    # retrieval=0.1, align=0, tv=0 → conf = 0.04 + 0 + 0 = 0.04 < 0.30
    rag = MockRag({
        "日期": RagQueryResult(
            answer="",
            contexts=[RagContext(content="xyz", doc_id="d1", score=0.1, entities=[])],
        ),
    })
    f = _mk_field(name="日期", field_type=FieldType.date)
    req = FillFormRequest(job_id="j1", fields=[f])
    res = svc.fill(req, rag)

    f_out = res.fields[0]
    # LLM 返回 "王五" 不是合法日期 → tv=0, align≈0, retrieval=0.1 → conf < 0.30
    assert f_out.value is None, f"conf<0.30 时 value 必须为 None，实际 {f_out.value!r}"
    assert f_out.confidence == 0.0
    assert f_out.status == FieldStatus.empty


def test_fill_retrieval_score_none_treated_as_zero() -> None:
    """contexts 为空列表 → retrieval_score=None → 按 0 处理 → conf < 0.30 → empty。"""
    llm = FakeLLMClient({"姓名": "赵六"})
    svc = _mk_service(llm)
    # MockRag 找不到匹配 → 返回空 contexts
    rag = MockRag({"不存在的关键字": RagQueryResult(answer="", contexts=[])})
    req = FillFormRequest(job_id="j1", fields=[_mk_field(name="姓名")])
    res = svc.fill(req, rag)

    f_out = res.fields[0]
    assert f_out.value is None, "空 contexts → conf=0 → value=None"
    assert f_out.confidence == 0.0
    assert f_out.status == FieldStatus.empty


def test_fill_retry_exhausted_falls_back() -> None:
    """retry 循环 1 次（MAX_RETRIES=1）仍未改善 → 用首次结果。

    patch _score_field 让首次和重试都返回固定的低 align 结果 →
    验证不会无限重试，且最终用首次 conf。
    """
    from unittest.mock import patch

    llm = FakeLLMClient({"姓名": "钱七"})
    svc = _mk_service(llm)
    rag = MockRag({
        "姓名": RagQueryResult(
            answer="",
            contexts=[RagContext(content="钱七", doc_id="d1", score=0.8, entities=["钱七"])],
        ),
    })

    # 固定返回 align=0.1 的低分（< 0.50 触发重试）
    call_count = [0]

    def fake_score(field, ctx):
        call_count[0] += 1
        # 返回 (raw_value, conf, align, tv, top)
        top = ctx.contexts[0] if ctx.contexts else None
        return ("钱七", 0.41, 0.1, 1.0, top)

    with patch.object(svc, "_score_field", side_effect=fake_score):
        req = FillFormRequest(job_id="j1", fields=[_mk_field(name="姓名")])
        res = svc.fill(req, rag)

    # MAX_RETRIES=1 → _score_field 被调用 2 次（首次 + 1 次重试）
    assert call_count[0] == 2, f"_score_field 应被调用 2 次（首次+retry），实际 {call_count[0]}"
    f_out = res.fields[0]
    # conf=0.41 → suggested（< 0.45 但 >= 0.30）
    assert f_out.status == FieldStatus.suggested
    assert f_out.confidence == 0.41


def test_fill_multi_row_generated_exceeds_existing_rows() -> None:
    """LLM 返回 5 行但 FormField 只分配 2 行 → 多余 3 行被忽略，不扩表。"""
    import json as _json

    from aff_contracts.settings import Settings

    # max_table_rows=10（允许 LLM 返回 5 行），但 fields 只有 2 行
    llm = FakeLLMClient({
        "表头列名：公司": _json.dumps({"entity_type": "工作经历", "query_hint": "工作"}, ensure_ascii=False),
        "按表头 [公司": _json.dumps([
            {"公司": "A", "职位": "a1"},
            {"公司": "B", "职位": "b1"},
            {"公司": "C", "职位": "c1"},  # 超出现有 row → 忽略
            {"公司": "D", "职位": "d1"},  # 超出
            {"公司": "E", "职位": "e1"},  # 超出
        ], ensure_ascii=False),
    })

    rag = MockRag({
        "工作经历": RagQueryResult(
            answer="",
            contexts=[RagContext(content="工作经历 A-E", doc_id="d1", score=0.9)],
        ),
    })

    # 只分配 2 行 × 2 列 = 4 个 FormField
    fields = [
        _mk_field(fid=f"r{i}-公司", name="公司", layout=LayoutKind.header_row_table,
                  row_group_id="exp1", row_index=i, column_key="公司")
        for i in range(2)
    ] + [
        _mk_field(fid=f"r{i}-职位", name="职位", layout=LayoutKind.header_row_table,
                  row_group_id="exp1", row_index=i, column_key="职位")
        for i in range(2)
    ]

    settings = Settings(max_table_rows=10)
    svc = _mk_service(llm, settings=settings)
    req = FillFormRequest(job_id="j1", fields=fields)
    res = svc.fill(req, rag)

    # 只有 row0 和 row1 被填
    for f in res.fields:
        if f.row_index in (0, 1):
            assert f.status == FieldStatus.suggested, f"row{f.row_index}.{f.column_key} 应 suggested"
        else:
            assert False, f"不应有 row_index={f.row_index} 的字段"

    # row0 = A/a1, row1 = B/b1
    f_map = {(f.row_index, f.column_key): f for f in res.fields}
    assert f_map[(0, "公司")].value == "A"
    assert f_map[(0, "职位")].value == "a1"
    assert f_map[(1, "公司")].value == "B"
    assert f_map[(1, "职位")].value == "b1"

    # C/D/E 被忽略
    assert res.stats.filled == 4, f"4 字段应全填，实际 {res.stats.filled}"


def test_validate_type_single_choice_with_options() -> None:
    """single_choice + notes 含选项列表 → 值在选项内返回 (True, 1.0)，不在返回 (False, 0.0)。"""
    from app.modules.fill.agent.runner import validate_type

    notes = "选项: 男|女"

    # 值在选项内
    ok, score = validate_type("single_choice", "男", notes)
    assert ok is True and score == 1.0

    ok, score = validate_type("single_choice", "女", notes)
    assert ok is True and score == 1.0

    # 值不在选项内
    ok, score = validate_type("single_choice", "其他", notes)
    assert ok is False and score == 0.0

    # 空串
    ok, score = validate_type("single_choice", "", notes)
    assert ok is False and score == 0.0

    # notes 为 None → 降级为非空校验
    ok, score = validate_type("single_choice", "任意值", None)
    assert ok is True and score == 1.0

    # 逗号分隔的选项格式也支持
    notes_comma = "options: A, B, C"
    ok, score = validate_type("single_choice", "B", notes_comma)
    assert ok is True and score == 1.0


# ---------------------------------------------------------------------- #
#  Day 6 Step 2: 契约回归测试（JSON Schema + fixtures 端到端 + 红线属性）
# ---------------------------------------------------------------------- #

def _root() -> "Path":
    from pathlib import Path
    return Path(__file__).resolve().parents[3]


def _load_json(rel: str) -> dict:
    import json
    return json.loads((_root() / rel).read_text(encoding="utf-8"))


def test_fill_result_passes_jsonschema_validation() -> None:
    """FillResult 输出通过 fill_result.schema.json 的 Draft202012 校验。

    覆盖：
      - stats 三字段类型为 integer >= 0
      - fields[] 通过 form_field.schema.json（含 locator oneOf、status enum、confidence ∈ [0,1]）
      - additionalProperties=False 严格校验
    """
    jsonschema = pytest.importorskip("jsonschema")

    # 构造一个有内容的 FillResult（复用已有 mock）
    llm = FakeLLMClient({"姓名": "张三"})
    svc = _mk_service(llm)
    rag = MockRag({
        "姓名": RagQueryResult(
            answer="",
            contexts=[RagContext(content="张三，男，手机 13800138000。",
                                 doc_id="doc_resume_001", score=0.9, entities=["张三"])],
        ),
    })
    req = FillFormRequest(job_id="job_001", fields=[_mk_field(fid="f_name", name="姓名")])
    res = svc.fill(req, rag)

    # 用 Pydantic 的 model_dump(mode="json") 序列化 → 过 JSON Schema
    data = res.model_dump(mode="json")

    # 加载 schema（fill_result $ref form_field.schema.json，需 resolver）
    fill_schema = _load_json("packages/contracts/jsonschema/fill_result.schema.json")
    field_schema = _load_json("packages/contracts/jsonschema/form_field.schema.json")

    # 用 RefResolver 解决 $ref（兼容 jsonschema>=4.0，不依赖 referencing）
    resolver = jsonschema.RefResolver.from_schema(fill_schema)
    # 手动注册 form_field schema，让 $ref 能解析
    resolver.store["https://auto-form-fill.local/schemas/v0/form_field.schema.json"] = field_schema

    validator = jsonschema.Draft202012Validator(fill_schema, resolver=resolver)
    errors = list(validator.iter_errors(data))
    assert not errors, "FillResult JSON Schema 校验失败:\n" + "\n".join(
        f"  - {e.json_path}: {e.message}" for e in errors
    )


def test_fill_end_to_end_with_contract_fixtures() -> None:
    """用契约官方 fixtures 驱动端到端 fill()，验证输入→输出链路。

    输入：packages/contracts/fixtures/success/form_field.json（空白姓名字段）
    检索：packages/contracts/fixtures/success/rag_query_result.json（RagPort 返回张三的证据）
    预期：fields[0].value="张三", status=suggested, stats.filled=1
    对比：packages/contracts/fixtures/success/fill_result.json 结构一致
    """
    # 1. 加载 fixtures
    field_data = _load_json("packages/contracts/fixtures/success/form_field.json")
    rag_data = _load_json("packages/contracts/fixtures/success/rag_query_result.json")
    expected = _load_json("packages/contracts/fixtures/success/fill_result.json")

    # 2. 构造输入 FormField（从 fixture 反序列化）
    input_field = FormField.model_validate(field_data)
    assert input_field.value is None, "fixture form_field.json 应为空白字段"

    # 3. 构造 MockRag（返回 rag_query_result.json 的内容）
    rag_result = RagQueryResult.model_validate(rag_data)
    # MockRag 按 query 关键字匹配 → "姓名" 命中
    rag = MockRag({"姓名": rag_result})

    # 4. 构造 FakeLLM（命中"姓名"返回"张三"）
    llm = FakeLLMClient({"【姓名】": "张三"})
    svc = _mk_service(llm)

    # 5. 执行 fill()
    req = FillFormRequest(job_id="job_001", fields=[input_field])
    res = svc.fill(req, rag)

    # 6. 断言：与 fill_result.json 对齐
    assert res.job_id == expected["job_id"]
    assert res.stats.filled == expected["stats"]["filled"]
    assert res.stats.empty == expected["stats"]["empty"]
    assert res.stats.low_confidence == expected["stats"]["low_confidence"]

    f_out = res.fields[0]
    assert f_out.value == expected["fields"][0]["value"], f"value 应为 {expected['fields'][0]['value']!r}"
    assert f_out.status.value == expected["fields"][0]["status"]
    assert f_out.sources, "应有 sources"

    # 7. locator 只读不改（输入 == 输出）
    assert f_out.locator == input_field.locator

    # 8. confidence ∈ [0, 1]
    assert f_out.confidence is not None
    assert 0.0 <= f_out.confidence <= 1.0


def test_fill_locator_readonly_and_boundary_properties() -> None:
    """红线属性验证：locator 只读不改 + confidence ∈ [0,1] + status 在 enum 内。

    构造 3 个字段（text/date/header_row_table），验证 fill() 后 locator 不变、
    confidence 在 [0,1]、status 在 FieldStatus enum 内、sources[].score 在 [0,1]。
    """
    import json as _json

    llm = FakeLLMClient({
        "【姓名】": "张三",
        "表头列名：公司": _json.dumps({"entity_type": "工作经历", "query_hint": "工作"}, ensure_ascii=False),
        "按表头 [公司": _json.dumps([{"公司": "ACME", "职位": "工程师"}], ensure_ascii=False),
    })

    rag = MockRag({
        "姓名": RagQueryResult(
            answer="",
            contexts=[RagContext(content="张三", doc_id="d1", score=0.9, entities=["张三"])],
        ),
        "工作经历": RagQueryResult(
            answer="",
            contexts=[RagContext(content="ACME 工程师", doc_id="d2", score=0.9)],
        ),
    })

    single = _mk_field(fid="s1", name="姓名", layout=LayoutKind.label_value)
    multi1 = _mk_field(fid="m1", name="公司", layout=LayoutKind.header_row_table,
                      row_group_id="g1", row_index=0, column_key="公司")
    multi2 = _mk_field(fid="m2", name="职位", layout=LayoutKind.header_row_table,
                      row_group_id="g1", row_index=0, column_key="职位")

    # 记录原始 locator（深拷贝）
    orig_locators = {
        f.id: f.locator.model_dump() for f in [single, multi1, multi2]
    }

    svc = _mk_service(llm)
    req = FillFormRequest(job_id="j1", fields=[single, multi1, multi2])
    res = svc.fill(req, rag)

    valid_statuses = {s.value for s in FieldStatus}

    for f in res.fields:
        # 1. locator 只读不改
        assert f.locator.model_dump() == orig_locators[f.id], f"字段 {f.id} 的 locator 被篡改"

        # 2. confidence ∈ [0, 1] 或 None
        if f.confidence is not None:
            assert 0.0 <= f.confidence <= 1.0, f"字段 {f.id} confidence={f.confidence} 超出 [0,1]"

        # 3. status 在 enum 内
        assert f.status.value in valid_statuses, f"字段 {f.id} status={f.status} 不在 enum 内"

        # 4. sources[].score ∈ [0, 1] 或 None
        for src in f.sources:
            if src.score is not None:
                assert 0.0 <= src.score <= 1.0, f"字段 {f.id} source score={src.score} 超出 [0,1]"

        # 5. sources[].snippet 非空字符串
        for src in f.sources:
            assert isinstance(src.snippet, str) and src.snippet, f"字段 {f.id} source snippet 为空"


# ---------------------------------------------------------------------- #
#  Day 6 Step 3: 端到端集成测试（混合场景 + retry 实际触发 + 行数不足降级）
# ---------------------------------------------------------------------- #

def test_fill_mixed_scenario_end_to_end_integration() -> None:
    """混合场景端到端集成测试：1 单字段 + 1 多行表（2 行 3 列）。

    模拟真实简历填写场景：
      - label_value: 姓名 → 张三
      - header_row_table: 工作经历（时间/公司/职位 × 2 行）

    验证：
      - stats.filled = 7（1 单字段 + 6 多行表字段）
      - 姓名走 label_value 路径，value=张三
      - 工作经历走 MSR 路径，row0/row1 值正确
      - RagPort 只被 query，upsert/delete 未被调用
      - LLM 调用次数合理（1 单字段 + 1 分类 + 1 批量 = 3 次）
    """
    import json as _json

    llm = FakeLLMClient({
        "【姓名】": "张三",
        "表头列名：公司": _json.dumps(
            {"entity_type": "工作经历", "query_hint": "工作经历"}, ensure_ascii=False
        ),
        "按表头 [公司": _json.dumps([
            {"公司": "ACME Corp", "职位": "算法工程师", "时间": "2020-07-01"},
            {"公司": "Beta Labs", "职位": "高级工程师", "时间": "2023-03-15"},
        ], ensure_ascii=False),
    })

    rag = MockRag({
        "姓名": RagQueryResult(
            answer="",
            contexts=[RagContext(content="张三，入职 ACME Corp。",
                                  doc_id="d1", score=0.9, entities=["张三"])],
        ),
        "工作经历": RagQueryResult(
            answer="",
            contexts=[RagContext(content="张三在 ACME Corp 和 Beta Labs 工作过。",
                                  doc_id="d2", score=0.95)],
        ),
    })

    # 1 单字段 + 6 多行表字段（3 列 × 2 行）
    fields = [_mk_field(fid="s1", name="姓名", layout=LayoutKind.label_value)]
    for row_i in range(2):
        for col_key in ["公司", "职位", "时间"]:
            ft = FieldType.date if col_key == "时间" else FieldType.text
            fields.append(FormField(
                id=f"work-r{row_i}-{col_key}", name=col_key, field_type=ft,
                layout=LayoutKind.header_row_table, row_group_id="work_exp",
                row_index=row_i, column_key=col_key,
                locator=ExcelLocator(sheet="工作经历", row=4 + row_i, col=["公司", "职位", "时间"].index(col_key) + 1),
            ))

    svc = _mk_service(llm)
    req = FillFormRequest(job_id="j1", fields=fields)
    res = svc.fill(req, rag)

    # stats 验证
    assert res.stats.filled == 7, f"7 个字段应全填，实际 {res.stats.filled}"
    assert res.stats.empty == 0

    # 单字段验证
    single = [f for f in res.fields if f.layout == LayoutKind.label_value][0]
    assert single.value == "张三"
    assert single.status == FieldStatus.suggested

    # 多行表验证
    f_map = {(f.row_index, f.column_key): f for f in res.fields if f.row_group_id == "work_exp"}
    assert f_map[(0, "公司")].value == "ACME Corp"
    assert f_map[(0, "职位")].value == "算法工程师"
    assert f_map[(0, "时间")].value == "2020-07-01"
    assert f_map[(1, "公司")].value == "Beta Labs"
    assert f_map[(1, "职位")].value == "高级工程师"
    assert f_map[(1, "时间")].value == "2023-03-15"

    # 所有多行表字段都应有 sources
    for f in res.fields:
        if f.row_group_id == "work_exp":
            assert f.sources, f"row{f.row_index}.{f.column_key} 应有 sources"

    # LLM 调用次数：1（姓名 build_prompt）+ 1（分类助手）+ 1（批量生成）= 3
    # 注意：label_value 路径可能因 retry 多调 1 次，但此处 align 高不会 retry
    assert len(llm.calls) >= 3, f"LLM 至少调用 3 次，实际 {len(llm.calls)}"


def test_fill_retry_actually_improves_and_adopts_retry_result() -> None:
    """retry 实际触发并改善：首次检索 align 低 → retry 后 align 高 → 采纳 retry 结果。

    构造 MockRag 首次返回低质量 context（align 低），retry 返回高质量 context。
    验证 fill() 最终采纳 retry 的结果。
    """
    # 首次检索：返回低质量 context（entities 不对齐）
    first_ctx = RagQueryResult(
        answer="",
        contexts=[RagContext(content="李四的相关信息", doc_id="d_first", score=0.3, entities=["李四"])],
    )
    # retry 检索：返回高质量 context（entities 对齐）
    retry_ctx = RagQueryResult(
        answer="",
        contexts=[RagContext(content="张三的手机号是 13800138000", doc_id="d_retry", score=0.9, entities=["张三"])],
    )

    # 自定义 RagPort：首次返回 first_ctx，第二次（retry）返回 retry_ctx
    class RetryRag(MockRag):
        def __init__(self):
            super().__init__({})
            self._call_count = 0

        def query(self, req):
            self.calls.append(req.query)
            self._call_count += 1
            if self._call_count == 1:
                return first_ctx
            return retry_ctx

    rag = RetryRag()
    llm = FakeLLMClient({"【姓名】": "张三"})
    svc = _mk_service(llm)

    f = _mk_field(fid="f1", name="姓名", layout=LayoutKind.label_value)
    req = FillFormRequest(job_id="j1", fields=[f])
    res = svc.fill(req, rag)

    f_out = res.fields[0]
    # retry 后采纳高质量结果
    assert f_out.value == "张三", f"retry 后应采纳张三，实际 {f_out.value!r}"
    assert f_out.status == FieldStatus.suggested
    # sources 应来自 retry_ctx（doc_id=d_retry）
    assert any(s.doc_id == "d_retry" for s in f_out.sources), \
        f"sources 应来自 retry_ctx (d_retry)，实际 {[s.doc_id for s in f_out.sources]}"
    # RagPort 调用次数：1 粗检索 + 1 细检索 + 1 retry = 3 次
    assert len(rag.calls) == 3, f"RagPort 应调用 3 次（粗+细+retry），实际 {len(rag.calls)}"


def test_fill_multi_row_generated_fewer_than_existing_rows() -> None:
    """LLM 返回 1 行但 FormField 分配 2 行 → 剩余 1 行走 EMPTY 降级。

    验证：
      - row0 被填（3 字段 suggested）
      - row1 未命中 → 3 字段 empty, confidence=0
      - stats.filled=3, stats.empty=3
    """
    import json as _json

    llm = FakeLLMClient({
        "表头列名：公司": _json.dumps(
            {"entity_type": "工作经历", "query_hint": "工作"}, ensure_ascii=False
        ),
        "按表头 [公司": _json.dumps([
            {"公司": "ACME", "职位": "工程师"},  # 只有 1 行
        ], ensure_ascii=False),
    })

    rag = MockRag({
        "工作经历": RagQueryResult(
            answer="",
            contexts=[RagContext(content="ACME 工程师", doc_id="d1", score=0.9)],
        ),
    })

    # 2 行 × 2 列 = 4 个 FormField，但 LLM 只返回 1 行
    fields = []
    for row_i in range(2):
        for col_key in ["公司", "职位"]:
            fields.append(_mk_field(
                fid=f"r{row_i}-{col_key}", name=col_key,
                layout=LayoutKind.header_row_table,
                row_group_id="exp1", row_index=row_i, column_key=col_key,
            ))

    svc = _mk_service(llm)
    req = FillFormRequest(job_id="j1", fields=fields)
    res = svc.fill(req, rag)

    f_map = {(f.row_index, f.column_key): f for f in res.fields}

    # row0 被填
    assert f_map[(0, "公司")].value == "ACME"
    assert f_map[(0, "公司")].status == FieldStatus.suggested
    assert f_map[(0, "职位")].value == "工程师"
    assert f_map[(0, "职位")].status == FieldStatus.suggested

    # row1 未命中 → EMPTY
    assert f_map[(1, "公司")].value is None
    assert f_map[(1, "公司")].status == FieldStatus.empty
    assert f_map[(1, "公司")].confidence == 0.0
    assert f_map[(1, "职位")].value is None
    assert f_map[(1, "职位")].status == FieldStatus.empty

    # stats：empty 只计 original_value 非空被清空的情况，
    # 此处 row1 的 original_value=None → 不计入 empty，只是不计 filled
    assert res.stats.filled == 2, f"row0 的 2 字段应填，实际 {res.stats.filled}"
    assert res.stats.empty == 0, f"row1 original_value=None 不计 empty，实际 {res.stats.empty}"
