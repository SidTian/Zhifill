# 填表模块（3.3 parsers + 3.5 Agent）

本目录由两人协作，**目录内再拆分**：

| 小节 | 范围 |
|------|------|
| **3.3** | 仅 `parsers/`：xlsx/docx/pdf → `FormField[]` + locator |
| **3.5** | `service.py` 填写策略：问图谱 → `FillResult`（**不含** parsers） |

---

## I/O

- **Parse（3.3）**: 空白表 → `ParseFormResult`
- **Fill（3.5）**: `FillFormRequest`（fields[] + job_id）+ `RagPort` → `FillResult`（fields[] 回填值 + stats）

---

## Fill Pipeline 架构（4 组件流水线）

```
FillService.fill()
     │
     ▼
┌──────────────┐   label_value        ┌────────────────────────────────────────────┐
│ FieldGrouper │─────────────────────▶│ 逐字段 Dual-Retrieval + CSF 打分 + Retry   │
│  (按 layout  │                       │  QueryPlanner → Runner → PostProc         │
│   /row_group │                       └────────────────────────────────────────────┘
│    分组)     │
│              │   header_row_table   ┌────────────────────────────────────────────┐
└──────┬───────┘─────────────────────▶│  MSR 4 步合批（替代 N×M 次检索+LLM 调用） │
       │                              │  Step1: pre_determine_entity_type         │
       ▼                              │  Step2: build_multi_row_query → 定向检索    │
  分 组 结 果                          │  Step3: generate_multi_row → 批量 JSON 数组 │
                                      │  Step4: 按 row_index / column_key 回写    │
                                      └────────────────────────────────────────────┘
```

### 组件清单

| 组件 | 文件 | 职责 |
|------|------|------|
| **FieldGrouper** | [agent/grouper.py](./agent/grouper.py) | 按 `layout` + `row_group_id` 分组；header_row_table 自动提取 `headers` |
| **QueryPlanner** | [agent/planner.py](./agent/planner.py) | Dual-Retrieval 粗/细查询、CSF 三因子打分、retry 查询、MSR 预问分类、MSR 定向查询 |
| **Runner (LLMClient)** | [agent/runner.py](./agent/runner.py) | 5 套类型感知 Prompt（TAPE）、grammar 约束（Ollama / OpenAI JSONSchema）、`validate_type()` 7 种类型校验、MSR 批量 JSON 解析与截断 |
| **PostProc（内嵌 FillService）** | [service.py](./service.py) | CSF 阈值判定、sources 去重、stats 统计、红线 enforcement |

---

## 4 大创新点

### 1. Dual-Retrieval + 实体对齐打分（Day 2）

每个 label_value 字段执行 **2 次图谱检索**：
- **粗检索**（`mode="mix"`）：`本人知识库中关于 {name} 的事实。`
- **细检索**（`mode="local"`）：`本人的【{name}】（类型 {field_type}）具体取值与来源是什么？`

**实体对齐打分**：`Jaccard({field_name 字符} ∩ top.context.entities) / ∪`，align < 0.50 时**自动触发重试**（精确查询重检索，最多 1 次）。

### 2. Type-Aware Prompt Engine (TAPE) 类型感知模板（Day 3）

5 套中文 Prompt 模板，按 `field_type` 精确引导 LLM：

| field_type | 模板要点 |
|------------|---------|
| `text` | 中文短语 ≤ 50 字，不输出解释 |
| `date` | 格式 YYYY-MM-DD，未知未知字段输出空串 |
| `number` | 纯数字字符串，无单位、无逗号，不合法输出空串 |
| `single_choice` | 只从 notes 中 `选项：A\|B\|C` 输出一个，不在选项中则空串 |
| `multi` | 输出 JSON 数组，格式 `["A", "B"]` |

**Grammar 约束双通道**：
- Ollama：`format=json_schema`（含 `StrictFieldValue` JSONSchema）
- DeepSeek / OpenAI：`response_format={"type": "json_schema", "schema": ...}`

### 3. Multi-Row Semantic Router (MSR) 多行语义路由（Day 5）

**问题**：每行每列单独填 = N×M 次检索 + N×M 次 LLM，延迟爆炸且上下文丢失。

**解决方案（4 步合批）**：

```
Step 1: pre_determine_entity_type(group, llm)
  → LLM 分类助手，把 (headers, group_name) 映射到 6 类实体枚举：
     工作经历 / 教育经历 / 项目经历 / 证书 / 获奖 / 其他
  → 返回 (entity_type, query_hint)；LLM 异常自动 fallback

Step 2: build_multi_row_query(entity_type, hint, headers)
  → 一次定向 RagQuery：mode="mix", response_format="json_object"
     例："请检索本人 工作经历（工作经历、任职记录）。表格字段：公司,时间,职位"

Step 3: generate_multi_row(llm, headers, contexts, settings)
  → 一次 LLM 调用 + JSONSchema 约束（array of object），批量返回 JSON 数组
  → settings.max_table_rows 双重保险截断（prompt 提示 + 返回后切片）

Step 4: 回写
  → 按 (row_index, column_key) 查找已有 FormField 写入
  → LLM 生成行数 > 已分配字段行数 → 多余行直接丢弃（不扩表）
  → LLM 生成行数 < 已分配字段行数 → 剩余字段走 EMPTY 兜底
```

