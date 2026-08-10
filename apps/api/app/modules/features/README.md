# 3.2 — 用户信息大模型特征提取（M2）

## 输入 / 输出

- **入**：`FeatureExtractRequest`（`doc_id` + 非空 `text`）
- **出**：`FeatureExtractResult`（键值特征、要点、可选 `enhanced_text`）

## 职责

- 调用可配置 LLM（OpenAI 兼容 / Ollama）做结构化抽取
- 无依据不编造；结果供 **3.4** 入库前增强（由编排层 3.6 调用）

## 不做

- LightRAG、文件格式解析、前端、表格写回

实现请改 `service.py`，保持 `port.py` 稳定；契约升格到 `packages/contracts` 时走统筹评审。
