# Day 6-7 合并执行计划：收尾与交付

> 编写日期：2026-08-16
> 前置状态：Day 1-5 全部完成（29/29 测试通过，Demo 端到端 100% 填写率）
> 本计划目标：把剩余的覆盖率补全、契约回归、端到端联调、文档收尾合并为一份可顺序执行的清单

---

## 当前已完成基线

| 项 | 状态 |
|----|------|
| `service.py` FillService.fill() 完整 Pipeline | ✅ |
| `agent/` 4 子模块（grouper/planner/runner/__init__） | ✅ |
| 4 大创新点（Dual-Retrieval / TAPE / MSR / CSF） | ✅ |
| `tests/test_fill_agent.py` 29 个用例 | ✅ 全通过 |
| `pyproject.toml` `agent` extra（openai>=1.40,<2） | ✅ |
| `BENCHMARK_REPORT.md` 模型基准对比 | ✅ |
| `demo_msr.py` 端到端 Demo（工作经历+证书） | ✅ |

---

## 执行计划（7 步，按依赖顺序）

### Step 1：补全 Day 6 边缘用例（覆盖率冲刺）

**目标**：把当前 29 个用例扩展到 35+，覆盖尚未测到的分支

**新增测试清单**（追加到 [test_fill_agent.py](../../tests/test_fill_agent.py)）：

| 用例 | 覆盖分支 | 依赖 |
|------|----------|------|
| `test_fill_deepseek_reasoning_content_stripped` | DeepSeek-R1 `reasoning_content` 字段过滤 | mock openai SDK 返回带 reasoning_content 的 message |
| `test_fill_confidence_low_threshold_marks_yellow` | conf ∈ [0.30, 0.45) → suggested + low_confidence 计数+1 | 构造 retrieval_score=0.5, align=0.1 的 context |
| `test_fill_confidence_empty_threshold_forces_null` | conf < 0.30 → value=None, confidence=0 | 构造 retrieval_score=0.1 的低分 context |
| `test_fill_retrieval_score_none_treated_as_zero` | contexts 为空 → retrieval_score=None → conf=0 | MockRag 返回空 contexts |
| `test_fill_max_retries_exhausted_falls_back` | retry 循环 3 次仍未改善 → 用首次结果 | patch _score_field 返回固定低 align |
| `test_fill_multi_row_generated_exceeds_existing_rows` | LLM 返回 5 行但 FormField 只分配 2 行 → 多余行忽略 | max_table_rows=5 但 fields 只有 2 行 |
| `test_validate_type_single_choice_with_options` | single_choice 字段 + notes 含 `选项：A|B|C` | validate_type("single_choice", "A", "选项：A\|B\|C") |

**验收**：`pytest tests/test_fill_agent.py -q` → 35+ passed

---

### Step 2：契约回归测试（fixtures 对齐）

**目标**：确保 `FillResult` 输出与 [fill_result.schema.json](../../../../../packages/contracts/jsonschema/fill_result.schema.json) + [fill_result.json](../../../../../packages/contracts/fixtures/success/fill_result.json) 对齐

**新增测试**（追加到 `test_fill_agent.py` 末尾）：

```python
def test_fill_result_matches_fixture_schema():
    """FillResult 输出通过 fill_result.schema.json 校验。"""
    import json
    from pathlib import Path
    jsonschema = pytest.importorskip("jsonschema")
    root = Path(__file__).resolve().parents[3]
    schema = json.loads((root / "packages/contracts/jsonschema/fill_result.schema.json").read_text("utf-8"))
    data = res.model_dump(mode="json")
    jsonschema.Draft202012Validator(schema).validate(data)
```

**验证点**：
- `stats` 三字段类型为 integer ≥ 0
- `fields[].locator` 只读不改（输入 locator == 输出 locator）
- `confidence` ∈ [0, 1]，`status` 在 enum 内
- 用 [form_field.json](../../../../../packages/contracts/fixtures/success/form_field.json) 做输入 + [rag_query_result.json](../../../../../packages/contracts/fixtures/success/rag_query_result.json) 做 RagPort 返回 → 断言输出与 [fill_result.json](../../../../../packages/contracts/fixtures/success/fill_result.json) 结构一致

**验收**：`pytest tests/contracts/test_fixtures.py tests/test_fill_agent.py -q` → 全绿，无回归

---

### Step 3：端到端联调（契约 fixtures 驱动）

**目标**：用契约官方 fixtures 跑一次完整 `fill()`，验证「输入→输出」链路

**实现方式**：在 [demo_msr.py](./demo_msr.py) 中新增 `main_with_fixtures()` 函数（或新建 `demo_fixtures.py`）：

```python
def main_with_fixtures():
    """用契约 fixtures 跑端到端：form_field.json → fill() → 对比 fill_result.json。"""
    # 1. 加载 form_field.json 作为输入 FormField
    # 2. 加载 rag_query_result.json 作为 MockRag 返回
    # 3. 调 FillService.fill()
    # 4. 断言 stats.filled == 1, fields[0].value == "张三"
    # 5. 输出与 fill_result.json 结构对比（value/confidence 可不同，但结构一致）
```

