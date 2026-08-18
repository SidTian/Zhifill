# 2.2 Agent 实现方案 & 7 天开发路线图

> 负责人：裴思爽（PeiSishuang）
> 模块：`apps/api/app/modules/fill/`（仅改 `service.py`；`parsers/` 归 1.2/1.3）
> 交付范围：[FillPort](./port.py) 中的 `fill()`；`parse()` 不实现
> 工期：**7 天核心开发 + 2 天 buffer = 9 天**（落在 5-10 天区间）
> 依赖状态：`RagPort` 当前空实现（[rag/service.py](../rag/service.py)），单测全 mock；`TaskSpec` 契约草案待 1.3 出

---

## 一、目标与验收标准

### 1.1 核心目标（对应 [DIVISION.md](../../../../../../docs/DIVISION.md) §2.2）

连接知识图谱（2.1）与大模型，对 1.3 产出的 `FormField[]` 做**基于证据的建议填写**：

- 输入：`FillFormRequest(job_id, fields: FormField[])` + 注入的 `RagPort`
- 输出：`FillResult(job_id, fields: filled[], stats: {filled, empty, low_confidence})`
- 红线：**无证据 → value=null, confidence=0；不回写图谱**（[port.py](./port.py) docstring）

### 1.2 验收 checklist

- [ ] 单行 `label_value` 字段：有证据→`suggested`+`sources[]`；无证据→`empty`
- [ ] 多行 `header_row_table`：按 `row_group_id` 批量建议，`row_index` 连续，受 `max_table_rows` 保护
- [ ] `confidence ∈ [0,1]`，`low_confidence < 0.45` 字段标黄
- [ ] 单测：mock RagPort 即可跑通，不依赖真实模型/图谱
- [ ] 与 [fixtures/success/fill_result.json](../../../../../contracts/fixtures/success/fill_result.json) schema 一致

---

## 二、四大创新点（差异化竞争力）

### 创新点 1：双检索 + 证据实体对齐打分
**Dual-Retrieval Evidence-Aligned Scoring**

```
Step A — 粗检索 (mix/global)：对整组字段做一次宽检索，拉 Top-K context
Step B — 细检索 (local)：对每个字段/每行表用字段名+schema做定向细检索
Step C — 实体对齐：用 Token 重叠率匹配 context.entities 与 字段值候选
         score = Jaccard(字段实体提及, context实体) × context.score
         score < 阈值 → 直接判"无证据"，confidence 强制置 0
```

**为什么比"纯 LLM 判断无证据"强**：LLM 有时会编造"没有找到证据"的口吻，但仍生成值；代码层实体对齐是**硬约束**，过不了就直接空，不把幻觉判断交给模型自觉。

### 创新点 2：类型感知 Prompt 模板引擎
**Type-Aware Prompt Engine (TAPE)**

根据 `FormField.field_type`（见 [fill.py](../../../../../contracts/python/aff_contracts/fill.py) FieldType）动态注入：

| field_type | 输出约束（grammar） | 代码层兜底校验 |
|------------|---------------------|----------------|
| `text` | 长度 ≤ 100，不含 `\n` | 正则 `^.{1,100}$` |
| `date` | `YYYY-MM-DD` 格式 | `datetime.strptime` 校验 |
| `number` | 仅数字/小数点/可选负号 | `float(x)` + 范围 |
| `single_choice` | 必须在 options 中 | set membership |
| `multi` | `item1\|item2\|item3` | split 后逐项校验 |

**价值**：结构化的格式稳定性不再靠"大模型自觉"，用 Pydantic/Ollama JSONSchema + 正则双重锁。

### 创新点 3：多行表语义路由 + 实体类型预问
**Multi-Row Semantic Router (MSR)**

```
对 header_row_table (row_group_id = G):
  1. 先问 LLM（1 次，非流式）：
     "根据本人知识库，下列表头 {headers} 的每行最可能属于哪类实体？
      选项：工作经历 | 教育经历 | 项目经历 | 证书 | 获奖 | 其他
      只输出 JSON: {entity_type, query_hint}"
  2. 用 entity_type + query_hint 作为 RagQuery 的前缀，拉对应类型的 context
  3. 一次批量 LLM 调用生成全部行（JSON 数组），避免每行单独查
  4. 按 max_table_rows 截断
```

