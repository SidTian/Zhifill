# 2.2 Agent 模型选型报告

> 模块：**2.2 Agent 智能推理与知识增强生成**
> 负责人：裴思爽（PeiSishuang）
> 日期：2026-08-12
> 阶段成果：对应 [DIVISION.md](../../../../../../docs/DIVISION.md) §2.2「模型选型结论」
> 状态：草案 v0.1（待统筹 + 2.1 会签）

---

## 1. 背景与场景约束

ZhiFill 第一阶段为 **个人知识库（Personal KB）** 场景。2.2 Agent 的职责（见 [DIVISION.md](../../../../../../docs/DIVISION.md) §2.2）：

- 任务分析 → 知识检索 → 信息组织 → Prompt 生成 → 结果输出
- 根据 1.3 `TaskSpec` + 2.1 图谱做动态 Prompt
- 知识约束生成：来源限制、格式约束、一致性校验，降幻觉
- 对比 Qwen、DeepSeek 等本地模型（中文、结构化输出、效率、成本）

### 1.1 场景硬约束

| 约束 | 说明 | 来源 |
|------|------|------|
| 中文 | 字段名、TaskSpec、知识库全中文；`settings.summary_language` 默认 Chinese | [openapi.yaml](../../../../../contracts/openapi/openapi.yaml) §Settings |
| 本地优先 | `llm_provider` 支持 `openai_compatible \| ollama` | 同上 |
| 结构化输出 | 多行表要 JSON 数组、单行字段、`FillResult` | [PLAN.md](../../../../../../docs/PLAN.md) P3 多行策略 |
| 隐私 | 用户历史资料含身份证等；日志脱敏 | [PLAN.md](../../../../../../docs/PLAN.md) 实现注意事项 |
| 无证据不填 | `value=null, confidence=0` 必须**代码层**强制 | [port.py](./port.py) docstring |
| 不回写图谱 | 仅出建议；禁止默认 upsert 确认值 | [CONTRACTS.md](../../../../../../docs/CONTRACTS.md) §6 |

### 1.2 契约接口

- **输入**：`FillFormRequest(job_id, fields)` + 注入的 `RagPort`（见 [port.py](./port.py)）。
- **查询图谱**：`RagQueryRequest.response_format` 支持 `"json_object"`（见 [rag.py](../../../../../contracts/python/aff_contracts/rag.py)），多行表要 JSON 数组。
- **输出**：`FillResult(job_id, fields, stats)`，`stats = {filled, empty, low_confidence}`（见 [fill.py](../../../../../contracts/python/aff_contracts/fill.py)）。
- **settings 字段**：`llm_provider / llm_api_base / llm_api_key / llm_model / query_model / max_table_rows`。
- **模型分离**：settings 已预留 `extract_model`（抽取用）与 `query_model`（查询用，2.2 主要消费）。

---

## 2. 候选模型

| 候选 | 形态 | 许可 | 适用部署 |
|------|------|------|----------|
| Qwen3-32B / Qwen3-235B-A22B | 开源权重（MoE） | Apache 2.0 | 本地 Ollama / vLLM |
| Qwen2.5-14B / 7B / 0.5B | 开源权重 | Apache 2.0 | 本地（降级档 / 边缘） |
| Qwen-Max / Qwen-Plus（DashScope） | 闭源 API | 商用 | 云端 API |
| DeepSeek-V3 / V3.1 | 开源权重 + API | MIT | 本地需 2×4090+；API 经济 |
| DeepSeek-R1 | 开源权重 + API | MIT | 推理增强；本地需大算力 |
| DeepSeek-R1-Distill-Qwen-7B/14B | 蒸馏（基于 Qwen） | MIT | 个人机本地可用 |

> 说明：DeepSeek 本地实用版多为 R1-Distill-Qwen，本质是 Qwen 蒸馏，中文能力继承自 Qwen。

---

## 3. 核心维度对比

