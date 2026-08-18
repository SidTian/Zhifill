# 2.2 Agent 交付核验报告

> **报告日期**：2026-08-17
> **负责人**：裴思爽（PeiSishuang）
> **模块**：`apps/api/app/modules/fill/`
> **全量测试**：53 passed（contracts 6 + fill_agent 42 + upload_storage 5）
> **红线核验**：6 条全部通过
> **综合结论**：✅ **Day 1-7 全部完成，可交付**

---

## 一、验收 Checklist（IMPLEMENTATION_PLAN.md §1.2）

基准：§1.2 验收 checklist 共 5 项

| # | 验收项 | 结果 | 核验证据 |
|---|--------|------|----------|
| 1 | 单行 `label_value`：有证据→suggested+sources；无证据→empty | ✅ | `test_fill_has_evidence_is_suggested_with_sources` + `test_fill_no_evidence_returns_empty` |
| 2 | 多行 `header_row_table`：按 row_group_id 批量，row_index 连续，max_table_rows 保护 | ✅ | `test_fill_multi_row_msr_end_to_end_two_rows`（2 行×3 列批量）+ `test_fill_multi_row_max_table_rows_enforced_via_settings`（max=1 截断） |
| 3 | `confidence ∈ [0,1]`，`low_confidence < 0.45` 标黄 | ✅ | `test_fill_confidence_low_threshold_marks_yellow`（conf=0.41→标黄，low_confidence++）+ `test_fill_locator_readonly_and_boundary_properties`（全字段 conf ∈ [0,1]） |
| 4 | 单测：mock RagPort 即可跑通，不依赖真实模型/图谱 | ✅ | 42 个 fill_agent 用例全部使用 `MockRag` + `FakeLLMClient`，`pytest tests/test_fill_agent.py` 无外部网络/服务依赖 |
| 5 | 与 `fill_result.json` schema 一致 | ✅ | `test_fill_result_passes_jsonschema_validation`（Draft202012 JSONSchema 校验通过）+ `test_fill_end_to_end_with_contract_fixtures`（fixtures 驱动端到端对齐） |

**验收 Checklist 结论**：5/5 ✅ 全部通过。

---

## 二、交付清单核验（IMPLEMENTATION_PLAN.md §八）

基准：§八「9 天后的交付清单」共 8 项