**收益**：把 N 行 × M 列次的 LLM 调用压缩为 **2 次**（预问 + 批量生成），**Token 消耗降低 60%+**，且语义定向更准（如问"工作经历"不会拉到"小学毕业学校"）。

### 创新点 4：置信度工程合成（非模型自言）
**Confidence Synthesis Formula (CSF)**

```
confidence =
  0.4 × context.score           (检索相关性，0-1)
+ 0.3 × entity_align_score      (创新点 1 的 Jaccard，0-1)
+ 0.3 × type_validity_score     (创新点 2 的类型合法度：1.0=完全通过，0.5=部分通过，0=非法)

if confidence < 0.30  →  value=null, status=empty, confidence=0
if confidence < 0.45  →  标 low_confidence（前端橙黄色），仍 suggested
if confidence ≥ 0.45  →  suggested
```

**关键**：confidence 不再是 LLM 生成的任意数字，而是**可解释、可审计**的三因子加权。前端可通过 `sources[].snippet` 追溯证据，满足 "不要瞎说" 的诉求。

---

## 三、模块架构与调用链（项目衔接）

### 3.1 整体数据流（与 [ARCHITECTURE.md](../../../../../../docs/ARCHITECTURE.md) 对齐）

```
                 ┌──────────────────────────────┐
                 │   1.3 TaskSemanticsPort       │
                 │  build_task_spec(structure)   │
                 └────────┬─────────────────────┘
                          │ TaskSpec dict (待契约化)
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                       2.2 FillService.fill()                     │
│                                                                   │
│  ┌──────────────────┐   ┌───────────────────┐   ┌─────────────┐  │
│  │  ① FieldGrouper  │──▶│  ② QueryPlanner   │──▶│  ③ Runner   │  │
│  │  (按 row_group_id│   │  (创新点1双检索   │   │  (LLM+grammar│  │
│  │   + field_type)  │   │   + CSF 打分)     │   │   创新点2/3)│  │
│  └──────────────────┘   └────────┬──────────┘   └──────┬──────┘  │
│                                  │                      │         │
│                          ┌───────▼────────┐    ┌───────▼──────┐  │
│                          │   RagPort.query│    │   ④ PostProc │  │
│                          │   (RagPort注入) │    │   创新点4 CSF│  │
│                          └────────────────┘    └───────┬──────┘  │
│                                                         │         │
│                                                  ┌──────▼──────┐  │
│                                                  │ FillResult  │  │
│                                                  │  +stats     │  │
│                                                  └──────┬──────┘  │
└─────────────────────────────────────────────────────────┼─────────┘
                                                          │
                                                          ▼
                                          ┌───────────────────────────┐
                                          │ 统筹 orchestrator + 前端   │
                                          │ 预览 (sources/suggested)   │
                                          │ → 用户确认 → export 回填   │
                                          └───────────────────────────┘
```

### 3.2 与上下游端口衔接（无契约侵入）

| 方向 | 依赖契约 | 衔接方式 |
|------|----------|----------|
| **← 1.3** | TaskSpec dict（1.3 先出草案） | `FillService.fill()` 现在签名是 `(FillFormRequest, RagPort)` → 内部**可选**接收 `task_spec`（1.3 有了以后通过 orchestrator 注入到 fields.notes 或额外参数），不破坏 FillPort |
| **↔ 2.1** | [RagPort](../rag/port.py)：`query(RagQueryRequest) -> RagQueryResult` | 只调 `query()`；`response_format="json_object"` 用于多行；不碰 `upsert/delete`（不回写图谱） |
| **→ 统筹** | FillResult + FormField.locator | 严格按契约返回；locator 只读不改，1.2 产出后 2.2 原样保留 |

---

## 四、7 天开发路线图（+ 2 天 buffer）

### Day 1 — 骨架与契约落地（约 4h）

**目标**：在不改变 FillPort 的前提下，为 `service.py` 搭出内部 4 组件框架，并补齐 agent 依赖声明。

**交付物**：

1. 修改 [pyproject.toml](../../../pyproject.toml)：
   - 新增 `agent` extra：`openai>=1.40,<2`
   - 同步更新 `requirements.lock`（走统筹 review PR）