**效果**：3 列 × 5 行表 = 原来 15 次 LLM → 现在 2 次（分类 + 批量），省 87%。

### 4. Confidence Synthesis Formula (CSF) 三因子置信度合成（Day 2）

```
confidence = 0.40 * retrieval_score
           + 0.30 * entity_align_score
           + 0.30 * type_validity
```

| 因子 | 取值范围 | 含义 |
|------|---------|------|
| retrieval_score | [0, 1] | contexts[0].score（无 contexts 记 0） |
| entity_align_score | [0, 1] | Jaccard({字段名} ∩ context.entities) |
| type_validity | [0, 1] | `validate_type()` 对 LLM 返回值的合法度分 |

**阈值三段式判定**：

| 区间 | 判定 | value | confidence | status |
|------|------|-------|-----------|--------|
| conf < 0.30 | EMPTY 强制置空 | `None` | 0.0 | `empty` |
| 0.30 ≤ conf < 0.45 | LOW_CONFIDENCE 标黄 | 原值（建议人工复核） | 原值 | `suggested` + `stats.low_confidence++` |
| conf ≥ 0.45 | SUGGESTED 正常建议 | 原值 | 原值（round 到 3 位） | `suggested` + `stats.filled++` |

---

## layout 分流策略

`FillService.fill()` 在 [service.py#L262-L275](./service.py#L262-L275) 按 `group.layout` 分流：

| LayoutKind | 路径 | 说明 |
|------------|------|------|
| `label_value` | `_fill_single_fields()` | Day 2-4 原逻辑：粗检索 + 逐字段细检索 + CSF 打分 + align<0.50 retry |
| `header_row_table` | `_fill_header_row_table()` | Day 5 MSR 4 步：预问 → 定向检索 → 批量生成 → 回写 |

两种 layout 可在**同一 `FillFormRequest`** 中混合出现，独立分组互不干扰（见 [test_fill_agent.py#L1382](../../tests/test_fill_agent.py#L1382) 混合场景集成测试）。

---

## 红线（必须遵守）

| # | 红线 | 验证 |
|---|------|------|
| 1 | **无证据 → `value=None, confidence=0`**，禁止瞎填 | `test_fill_no_evidence_returns_empty` + `test_fill_confidence_empty_threshold_forces_null` |
| 2 | **不回写知识图谱**（只读 RagPort.query，不调 upsert/delete） | `test_fill_never_calls_rag_write_paths`（MockRag 调写路径直接 AssertionError） |
| 3 | **`settings.max_table_rows` 必须 enforce** | Prompt 提示 + 返回后切片双重保险；`test_fill_multi_row_max_table_rows_enforced_via_settings` |
| 4 | **`locator` 只读不改**（输入 locator == 输出 locator） | `test_fill_locator_readonly_and_boundary_properties` |
| 5 | **不扩表**：MSR 生成行 > FormField 已分配行数 → 直接丢弃 | `test_fill_multi_row_generated_exceeds_existing_rows` |
| 6 | **只依赖 RagPort 与 contracts packages**，禁止 import 2.1 内部模块 | import 检查（`agent/` 与 `service.py` 只 import `aff_contracts.*`） |

---

## parse() 不实现声明

本模块（3.5 Agent / fill strategy）**只实现 `FillService.fill()`**。

- `FillService.parse()` 由 **3.3 parsers 模块**（1.2 + 1.3）负责，`FillService.parse()` 当前在 `FillService` 中抛出 `NotImplementedModule`，本模块不触碰 parsers/xlsx/docx/pdf 解析逻辑。
- 两模块通过 `FormField[]` + `locator` 契约衔接：3.3 负责产出带 locator 的空白 FormField 列表，3.5 负责回填值 + confidence + sources。

---

## 目录结构

```
fill/
├── README.md                        # 本文档
├── IMPLEMENTATION_PLAN.md           # Day 1-7 原始 9 天计划
├── DAY6_7_PLAN.md                   # Day 6-7 合并执行计划（正在执行）
├── SELECT_MODEL.md                  # 模型选型文档（含 LLM 模板 & 约束）
├── BENCHMARK_REPORT.md              # Day 3 模型基准对比报告 (Qwen vs DeepSeek)
├── benchmark_llm.py                 # 基准测试脚本 (5 字段 × 3 轮 × 2 模型)
├── demo_msr.py                      # Day 5 MSR 本地 Demo (姓名+工作经历+证书)
├── service.py                       # FillService: fill() 串联 4 组件
└── agent/                           # agent/ 子模块（Day 1 拆分）
    ├── __init__.py                  # 导出 FieldGrouper / QueryPlanner / Runner
    ├── grouper.py                   # FieldGrouper: 分组
    ├── planner.py                   # QueryPlanner: 双检索+CSF+MSR 预问
    └── runner.py                    # Runner: LLMClient + TAPE 模板 + validate_type + MSR 批量
```

---

## 规则

- 不回写知识图谱
- 无证据不填
- 可导出字段必须带 `locator`