| # | 交付项 | 计划要求 | 结果 | 核验证据 |
|---|--------|---------|------|----------|
| 1 | `FillService.fill()` 实现 | service.py | ✅ | [service.py fill()](./service.py#L59-L280)：grouper→layout 分流→PostProc 完整串联，统一走 `_apply_value_to_field` 做阈值/stats/sources |
| 2 | 4 个子模块：grouper / planner / runner / PostProc | 4 文件 | ✅ | [agent/grouper.py](./agent/grouper.py)（分组+headers）· [agent/planner.py](./agent/planner.py)（双检索+CSF+MSR预问）· [agent/runner.py](./agent/runner.py)（TAPE+grammar+validate_type+MSR批量）· PostProc 内嵌 service.py（阈值判定+sources去重+stats） |
| 3 | pyproject.toml 新增 `agent` extra + requirements.lock | agent extra | ✅ | [pyproject.toml L41-L43](../../../pyproject.toml#L41-L43)：`agent = ["openai>=1.40,<2"]` |
| 4 | `tests/test_fill_agent.py`（计划 8 用例，pytest 全绿） | **8 → 42 个**，超额 5× | ✅ | [test_fill_agent.py 42 passed](../../tests/test_fill_agent.py)：29 Day1-5 核心 + 7 Step1 边缘 + 3 Step2 契约 + 3 Step3 集成，全部全绿 |
| 5 | README.md 更新：Pipeline 与创新点 + parse() 声明 | 19→189 行 | ✅ | [README.md](./README.md)：8 章节（I/O / 4 组件架构图 / 4 创新点详解 / layout 分流 / 6 红线 / parse() 声明 / 目录结构 / 规则） |
| 6 | SELECT_MODEL.md §待办更新 | 6 项 | ✅ | [SELECT_MODEL.md §8](./SELECT_MODEL.md#L177-L186)：4/6 完成勾选，2 项标注「依赖 1.3/2.1 外部团队」，附完成证据链接 |
| 7 | 本地端到端：fake RagPort + 契约 fixtures 对齐 schema | fixtures 驱动 | ✅ | `test_fill_end_to_end_with_contract_fixtures`（form_field.json→RagPort→fill()→fill_result.json 结构对齐）+ [demo_msr.py](./demo_msr.py)（姓名+工作经历 2 行+证书，本地可跑） |
| 8 | 不回写图谱断言：rag.upsert/delete 未被调用 | 红线 | ✅ | `test_fill_never_calls_rag_write_paths`：MockRag 的 upsert/delete 被调用直接抛 AssertionError，fill() 全程只调 query |

**交付清单结论**：8/8 ✅ 全部完成，且 3 项（用例数 / README 体量 / 端到端覆盖）超计划完成。

---

## 三、4 大创新点落地核验

| # | 创新点 | 实现位置 | 验证测试 | 状态 |
|---|--------|---------|----------|------|
| 1 | **Dual-Retrieval + 实体对齐打分**（粗检索+细检索+Jaccard align<0.50→retry） | [planner.py entity_align_score + build_retry_query](./agent/planner.py#L51-L139) + [service.py _fill_single_fields retry 循环](./service.py#L102-L126) | `test_fill_retry_triggered_when_align_low` · `test_fill_retry_actually_improves_and_adopts_retry_result` · `test_fill_retry_exhausted_falls_back` | ✅ |
| 2 | **Type-Aware Prompt Engine (TAPE)**（5 模板+grammar双通道+validate_type 7 类型） | [runner.py build_prompt + LLMClient.complete + validate_type](./agent/runner.py#L62-L253) | `test_build_prompt_injects_field_type_templates` · `test_llm_complete_schema_openai_compatible` · `test_validate_type_boundary_cases` · `test_validate_type_single_choice_with_options` · `test_fill_deepseek_reasoning_content_stripped` | ✅ |
| 3 | **MSR 多行语义路由**（4 步合批替代 N×M 次调用+max_table_rows 双保险） | [planner.py pre_determine_entity_type](./agent/planner.py#L142-L183) + [runner.py generate_multi_row](./agent/runner.py#L267-L350) + [service.py _fill_header_row_table](./service.py#L146-L250) | `test_fill_multi_row_msr_end_to_end_two_rows` · `test_fill_multi_row_max_table_rows_enforced_via_settings` · `test_fill_multi_row_entity_type_fallback_still_works` · `test_fill_multi_row_generated_exceeds_existing_rows` · `test_fill_multi_row_generated_fewer_than_existing_rows` | ✅ |
| 4 | **CSF 三因子置信度合成**（0.40·retrieval + 0.30·align + 0.30·tv，三段式阈值） | [planner.py calc_confidence](./agent/planner.py#L76-L101) + [service.py _apply_value_to_field](./service.py#L64-L92) | `test_fill_confidence_low_threshold_marks_yellow`（[0.30,0.45)→标黄）· `test_fill_confidence_empty_threshold_forces_null`（<0.30→置空）· `test_fill_confidence_precision`（round 3 位）· `test_fill_retrieval_score_none_treated_as_zero` | ✅ |

---

## 四、6 条红线核验

| # | 红线 | 实现方式 | 验证测试 | 状态 |
|---|------|---------|----------|------|
| 1 | **无证据 → value=None, confidence=0**（禁止瞎填） | CSF conf<0.30 强制 EMPTY；`_apply_value_to_field` L70-L73 | `test_fill_no_evidence_returns_empty` · `test_fill_confidence_empty_threshold_forces_null` · `test_fill_retrieval_score_none_treated_as_zero` | ✅ |
| 2 | **不回写知识图谱**（只读 RagPort.query） | MockRag 调 upsert/delete 直接抛 AssertionError；service.py 未调用写路径 | `test_fill_never_calls_rag_write_paths` | ✅ |
| 3 | **`settings.max_table_rows` 必须 enforce** | Prompt 提示 + generate_multi_row 返回后切片双重保险 | `test_fill_multi_row_max_table_rows_enforced_via_settings`（max=1 强制截断）· `test_generate_multi_row_parse_and_truncate` | ✅ |
| 4 | **`locator` 只读不改**（输入 == 输出） | service.py 全程不修改 f.locator | `test_fill_locator_readonly_and_boundary_properties`（3 字段×布局，orig == out 深拷贝对比）| ✅ |
| 5 | **不扩表**（MSR 生成行 > 已分配行 → 丢弃） | `_fill_header_row_table` L237 `if row_idx > max_existing_row: break` | `test_fill_multi_row_generated_exceeds_existing_rows`（生成 5 行 / 已有 2 行 → 只保留 row0-1） | ✅ |
| 6 | **只依赖 RagPort + contracts packages**（不 import 2.1 内部） | `agent/` + `service.py` imports 仅 `aff_contracts.*` 与 typing/logging/json；未 import 其他内部模块 | 静态 import 检查（见 §六） | ✅ |

---

## 五、里程碑与日进展

| Day | 主题 | 新增测试 | 核心交付 |
|-----|------|---------|---------|
| **Day 1** | 骨架与契约落地（4 组件 + fill 串联） | 1 | [agent/](./agent/) 4 文件 + [service.py](./service.py) fill() 骨架 |
| **Day 2** | FieldGrouper + QueryPlanner + CSF 打分 + **重试机制（加分项）** | +7→8 | grouper 分组 + Dual-Retrieval 双检索 + CSF 三因子 + retry 自动重检索 |
| **Day 3** | LLM Runner + TAPE 模板 + grammar 约束 + **模型基准（加分项）** | +6→14 | LLMClient 双通道 + 5 模板 + validate_type 7 类型 + [BENCHMARK_REPORT.md](./BENCHMARK_REPORT.md) |
| **Day 4** | PostProc 串联 + stats + 红线 enforcement + **debug 日志/去重/精度（加分项）** | +4→18 | _apply_value_to_field 统一逻辑 + CSF 三段式判定 + sources 去重 + debug 三维打分日志 |
| **Day 5** | MSR 多行语义路由（4 步合批） + layout 分流 | +11→29 | pre_determine_entity_type + build_multi_row_query + generate_multi_row + MSR 回写 + max_table_rows 双保险 |
| **Day 6 Step 1** | 覆盖率冲刺：7 个边缘用例 | +7→36 | reasoning_content 过滤 / 阈值两段式 / 空 contexts / retry 耗尽 / 行超限 / 选项校验 |
| **Day 6 Step 2** | 契约回归：JSON Schema + fixtures 端到端 + 红线属性 | +3→39 | fill_result.schema.json Draft202012 校验 / fixtures 端到端 / locator 只读 & 边界 |
| **Day 6 Step 3** | 端到端集成：混合场景 + retry 实际改善 + 行数不足降级 | +3→42 | 1 单字段+6 多行表全填 / retry 后 sources 来自 retry_ctx / LLM 行数少于分配行的 EMPTY 兜底 |
| **Day 6 Step 4** | README.md 扩充（19→189 行，8 章节） | - | 架构图 + 4 创新点 + layout 分流 + 6 红线 + parse() 声明 + 目录树 |
| **Day 6 Step 5** | SELECT_MODEL.md §8 待办勾选 | - | 4/6 完成，2 项明确标注「依赖外部团队」+ 完成证据链接 |
| **Day 6 Step 6** | 全量 tests/ 53 passed + 临时文件清理 | - | 6 contracts + 42 fill_agent + 5 upload_storage 全绿；删除 demo_msr_output.txt |
| **Day 7** | 交付清单核验（本报告） | - | 5 验收 + 8 交付 + 4 创新点 + 6 红线 全部 ✅ |

---

## 六、代码静态质量核查（补充）

### import 边界检查（红线 #6）

对 `fill/` 下核心 Python 源文件 grep `^import` / `^from`：

| 文件 | import 范围 | 合规 |
|------|------------|------|
| [service.py](./service.py) | `from __future__` · `typing` · `logging` · `collections.defaultdict` · `aff_contracts.*` · `app.modules.fill.agent.*` | ✅ |
| [agent/grouper.py](./agent/grouper.py) | `from __future__` · `typing` · `dataclasses` · `aff_contracts.*` | ✅ |
| [agent/planner.py](./agent/planner.py) | `from __future__` · `typing` · `aff_contracts.*` | ✅ |
| [agent/runner.py](./agent/runner.py) | `from __future__` · `typing` · `json` · `re` · `datetime` · `aff_contracts.*`（`openai` 仅在 LLMClient 构造函数内延迟 import） | ✅ |
| [agent/__init__.py](./agent/__init__.py) | 仅相对 re-export 本目录 3 个子模块 | ✅ |

**结论**：无 2.1 内部模块 import，`openai` SDK 延迟 import，契约边界合规。

### Pydantic 类型安全

所有外部 I/O（FillFormRequest / FillResult / FormField / RagContext / RagQueryResult / Settings）均走 `aff_contracts` Pydantic v2 模型，静态不构造未校验 dict 直接传递。

---

## 七、遗留项与后续工作

### ⏳ 阻塞项（依赖外部团队，非本模块可控）

| # | 项 | 依赖 | 影响 |
|---|----|------|------|
| 1 | `RagQueryResult.contexts[].entities` 实际填充情况对齐 | 2.1 图谱模块 | 仅影响 entity_align_score 打分精度；当前实现兼容 entities=[] 空列表（降级为 align=0，仍可正常填，只是需更多检索命中） |
| 2 | `TaskSpec` 契约草案（1.3） | 1.3 Task/Workflow 模块 | 仅影响 TAPE 模板是否能接 TaskSpec 动态入参；当前基于 field_type/notes 的模板已可用，后续可在不破坏现有接口前提下扩展 |

### 💡 可选优化（不阻塞交付）

- [x] 引入 `referencing` 库替代 `jsonschema.RefResolver`（当前 `RefResolver` 虽 deprecated 但可用，jsonschema>=4.0 全版本兼容）→ **已完成（2026-08-18）：优先用 `referencing.Registry`，旧版 jsonschema 自动降级到 `RefResolver`，兼容双版本**
- [ ] 新增 1.3 TaskSpec 入参后，扩展 `build_prompt(field, task_spec=None)` 签名
- [ ] 若 2.1 entities 策略明确，可调整 `entity_align_score` 权重（目前 0.30，与 retrieval/type_validity 等权）
- [x] requirements.lock 提交（待统筹 review 确认 `pyproject.toml agent extra` 后一并更新）→ **已完成（2026-08-18）：requirements.lock 新增 openai==1.109.1 及 5 个传递依赖（distro/jiter/sniffio/tqdm）**
- [x] Prompt 缓存：同 schema + 同 headers 的 `multi_row_tmpl` Prompt 做 LRU 缓存 → **已完成（2026-08-18）：`build_multi_row_schema` 加 `@lru_cache(maxsize=64)`，避免重复构造 dict**
- [x] 并行优化：同一字段组内的多个细检索用 `ThreadPoolExecutor` 并发 → **已完成（2026-08-18）：`service.py fill()` 中 `fine_queries` 多字段时走线程池（max_workers=4），单字段保持串行避免开销**
- [x] BENCHMARK 统计 Bug 修复 → **已完成（2026-08-18）：`benchmark_llm.py` 统计层修复（报错调用不再被 `if not c.error` 过滤为幽灵 0 值），`BENCHMARK_REPORT.md` 勘误标注**

---

## 八、最终交付结论

```
交付物核验：        8 / 8  ✅
验收 Checklist：    5 / 5  ✅
4 大创新点落地：    4 / 4  ✅
6 条红线合规：      6 / 6  ✅
全量测试通过：     53 / 53 ✅（仅 1 条 httpx 版本 deprecation warning，不影响功能）
```

**综合结论**：✅ **Day 1-7 全部交付完成，满足验收标准，可进入统筹 review 与 PR 提交流程。**

---

（报告完）