2. 新文件：`apps/api/app/modules/fill/agent/` 内部子模块（4 个文件，不含 parsers/）
   - `__init__.py`
   - `grouper.py`（FieldGrouper，创新点 3 分组）
   - `planner.py`（QueryPlanner + 双检索 + CSF 得分，创新点 1/4）
   - `runner.py`（LLM 调用 + grammar 约束 + Type-Aware，创新点 2）
3. `FillService.fill()` 从抛异常改为**调用 4 组件流水线**（单测 mock 全部内部组件即可跑通）

**验收**：`FillService.fill()` 对空 fields 返回 `FillResult(job_id, fields=[], stats={0,0,0})`，不依赖真实 LLM/RAG。

### Day 2 — FieldGrouper + QueryPlanner（创新点 1 与 3 基础，约 6h）

**目标**：字段分组 + 双检索 + 证据实体对齐。

**交付物**：

1. `grouper.py`：
   - 按 `row_group_id` 分组（header_row_table）
   - 按 `field_type` 子分组（text/date/number 不同约束模板）
   - 输出 `list[FieldGroup]`
2. `planner.py`：
   - `plan_queries(groups: list[FieldGroup]) -> list[QueryPlan]`
   - QueryPlan = (粗检索 query, 细检索 queries per field, 预期 JSON schema 草稿)
   - 实现 `entity_align_score(snippet: str, value_candidate: str, entities: list[str]) -> float`（Jaccard 实现）
3. CSF 三因子算法函数：`calc_confidence(...) -> float`，阈值常量 `LOW_CONF_THRESHOLD=0.45`、`EMPTY_THRESHOLD=0.30`

**验收**：单测覆盖 3 组场景——单行单字段、同一 row_group 多行、空 fields。

### Day 3 — LLM Runner + 类型感知 Prompt 模板（创新点 2，约 6h）

**目标**：LLM 调用抽象层 + grammar 强制约束 + 5 种 field_type 模板。

**交付物**：

1. `runner.py`：
   - `LLMClient` 抽象：`__init__(settings: Settings)`，对齐 [config.py](../../../app/core/config.py) / [settings.py](../../../../../contracts/python/aff_contracts/settings.py) 的 `llm_provider/api_base/api_key/query_model(or llm_model)`
   - openai SDK 统一调用：Qwen DashScope 兼容模式 + Ollama 模式仅切 `base_url`
   - Ollama 时：若请求带 JSON schema → 透传 `format=<schema>` 走 GBNF grammar（100% 合法 JSON）
   - DeepSeek-R1 兼容：过滤 `reasoning_content` 字段
   - 流式**默认关闭**（单轮，不做 UI 渐进）
2. 5 套 Prompt 模板（中文，对齐 `summary_language=Chinese`）：
   ```
   text_tmpl = "根据以下知识库证据，为字段【{field_name}】（类型：文本，≤100字）生成填写值。无证据请输出空串。"
   date_tmpl = "...日期格式严格 YYYY-MM-DD。..."
   number_tmpl = "...仅数字。..."
   multi_row_tmpl = "按表头 [{headers}] 生成最多 {max_rows} 行 JSON 数组，每行一个对象。无证据输出 []。"
   ...
   ```
3. 类型校验器 `validate_type(field_type: str, value: str) -> tuple[bool, float]`：通过/部分通过/非法三态 + 合法度分

**验收**：mock `openai.OpenAI`，验证 5 种 field_type 的 prompt 都正确注入，且 validate_type 对边界用例（空串/非法日期/数字带汉字）返回正确得分。

### Day 4 — PostProc 串联 + FillResult 拼装（创新点 4 落地，约 4h）

**目标**：把前三步输出串成 [FillResult](../../../../../contracts/python/aff_contracts/fill.py)。

**交付物**：