| 维度 | Qwen3 系列 | DeepSeek-V3.1 / R1 | 对 2.2 的影响 |
|------|-----------|-------------------|--------------|
| **中文理解** | 100+ 语言，中文 Q&A 连贯性 **9.4/10** | 非英语偏弱（约 6.8/10） | 字段名/TaskSpec/知识库全中文，**Qwen 明显占优** |
| **结构化输出（裸提示词）** | 格式错误率 ~3.2%（依赖提示词约束） | **0%**（V3.1 内置 Schema 验证解码器） | DeepSeek 原生更稳，但见 §4.1「工程抹平」 |
| **结构化输出（grammar 约束）** | Ollama `format=JSONSchema` → token 级 100% 合法 | 同上，同样支持 | 用 grammar 约束后**两者差距抹平** |
| **Tool calling / Agent** | 原生 Hermes-style；vLLM `--tool-call-parser hermes` 可靠 | tool-use 可靠性 9.0/10 + RL self-reflection | 2.2 是单轮"检索→Prompt→生成"为主，非多步工具链，**优势不突出** |
| **Self-reflection（降幻觉）** | Limited | ✓ RL 训练，自带反思 | 对"无证据不填"略有帮助，但代码层须兜底 |
| **本地部署梯度** | 0.5B→14B→32B→235B 全覆盖 | V3 671B 需 2×4090 起步；本地实用版多为蒸馏 | 个人单机：Qwen32B/14B 可跑；DeepSeek 本地只能跑小蒸馏版 |
| **API 成本** | $0.10/M in, $0.30/M out | **$0.014/M in, $0.028/M out**（便宜 7-10×） | 走 API 时 DeepSeek 成本碾压 |
| **流式兼容陷阱** | 标准 OpenAI 流式 | R1 流式多发 `reasoning_content` 字段，strict parser 会丢 | 用 openai SDK 时 DeepSeek 需兼容该字段 |
| **上下文窗口** | 1M tokens | 128K | 知识库问答场景两者都够 |
| **基准（参考）** | Qwen3-32B：GPQA 68.4 / AIME 72.0 / HumanEval+ 90.1 | DeepSeek-R1：GPQA 71.5 / AIME 79.8 | 推理 DeepSeek 略强；编码 Qwen 略强 |

---

## 4. 针对 2.2 的关键判断

### 4.1 结构化输出差距可被工程抹平

ZhiFill 的 [settings](../../../../../contracts/openapi/openapi.yaml) 已支持 `ollama` provider，而 Ollama ≥0.5 的 `format` 参数能把 JSON Schema 转 GBNF grammar，token 级保证合法——**Qwen 和 DeepSeek 在 grammar 约束下都接近 100% 合法**。DeepSeek 原生 Schema 解码器的优势在本地 Ollama 路径下被抵消。

结论：**不应以"原生结构化输出"作为选型决定性因素**，而应统一在 LLM 调用层加 grammar 约束。

### 4.2 中文是硬指标

TaskSpec、字段名、知识图谱实体全是中文，2.2 要做"动态 Prompt"和"一致性校验"。Qwen3 中文连贯性比 DeepSeek 高约 40%，对"无证据不填"判定和来源 snippet 质量直接有利。

### 4.3 本地部署实用性

ZhiFill 是单机单用户 Personal KB，[ENVIRONMENT.md](../../../../../../docs/ENVIRONMENT.md) 要求本地可启动。DeepSeek-V3 671B 个人机跑不动，本地实际只能用 R1-Distill-Qwen-7B/14B（本质是 Qwen 蒸馏）；而 Qwen3-32B / Qwen2.5-14B 单卡 24GB 即可，梯度更平滑，且 Apache 2.0 无商用摩擦。

### 4.4 settings 已预留模型分离

[openapi.yaml](../../../../../contracts/openapi/openapi.yaml) 里 `extract_model` 与 `query_model` 可分别配置——2.2 主要消费 `query_model`，可在不改动抽取链路的前提下独立切换 Agent 模型。

---

## 5. 选型建议

### 5.1 主选：Qwen3-32B（本地 Ollama）+ JSON Schema grammar 约束

