# 填表模块（3.3 parsers + 3.5 Agent）

本目录由两人协作，**目录内再拆分**：

| 小节 | 范围 |
|------|------|
| **3.3** | 仅 `parsers/`：xlsx/docx/pdf → `FormField[]` + locator |
| **3.5** | `service.py` 填写策略：问图谱 → `FillResult`（**不含** parsers） |

## I/O

- **Parse（3.3）**: 空白表 → `ParseFormResult`
- **Fill（3.5）**: fields + `RagPort` → `FillResult`

## 规则

- 不回写知识图谱
- 无证据不填
- 可导出字段必须带 `locator`