1. 在 `service.py` 实现完整 Pipeline：
   ```python
   def fill(self, request, rag):
     groups = FieldGrouper.group(request.fields)
     for g in groups:
       plans  = QueryPlanner.plan(g)
       ctx    = rag.query(plans.coarse)        # 粗检索
       ctxs   = [rag.query(p) for p in plans.fine] # 细检索
       vals   = Runner.generate(g, plans, ctx+ctxs)
       for field, raw_value in zip(g.fields, vals):
           ok, tv_score = validate_type(field.field_type, raw_value)
           conf = CSF(..., entity_align_score(raw_value, ctxs, field.name), tv_score)
           if   conf < EMPTY_THRESHOLD:  value=None; status=empty; conf=0
           elif conf < LOW_CONF_THRESHOLD: value=raw; status=suggested; stats.low_confidence++
           else:                          value=raw; status=suggested; stats.filled++
           field.sources = [SourceRef(snippet=c.content, doc_id=c.doc_id, score=c.score) for c in ctxs]
     return FillResult(job_id=request.job_id, fields=..., stats=...)
   ```
2. `stats` 统计：`filled / empty / low_confidence` 三计数；空字段不计入 empty（原有值不为 null 且被留空时计）
3. **红线 enforcement**：所有字段无论什么结果，**不调用 RagPort.upsert/delete**（单测可断言：RagPort mock 仅调用 `.query`）

**验收**：与 [fixtures/success/fill_result.json](../../../../../contracts/fixtures/success/fill_result.json) 同结构字段对比，`FormField.model_validate(fields[i])` 全部通过。

### Day 5 — 多行语义路由（创新点 3 完整版，约 6h）

**目标**：header_row_table 的 entity_type 预问 + 批量 JSON 压缩调用。

**交付物**：

1. `planner.py` 新增 `pre_determine_entity_type(group: FieldGroup, runner: LLMClient) -> tuple[str, str]`：
   - 用 1 次小模型调用（可复用 settings.query_model）返回 `{entity_type, query_hint}`
   - 失败时 fallback：entity_type="其他"，query_hint=group.name
2. Runner 新增 `generate_multi_row(group, entity_type, hint, contexts, schema, max_rows)`：
   - 走 `response_format="json_object"` 或 Ollama `format=JSONSchema`
   - 输出严格 JSON 数组，按 `max_rows=settings.max_table_rows`（[config.py](../../../app/core/config.py)）截断
3. `row_index` 自动分配（连续从 0 开始）、`row_group_id` 保留原值、`column_key` 对齐 headers

**验收**：单测给 3 列（时间/组织/角色）+ 上下文含 2 条工作经历，能正确产出 row_group_id 相同、row_index 0/1、各列 value 正确、未超 max_table_rows。

### Day 6 — 单测补全 + 契约回归（约 5h）

**目标**：覆盖率 ≥ 80%；跑通仓库现有契约测试；新增 fixture 兼容。

**交付物**：

1. 新文件：`apps/api/tests/test_fill_agent.py`（或 `apps/api/tests/modules/test_fill.py`，与 [tests/test_upload_storage.py](../../../tests/test_upload_storage.py) 风格一致）
   - `test_fill_empty_fields()`
   - `test_fill_label_value_with_evidence()`
   - `test_fill_label_value_no_evidence_returns_empty()`（红线）
   - `test_fill_header_row_multi_row_with_hint()`
   - `test_fill_no_rag_upsert_called()`（红线：不回写）
   - `test_fill_stats_counts_correct()`
   - `test_fill_confidence_below_threshold_force_empty()`
   - `test_fill_deepseek_reasoning_content_stripped()`
2. 运行 `pytest apps/api/tests -v`，保证：
   - 新增 8 个用例全通过（mock RagPort，mock openai）
   - 已有 [contracts/test_fixtures.py](../../../tests/contracts/test_fixtures.py) 不回归
3. （可选）新增 fixtures 兼容：构造一个 `FillResult` 样本并通过 `fill_result.schema.json` 校验

**验收**：pytest 绿；不引入真实 LLM/图谱依赖。

### Day 7 — 本地联调 + 文档收尾（约 4h）

**目标**：把实现串进 orchestrator（不侵入代码），产出 Demo 说明文档。

**交付物**：

1. 把 `FillService.fill()` 接入方式在文档中说明，并手动在 local 调 `get_fill_service().fill()` 打一组端到端：
   - 用 fake RagPort 返回 [rag_query_result.json](../../../../../contracts/fixtures/success/rag_query_result.json)
   - 用 [form_field.json](../../../../../contracts/fixtures/success/form_field.json) 作 fields 输入
   - 输出 stats 与值与 fixture 期望值对齐