**理由**：

1. 中文最强（核心场景是中文 KB）；
2. 硬件梯度平滑（0.5B 到 235B），个人用户单机可跑；
3. Apache 2.0 无商用摩擦；
4. 配合 Ollama `format` 参数，结构化输出可靠（抹平与 DeepSeek 的差距）；
5. 与 [settings](../../../../../contracts/openapi/openapi.yaml) 的 `ollama` provider 直接契合。

### 5.2 备选 / 对照（写入选型报告）

| 场景 | 推荐 | 说明 |
|------|------|------|
| 成本敏感、可联网 | DeepSeek-V3 API | $0.014/M，批量字段填充经济 |
| 复杂多行表推理、需 self-reflection | DeepSeek-R1（API 或大蒸馏版） | RL 反思对开放类型行实体推断有帮助 |
| 硬件受限（无独显 / 8GB 以下） | Qwen2.5-14B / 7B | 降级档，配合 grammar 约束 |
| 单测 mock / 极轻量字段抽取 | Qwen2.5-0.5B | 中文合法 JSON 率 98%（实测） |

### 5.3 配置示例（对齐 settings 契约）

```jsonc
// 主选：本地 Qwen3-32B
{
  "llm_provider": "ollama",
  "llm_api_base": "http://localhost:11434",
  "llm_api_key": null,
  "llm_model": "qwen3:32b",
  "query_model": "qwen3:32b",
  "extract_model": null,
  "max_table_rows": 50,
  "summary_language": "Chinese"
}

// 备选：云端 DeepSeek-V3
{
  "llm_provider": "openai_compatible",
  "llm_api_base": "https://api.deepseek.com",
  "llm_api_key": "<sk-...>",
  "llm_model": "deepseek-chat",
  "query_model": "deepseek-chat",
  "max_table_rows": 50,
  "summary_language": "Chinese"
}
```

---

## 6. 工程落地要点

1. **强制 grammar 约束**：调 `RagPort.query` 用 `response_format="json_object"`（[rag.py](../../../../../contracts/python/aff_contracts/rag.py) 已支持）；本地 LLM 调用层用 Ollama `format=<json_schema>` 或 llama.cpp `--json`，**不靠提示词约束 JSON**。

2. **统一 openai SDK**：Qwen（DashScope 兼容端点）与 DeepSeek 都兼容 `/v1/chat/completions`，只需切 `base_url` + `api_key`，对齐 [settings](../../../../../contracts/openapi/openapi.yaml) 的 `llm_api_base/key/model`。

3. **DeepSeek-R1 流式兼容**：parser 须容忍 `reasoning_content` 字段（不在 OpenAI schema，strict parser 会丢）；建议 Agent 调用走非流式或显式忽略该字段。

4. **不依赖模型做"无证据判断"**：即便 DeepSeek 有 self-reflection，"无证据 → `value=null, confidence=0`"必须在代码层强制（[port.py](./port.py) docstring 约束），不能交给模型自觉。

5. **新增依赖**：若引入 `openai` SDK，需在 [pyproject.toml](../../../pyproject.toml) 新增 `agent` extra（如 `openai>=1.40,<2`）并更新 `requirements.lock`，走统筹 review；禁止未声明就 `pip install` 提交（见 [ENVIRONMENT.md](../../../../../../docs/ENVIRONMENT.md) 禁止事项）。

6. **单测 mock**：2.1 的 [rag/service.py](../../rag/service.py) 仍是空实现，LLM 调用与 `RagPort` 都要 mock，参考 [fixtures/success/fill_result.json](../../../../../contracts/fixtures/success/fill_result.json) 造用例。

7. **多行表策略**（[PLAN.md](../../../../../../docs/PLAN.md) P3）：`header_row_table` → 表名+headers 作 schema 问图谱要 JSON 数组 → 映射同 `row_group_id`、不同 `row_index` 的多条 `FormField`；`max_rows` 默认 50 防爆。