**验收**：端到端跑通，输出写入 `demo_fixtures_output.txt`，stats.filled=1

---

### Step 4：README.md 更新

**目标**：让新人能通过 README 理解 fill() 运行机制

**更新文件**：[README.md](./README.md)

**新增章节**：

```markdown
## Fill Pipeline 架构

### 4 组件流水线
FieldGrouper → QueryPlanner → Runner → PostProc(CSF)

### 4 大创新点
1. Dual-Retrieval + 实体对齐打分
2. Type-Aware Prompt Engine (TAPE)
3. Multi-Row Semantic Router (MSR)
4. Confidence Synthesis Formula (CSF)

### layout 路由
- label_value → 逐字段 score + retry
- header_row_table → MSR 4 步（预问 → 定向检索 → 批量生成 → 回写）

### 红线
- 无证据 → value=null, confidence=0
- 不回写图谱（不调 upsert/delete）
- max_table_rows 限制生成行数

### parse() 不实现
parse() 由 1.2/1.3 负责，本模块抛 NotImplementedModule。
```

**验收**：README 包含 Pipeline 图、创新点说明、红线声明

---

### Step 5：SELECT_MODEL.md 待办勾选

**目标**：更新 [SELECT_MODEL.md](./SELECT_MODEL.md) §8 待办，反映已完成项

**更新内容**：

```markdown
## 8. 待办

- [x] 统筹 review 本文档（新文件，须知会）。
- [ ] 与 2.1 对齐 `RagQueryResult.contexts` 中 `entities` 字段的实际填充情况。
- [ ] 等 1.3 `TaskSpec` 契约草案，确定动态 Prompt 模板入参结构。
- [x] 在 pyproject.toml 新增 agent extra（openai SDK）并更新 requirements.lock。
- [x] 搭 mock-based fill() 单测骨架（不依赖真实模型 / 真实图谱）→ 已有 29 个用例。
- [x] 实测对比：Qwen vs DeepSeek → 见 BENCHMARK_REPORT.md。
```

**验收**：5 项中 4 项勾选，剩余 2 项标注「依赖 1.3/2.1 外部团队」

---

### Step 6：最终全量测试 + 清理

**目标**：确保所有测试通过，清理临时文件

**执行命令**：

```powershell
cd d:\Users\Yoga\Documents\GitHub\Zhifill\apps\api
$env:PYTHONPATH="packages\contracts\python;."
python -m pytest tests/ -v
```

**清理项**：
- 删除 `demo_msr_output.txt`（Demo 临时输出）
- 保留 `demo_msr.py`（可复用的 Demo 脚本）
- 确认 `__pycache__` 不被提交

**验收**：`tests/` 全部通过（含 contracts + fill_agent + upload_storage）

---

### Step 7：交付清单核验

**对照** [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) §八「9 天后的交付清单」：

| 交付物 | 状态 | 备注 |
|--------|------|------|
| FillService.fill() 实现 | ✅ | [service.py](./service.py) |
| 4 子模块 | ✅ | [agent/](./agent/) |
| pyproject.toml agent extra | ✅ | openai>=1.40,<2 |
| tests/test_fill_agent.py | ✅→35+ | Step 1 补全后 |
| README.md 更新 | ⏳ | Step 4 |
| SELECT_MODEL.md 待办更新 | ⏳ | Step 5 |
| 本地端到端 fixture 对齐 | ⏳ | Step 3 |
| 不回写图谱断言 | ✅ | test_fill_never_calls_rag_write_paths |

**验收**：全部 ✅

---

## 执行顺序与依赖关系

```
Step 1 (补边缘用例)
  └→ Step 2 (契约回归)
       └→ Step 3 (端到端 fixtures 联调)
            └→ Step 4 (README) + Step 5 (SELECT_MODEL)  [并行]
                 └→ Step 6 (全量测试 + 清理)
                      └→ Step 7 (交付清单核验)
```

Step 4 和 Step 5 可以并行执行（都是文档更新，无代码依赖）。

---

## 风险与对策

| 风险 | 对策 |
|------|------|
| `reasoning_content` mock 需要构造 openai SDK 响应对象 | 用 `unittest.mock.MagicMock` 构造 `choices[0].message.content` + `reasoning_content` |
| fixtures schema 校验依赖 `jsonschema` 包 | 已在 `dev` extra 中声明，`pytest.importorskip` 兜底 |
| Demo 输出中文编码问题 | 已在 demo_msr.py 中用 `sys.stdout = open(file, encoding="utf-8")` 解决 |
| 1.3 TaskSpec 契约未出 | SELECT_MODEL.md 保留未勾选项，标注「依赖外部团队」 |

---

## 完成标准

- [ ] `pytest tests/ -v` 全绿（含 contracts + fill_agent 35+ + upload_storage）
- [ ] `fill_result.schema.json` 校验通过
- [ ] README.md 包含 Pipeline + 创新点 + 红线 + parse() 声明
- [ ] SELECT_MODEL.md §8 待办 4/6 勾选
- [ ] 端到端 Demo（fixtures 驱动）输出 stats.filled=1
- [ ] 交付清单 8 项全部 ✅

（完）