2. 更新 `apps/api/app/modules/fill/README.md`：说明内部 4 组件 Pipeline 与 4 个创新点，标注"parse() 不实现（1.2/1.3 职责）"
3. 更新 [SELECT_MODEL.md](./SELECT_MODEL.md) §待办，勾掉依赖声明与单测骨架两项，保留实测对比项。

**验收**：统筹侧 review 模块输出；README 使新人能理解 fill() 运行机制。

---

### Buffer 2 天（Day 8-9，可选做）

| 项 | 内容 | 状态 |
|----|------|------|
| 实测对比 | 本地 Ollama 跑 Qwen3-32B vs DeepSeek-R1-Distill-14B，跑一组简历→FillResult 字段命中率，补充进 SELECT_MODEL.md | ⏳ 依赖 DeepSeek API Key 充值（402 报错，详见 BENCHMARK_REPORT.md §六） |
| 并行优化 | 同一字段组内的多个细检索用 `asyncio.gather` 并发（Runner 改 async 版，settings 层走 async openai SDK） | ✅ 已完成（2026-08-18）：`service.py fill()` 中多字段 `fine_queries` 走 `ThreadPoolExecutor(max_workers=4)` 并发，单字段保持串行避免开销 |
| Prompt 缓存 | 同 schema + 同 headers 的 multi_row_tmpl Prompt 做 LRU 缓存（避免重复构建） | ✅ 已完成（2026-08-18）：`build_multi_row_schema` 加 `@lru_cache(maxsize=64)` |
| 1.3 TaskSpec 接入 | 等 1.3 草案出后，注入 `build_task_spec()` 的结果到 QueryPlanner；**不改 FillPort 签名**，用 fields.notes 传递（契约优先） | ⏳ 依赖 1.3 外部团队 |

---

## 五、关键代码骨架（可直接 copy 到文件）

> 注：以下骨架仅为「落地起点」，完整实现按 Day 1-7 写。

### 5.1 `apps/api/app/modules/fill/agent/__init__.py`（空即可）

```python
"""Internal 2.2 agent pipeline submodule.

Not exposed via port.py — only used inside FillService.fill().
"""
```

### 5.2 `apps/api/app/modules/fill/agent/grouper.py`（Day 1 骨架）

```python
from __future__ import annotations

from dataclasses import dataclass, field

from aff_contracts import FormField
from aff_contracts.fill import LayoutKind


@dataclass
class FieldGroup:
    key: str                              # row_group_id or f"single-{field.id}"
    layout: LayoutKind
    fields: list[FormField] = field(default_factory=list)
    headers: list[str] | None = None      # header_row_table 的列名（从 column_key 汇总）


class FieldGrouper:
    @staticmethod
    def group(fields: list[FormField]) -> list[FieldGroup]:
        by_key: dict[str, FieldGroup] = {}
        for f in fields:
            if f.layout == LayoutKind.header_row_table and f.row_group_id:
                key = f.row_group_id
            else:
                key = f"single-{f.id}"
            if key not in by_key:
                by_key[key] = FieldGroup(key=key, layout=f.layout)
            by_key[key].fields.append(f)

        for g in by_key.values():
            if g.layout == LayoutKind.header_row_table:
                col_keys = sorted({f.column_key for f in g.fields if f.column_key})
                g.headers = col_keys or None
        return list(by_key.values())
```

### 5.3 `apps/api/app/modules/fill/agent/planner.py`（Day 2 骨架）