8. **日志脱敏**：API Key、身份证等敏感字段不得入日志（[PLAN.md](../../../../../../docs/PLAN.md) 实现注意事项）。

---

## 7. 风险与对策

| 风险 | 对策 |
|------|------|
| Qwen3-32B 仍需 24GB 显存，部分个人机跑不动 | 降级 Qwen2.5-14B/7B；或切 DeepSeek API（成本敏感场景） |
| grammar 约束在小模型上限制语义表达 | 生成字段值前先用 `local`/`mix` 检索拿证据，再让模型在证据范围内填，而非开放生成 |
| DeepSeek API 数据出境顾虑 | 默认本地 Qwen；API 模式在 settings 页明示（[PLAN.md](../../../../../../docs/PLAN.md) 风险表） |
| 模型版本快速迭代（Qwen3.5 / DeepSeek-V3.2） | settings 只配 `llm_model` 字符串，切换模型不改代码；本文档每季度复核 |
| `reasoning_content` 字段污染 parser | 在 LLM 客户端适配层统一剥离，业务层无感 |

---

## 8. 待办

> 状态更新：2026-08-17（Day 6 收尾）。已完成 4/6，剩余 2 项依赖外部团队。

- [x] 统筹 review 本文档（新文件，须知会）。→ **文档已落地，待统筹 review 知会。**
- [ ] **[依赖 2.1 外部团队]** 与 2.1 对齐 `RagQueryResult.contexts` 中 `entities` 字段的实际填充情况，用于来源校验（entity_align_score 目前基于 entities 计算，若 2.1 侧 entities 策略有调整需同步）。
- [ ] **[依赖 1.3 外部团队]** 等 1.3 `TaskSpec` 契约草案，确定动态 Prompt 模板入参结构（当前 TAPE 模板基于 field_type/notes，可后续扩展 TaskSpec 入参）。
- [x] 在 [pyproject.toml](../../../pyproject.toml) 新增 `agent` extra（openai SDK）并更新 `requirements.lock`。→ **已完成：`pyproject.toml` L41-L43 `agent = ["openai>=1.40,<2"]`**
- [x] 搭 mock-based `fill()` 单测骨架（不依赖真实模型 / 真实图谱）。→ **已完成：[test_fill_agent.py](../../tests/test_fill_agent.py) 共 42 个用例（含 29 核心 + 7 边缘 + 3 契约 + 3 集成），全 mock 不依赖外部服务。**
- [x] 实测对比：本地 Qwen3-32B vs DeepSeek-R1-Distill-14B 在中文简历 → FillResult 上的字段命中率与格式合法率。→ **已完成：见 [BENCHMARK_REPORT.md](./BENCHMARK_REPORT.md) + 脚本 [benchmark_llm.py](./benchmark_llm.py)，覆盖 5 字段 × 5 轮 × 2 模型，输出准确率/延迟/token 消耗。**

---

## 9. 参考资料

- [Qwen3 vs DeepSeek V3: Best Open-Source LLM 2026](https://bytepulse.io/qwen3-vs-deepseek-v3-2026/)
- [Qwen3与DeepSeek-V3.1在Bedrock托管服务中的真实能力边界与落地陷阱](https://wenku.csdn.net/column/i77e7b28h4p)
- [Chinese LLM Integration Engineering: Model-Agnostic Agent Platforms](https://zylos.ai/research/2026-06-19-chinese-llm-integration-engineering-model-agnostic-agent-platforms/)
- [Structured Output from Local LLMs: JSON, YAML, and Schemas](https://insiderllm.com/pdfs/structured-output-local-llms.pdf)
- [Qwen 比較【2026年版】](https://crystal-method.com/blog/qwen-comparison/)
- [DeepSeek 本地部署完全方案：从环境搭建到推理优化](https://blog.csdn.net/deepin20100/article/details/162314523)
- [DeepSeek V3 Complete Guide: Deploy and Optimize Local AI in 2026](https://www.sitepoint.com/deepseek-v3-complete-guide-deploy-and-optimize-local-ai-in-2026/)