```python
from __future__ import annotations

from dataclasses import dataclass


LOW_CONF_THRESHOLD = 0.45
EMPTY_THRESHOLD = 0.30
RETRIEVAL_WEIGHT = 0.40
ENTITY_ALIGN_WEIGHT = 0.30
TYPE_VALIDITY_WEIGHT = 0.30


@dataclass
class QueryPlan:
    group_key: str
    coarse_query: str
    fine_queries: dict[str, str]   # field.id -> query
    expected_schema: dict         # JSONSchema 草稿，送 runner/ollama format


class QueryPlanner:
    @staticmethod
    def plan(group) -> QueryPlan:
        name_ctx = "、".join({f.name for f in group.fields})
        coarse = f"本人知识库中关于：{name_ctx} 的事实。"
        fine = {f.id: f"本人的【{f.name}】（类型 {f.field_type}）具体取值与来源是什么？" for f in group.fields}
        return QueryPlan(group_key=group.key, coarse_query=coarse, fine_queries=fine, expected_schema={})  # Runner 层补 schema

    @staticmethod
    def entity_align_score(value: str, snippet: str, entities: list[str] | None) -> float:
        if not value or not snippet:
            return 0.0
        v_tokens = set(value.replace(" ", ""))
        s_tokens = set(snippet.replace(" ", "")) | set((entities or []))
        inter = v_tokens & s_tokens
        union = v_tokens | s_tokens
        return len(inter) / len(union) if union else 0.0

    @staticmethod
    def calc_confidence(retrieval_score: float | None, align_score: float, type_validity: float) -> float:
        r = retrieval_score or 0.0
        return min(max(RETRIEVAL_WEIGHT * r + ENTITY_ALIGN_WEIGHT * align_score + TYPE_VALIDITY_WEIGHT * type_validity, 0.0), 1.0)
```

### 5.4 `apps/api/app/modules/fill/agent/runner.py`（Day 3 骨架）

```python
from __future__ import annotations

from typing import Any

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - 未装 agent extra 时走 mock
    OpenAI = Any  # type: ignore[assignment,misc]

from aff_contracts import Settings


TEXT_TMPL = """你是填写助手。根据以下知识库证据，为字段【{name}】生成填写值。
类型约束：{type_constraint}。
严格只输出填写值本身；没有证据输出空字符串。不要加解释。

证据片段：
{contexts}
"""


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        self.model = settings.query_model or settings.llm_model
        if settings.llm_provider == "ollama" and not settings.llm_api_base.endswith("/v1"):
            base = settings.llm_api_base.rstrip("/") + "/v1"
        else:
            base = settings.llm_api_base
        self._client = OpenAI(api_key=settings.llm_api_key or "ollama", base_url=base)

    def complete(self, prompt: str, *, schema: dict | None = None, temperature: float = 0.0) -> str:
        kwargs: dict[str, Any] = dict(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            stream=False,
        )
        # 注：Ollama 原生 format 参数在 /v1/chat/completions 兼容层需透传 extra_body；后续实现期补
        resp = self._client.chat.completions.create(**kwargs)
        content = resp.choices[0].message.content or ""
        return content.strip()


def validate_type(field_type: str, value: str) -> tuple[bool, float]:
    if value == "":
        return False, 0.0
    if field_type == "date":
        from datetime import datetime
        try:
            datetime.strptime(value, "%Y-%m-%d"); return True, 1.0
        except ValueError:
            return False, 0.0
    if field_type == "number":
        try:
            float(value); return True, 1.0
        except ValueError:
            return False, 0.0
    if field_type == "text":
        return (len(value) <= 100 and "\n" not in value), (1.0 if len(value) <= 100 and "\n" not in value else 0.5)
    return True, 1.0
```

### 5.5 `apps/api/app/modules/fill/service.py`（Day 4 骨架，替换原 NotImplemented）

```python
from __future__ import annotations

from aff_contracts import FillFormRequest, FillResult, FillStats, FieldStatus
from aff_contracts.common import SourceRef

from app.core.errors import NotImplementedModule
from app.modules.fill.agent.grouper import FieldGrouper
from app.modules.fill.agent.planner import (
    EMPTY_THRESHOLD, LOW_CONF_THRESHOLD, QueryPlanner,
)
from app.modules.fill.port import FillPort
from app.modules.rag.port import RagPort


class FillService(FillPort):
    def parse(self, request):
        # 1.2/1.3 职责；2.2 不实现（OWNERS.md L31 勿覆盖他人 service）
        raise NotImplementedModule("fill", "parse")

    def fill(self, request: FillFormRequest, rag: RagPort) -> FillResult:
        from aff_contracts.rag import RagQueryRequest

        groups = FieldGrouper.group(request.fields)
        stats = FillStats()

        for group in groups:
            plan = QueryPlanner.plan(group)
            coarse = rag.query(RagQueryRequest(query=plan.coarse_query, mode="mix"))

            fine_ctxs = {}
            for fid, q in plan.fine_queries.items():
                fine_ctxs[fid] = rag.query(RagQueryRequest(query=q, mode="local"))

            for f in group.fields:
                # ------ 简化版：单字段单值；Day5 再扩 multi_row 批量 ------
                ctx = fine_ctxs.get(f.id) or coarse
                raw_value = ""  # 接 Runner.generate()
                # TODO(day3): 接入 LLMClient + type-aware prompt + validate_type
                type_validity = 1.0 if raw_value else 0.0
                ctx_top = ctx.contexts[0] if ctx.contexts else None
                align = QueryPlanner.entity_align_score(raw_value, ctx_top.content if ctx_top else "", ctx_top.entities if ctx_top else None)
                conf = QueryPlanner.calc_confidence(ctx_top.score if ctx_top else None, align, type_validity)

                if conf < EMPTY_THRESHOLD:
                    f.value = None; f.confidence = 0.0; f.status = FieldStatus.empty; stats.empty += 1
                else:
                    f.value = raw_value or None
                    f.confidence = round(conf, 3)
                    f.status = FieldStatus.suggested
                    if conf < LOW_CONF_THRESHOLD:
                        stats.low_confidence += 1
                    stats.filled += 1
                f.sources = [SourceRef(snippet=c.content, doc_id=c.doc_id, score=c.score) for c in (ctx.contexts[:3])]

        return FillResult(job_id=request.job_id, fields=request.fields, stats=stats)


def get_fill_service() -> FillPort:
    return FillService()
```

### 5.6 `apps/api/tests/test_fill_agent.py`（Day 6 骨架，3 个最小用例）

```python
from __future__ import annotations

from aff_contracts import (
    FillFormRequest, FillResult, FormField, FieldStatus,
    RagQueryResult, RagContext, SourceRef, ExcelLocator,
)
from aff_contracts.fill import FieldType, LayoutKind


class MockRag:
    def __init__(self, results: dict[str, RagQueryResult]) -> None:
        self.results = results
        self.calls: list[str] = []

    def query(self, req):
        self.calls.append(req.query)
        for q, r in self.results.items():
            if q in req.query:
                return r
        return RagQueryResult(answer="", contexts=[])

    def upsert(self, *a, **kw):
        raise AssertionError("fill() 不可调用 RagPort.upsert")

    def delete(self, *a, **kw):
        raise AssertionError("fill() 不可调用 RagPort.delete")


def _mk_field(fid="f1", name="姓名", layout=LayoutKind.label_value, **kw):
    return FormField(
        id=fid, name=name, field_type=FieldType.text, value=None, original_value=None,
        required=True, confidence=None, sources=[], status=FieldStatus.empty,
        layout=layout, row_group_id=kw.get("row_group_id"),
        row_index=kw.get("row_index"), column_key=kw.get("column_key"),
        locator=kw.get("locator") or ExcelLocator(sheet="S", row=1, col=1),
        notes=None,
    )


def test_fill_empty_fields():
    from app.modules.fill import get_fill_service
    svc = get_fill_service()
    req = FillFormRequest(job_id="j1", fields=[])
    res = svc.fill(req, MockRag({}))
    assert isinstance(res, FillResult) and res.job_id == "j1"
    assert res.stats.filled == 0 and res.stats.empty == 0


def test_fill_no_evidence_returns_empty():
    from app.modules.fill import get_fill_service
    svc = get_fill_service()
    f = _mk_field()
    req = FillFormRequest(job_id="j1", fields=[f])
    res = svc.fill(req, MockRag({}))  # 无 context
    assert res.fields[0].value is None and res.fields[0].status == FieldStatus.empty
    assert res.stats.empty >= 1 and res.stats.filled == 0


def test_fill_no_rag_upsert_called():
    from app.modules.fill import get_fill_service
    svc = get_fill_service()
    rag = MockRag({"姓名": RagQueryResult(answer="张三", contexts=[RagContext(content="张三", doc_id="d", score=0.9, entities=["张三"])])})
    req = FillFormRequest(job_id="j1", fields=[_mk_field()])
    svc.fill(req, rag)
    assert rag.calls  # 确认有 query
```

---

## 六、与项目衔接的注意事项（反复强调）

| # | 要点 | 参照 |
|---|------|------|
| 1 | **不实现 `parse()`**，仍抛 `NotImplementedModule` | [README.md](./README.md) + [OWNERS.md](../../../../../../docs/OWNERS.md#L31) |
| 2 | 只依赖 `RagPort` Protocol，**不 `from app.modules.rag.service import`** | [CONTRACTS.md](../../../../../../docs/CONTRACTS.md) 协作者规则 |
| 3 | 不改契约包；若要加 `TaskSpec` 类型，先由 1.3 起 contracts PR | [OWNERS.md](../../../../../../docs/OWNERS.md#L26) |
| 4 | 输出字段的 `locator` **只读不改**，原样保留 | [ARCHITECTURE.md](../../../../../../docs/ARCHITECTURE.md) locator 规则 |
| 5 | **禁止**任何代码路径调用 `RagPort.upsert/delete` | [ACCEPTANCE.md](../../../../../../docs/ACCEPTANCE.md) §7 |
| 6 | 新增 `openai` 依赖须走 [pyproject.toml](../../../pyproject.toml) `agent` extra + 更新 requirements.lock + 统筹 review | [ENVIRONMENT.md](../../../../../../docs/ENVIRONMENT.md) 禁止事项 §2 |
| 7 | settings 读取：对齐 [AppConfig](../../../app/core/config.py) / [Settings](../../../../../contracts/python/aff_contracts/settings.py) 的字段，不加新 settings key 除非走契约 PR | openapi.yaml Settings schema |
| 8 | `max_table_rows` 统一读 settings，不要硬编码 | config.py + openapi.yaml |

---

## 七、风险与 buffer 应对

| 风险 | 概率 | 影响 | buffer 对策 |
|------|------|------|------------|
| 1.3 TaskSpec 契约迟迟未定 | 中 | 动态 Prompt 少了 TaskSpec 层语义 | 先按 fields.name/field_type 本身做 Prompt，TaskSpec 来了后作为**增强输入**注入（不改 FillPort 签名），保持向后兼容 |
| 2.1 RagPort 的 `contexts[].entities` 始终为 None | 中 | 创新点 1 实体对齐得分低 | 降级：仅用 snippet 文本 Jaccard（不要 entities），权重 0.30 转给 retrieval_score |
| openai SDK 依赖引入争议（精简 extra） | 低 | 统筹要求换更轻客户端 | `runner.py` 保留 abstract，另加 `SimpleHTTPClient` 实现（只用 `requests` post，requests 已由 fastapi 间接带入） |
| Qwen API / Ollama 本地不可用时 demo 卡住 | 中 | 联调期阻塞 | Runner 内置 `FakeLLMClient`：直接从 contexts 中抽 token 最长字符串作值，CI/demo 不依赖真模型 |

---

## 八、9 天后的交付清单（最终 check）

- [x] `FillService.fill()` 实现（service.py）
- [x] 4 个子模块：grouper / planner / runner / PostProc（PostProc 合并在 service.py）
- [x] pyproject.toml 新增 `agent` extra + requirements.lock 更新 PR
- [x] tests/test_fill_agent.py（42 个用例，pytest 全绿）
- [x] README.md 更新：Pipeline 与创新点说明 + `parse()` 未实现声明
- [x] SELECT_MODEL.md §待办更新
- [x] 本地端到端：fake RagPort + 契约 fixtures 对齐 fill_result.schema.json
- [x] 不回写图谱断言（rag.upsert/delete 未被调用）

### Buffer 优化项交付清单（2026-08-18 补充）

- [x] 并行细检索优化（`ThreadPoolExecutor` max_workers=4）
- [x] Prompt LRU 缓存（`build_multi_row_schema` @lru_cache）
- [x] `referencing` 替代 `RefResolver`（兼容降级）
- [x] BENCHMARK 统计 Bug 修复（报错调用不再被过滤为幽灵 0 值）
- [x] requirements.lock 同步更新（openai==1.109.1 + 5 个传递依赖）
- [x] 核心分支 `logger.info` 日志补全（fill 入口/分组/路径分流/打分/重试/PostProc/MSR 4 步）

（完）
