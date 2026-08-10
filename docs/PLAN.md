# 智填 ZhiFill — 协作规划与契约优先架构

## 目标

第一阶段完成 **个人用户知识库（Personal KB）** 基础搭建与技术路线验证：

1. 历史资料 → **1.1 统一表示** → **2.1 Schema 抽取 + 知识图谱**（新文件须增量更新节点/关系）
2. 当前任务文件 → **1.2 结构** → **1.3 语义/TaskSpec** → **2.2 Agent** 填报建议
3. **统筹**：前端预览确认 → **自动回填** 下载；填写结果 **不回写** 知识库

企业知识库为后续扩展。分工主文档：**[docs/DIVISION.md](./DIVISION.md)**。

## 已确认决策

| 项 | 选择 |
|---|---|
| 场景 | 个人用户（Personal KB）；本地 Web；单机单用户无登录 |
| 人数 | **6 人**：统筹（SidTian）+ 1.1 / 1.2 / 1.3 / 2.1 / 2.2 |
| SidTian 职责 | **统筹规划 + 前端 + 数据回填 + 系统集成** |
| Schema | 由 **2.1** 设计，全系统对齐 |
| 任务文件优先级 | **先 Word**，再 PDF、Excel（1.2） |
| 知识来源 | 用户上传多源历史资料（1.1 统一） |
| 交付 | 预览确认后下载；**填写结果不回写知识库** |
| 图谱 | 2.1 构建（推荐 LightRAG 或等价方案） |
| 模型 | 本地/API 可切换；**2.2** 负责 Qwen/DeepSeek 等选型对比 |
| 协作 | GitHub；契约优先；计划进仓库 |

## 本期不做

- 企业知识库 / 多租户 SaaS
- 外部云盘同步
- 填写结果自动回写图谱
- 平面 PDF 像素级完美贴字（可降级）
- 图谱大屏可视化（可选后续）

---

## 协作模型（6 人）

详见 **[DIVISION.md](./DIVISION.md)**、**[OWNERS.md](./OWNERS.md)**。

| 编号 | 职责 | 目录 |
|---|---|---|
| **统筹（SidTian）** | 规划/契约/前端/回填/集成部署 | `docs/`、`apps/web/`、`export/`、编排、Compose |
| **1.1** | 历史资料统一表示 | `modules/ingest/` |
| **1.2** | 任务文档结构解析 | `modules/form_structure/` |
| **1.3** | 语义理解与任务需求 | `modules/task_semantics/` |
| **2.1** | Schema + 抽取 + 图谱 | `modules/rag/` |
| **2.2** | Agent 推理与生成 | `modules/fill/` |

```
历史资料 ──► 1.1 ──► 2.1 图谱 ──┐
                                ├──► 2.2 Agent ──► 统筹前端预览 ──► 统筹回填下载
当前任务 ──► 1.2 ──► 1.3 TaskSpec ─┘
```

---

## 仓库可见规划（GitHub）

实现骨架阶段必须在**仓库内**提交（不仅在本地 kilo plans）：

```
docs/
    DIVISION.md             # 第一阶段架构与 6 人分工（人员主文档）
    PLAN.md                 # 产品决策与分阶段计划
    ARCHITECTURE.md         # 模块边界、数据流、图谱更新语义
    CONTRACTS.md            # 契约索引与版本规则
    OWNERS.md               # 1.1–2.2 与统筹目录归属
    ACCEPTANCE.md           # 验收清单
    ENVIRONMENT.md          # 运行环境约束
packages/contracts/       # 跨语言/跨人共享的 schema（见下）
```


约定：

- **契约变更**：改 `packages/contracts` 必须 bump 版本字段 + 在 PR 说明破坏性；禁止静默改字段含义。
- **实现 PR**：只碰自己拥有的 `modules/*`；跨模块只依赖 contracts + 对方 public port。
- **空实现**：各模块提供未实现占位（`NotImplementedError`）/ HTTP 501 / 前端占位页，保证仓库可克隆、可启动骨架。

---

## 空目录骨架（阶段 0 唯一实现范围）

```
auto-form-fill/
  README.md
  docs/
    PLAN.md
    ARCHITECTURE.md
    CONTRACTS.md
    OWNERS.md
    ACCEPTANCE.md
  packages/
    contracts/
      README.md
      openapi/
        openapi.yaml          # HTTP 总契约（可先 paths+schemas 骨架）
      jsonschema/
        document_bundle.schema.json
        form_field.schema.json
        form_job.schema.json
        fill_result.schema.json
        rag_query.schema.json
        settings.schema.json
      python/                 # 可选：Pydantic 镜像，与 jsonschema 同步
        pyproject.toml
        aff_contracts/
          __init__.py
          ingest.py
          rag.py
          fill.py
          export.py
          common.py
  apps/
    api/
      README.md
      pyproject.toml          # 骨架依赖即可
      app/
        main.py               # 挂路由，返回 501/健康检查
        api/
          health.py
          settings.py
          knowledge.py
          forms.py
        modules/
          ingest/
            README.md         # I/O 说明
            port.py           # Protocol / ABC：输入输出类型
            service.py        # raise NotImplementedError
          rag/
            README.md
            port.py
            service.py
          fill/
            README.md
            port.py
            service.py
            parsers/          # excel.py word.py pdf.py 空壳
          export/
            README.md
            port.py
            service.py
            writers/          # excel.py word.py pdf.py 空壳
          orchestrator/
            README.md
            jobs.py           # 状态机空壳
        core/
          config.py
          paths.py
      tests/
        contracts/            # 契约样例 fixture 是否通过 schema
    web/
      README.md
      package.json            # 骨架
      src/app/                # 占位路由：设置/知识库/填表/预览
  data/                       # gitignore 内容；保留 .gitkeep
    knowledge/raw/.gitkeep
    forms/raw/.gitkeep
    exports/.gitkeep
    lightrag/.gitkeep
  docker-compose.yml          # api + web 占位
  .env.example
  .gitignore
```

**阶段 0 完成标准**：协作者 clone 后能对照 `docs/` + `packages/contracts` 开工；API 能访问 `/health`；各模块 port 签名稳定；无真实填表/索引逻辑也可接受。

---

## 模块输入输出契约（核心）

### 公共类型

```text
FileRef: { path: str, filename: str, mime: str, sha256: str, size: int }

JobStatus: pending | running | succeeded | failed

Confidence: number 0..1
```

### P1 — Ingest

**输入**

```text
IngestRequest:
  doc_id: str
  file: FileRef
  source: knowledge          # 仅知识库文件
  options:
    language: "zh" | "en" | "auto"
```

**输出**

```text
DocumentBundle:
  doc_id: str
  title: str
  media_type: str
  text: str                  # 主文本（必填，供 LightRAG insert）
  chunks_hint: optional [{ text, heading?, page?, sheet? }]  # 可选，P2 可忽略自切
  tables: optional [{ name?, headers[], rows[][] }]          # xlsx/pdf表结构化辅助
  metadata:
    filename, mime, sha256, page_count?, sheet_names?, created_at
  warnings: string[]
```

**职责边界**

- 负责：pdf/docx/md/txt/xlsx → 文本与可选结构化表；编码/基础清洗。
- 不负责：调用 LLM、写图谱、向量化。
- 失败：抛 `IngestError(code, message)`；orchestrator 标 failed。

### P2 — RAG / LightRAG

**输入（索引/更新）**

```text
UpsertDocumentRequest:
  bundle: DocumentBundle
  mode: insert | reindex     # 同 doc_id 再来：先按 LightRAG 删除再插入，或官方更新路径
```

**输入（删除）**

```text
DeleteDocumentRequest:
  doc_id: str
```

**输入（查询）**

```text
RagQueryRequest:
  query: str
  mode: "mix" | "hybrid" | "local" | "global" | "naive"   # 默认 mix
  subject_hint: "self"       # 固定本人
  response_format: text | json_object
```

**输出**

```text
UpsertDocumentResult:
  doc_id: str
  status: ready | failed
  stats: { entities_upserted?, relations_upserted?, chunks? }  # 能给则给
  error?: str

RagQueryResult:
  answer: str
  contexts: [{ content, doc_id?, score?, entities? }]
  raw?: object               # LightRAG 原始可调试字段
```

**图谱更新语义（硬性需求）**

| 事件 | 行为 |
|---|---|
| 首次上传 doc_id | `ainsert` 文本 → 抽取实体/关系 → **合并进现有图谱**（同名实体融合由 LightRAG 负责） |
| 同一文件更新（同 doc_id 新内容） | **先 delete 旧文档图谱贡献，再 insert 新 bundle**（避免陈旧节点残留）；状态：reindexing |
| 新文件（新 doc_id） | 仅 insert；与已有节点按实体名/LightRAG 策略连接 |
| 删除文档 | LightRAG 文档删除 + 受影响实体/关系重建或清理 |
| 查询 | 默认 `mix`；填表侧可要求 `json_object` |

实现约束：

- 工作目录 working_dir = `data/lightrag`
- LLM/Embedding 来自 settings（OpenAI 兼容 | Ollama）
- Embedding 变更：拒绝静默切换，需清空重建（settings 层提示）
- **P2 不解析原始 pdf/xlsx**，只吃 `DocumentBundle`

### P3 — Fill（解析表 + 问图谱）

**输入**

```text
ParseFormRequest:
  job_id: str
  file: FileRef              # xlsx | docx | pdf

FillFormRequest:
  job_id: str
  fields: FormField[]        # parse 产物；value 可空
  rag: RagPort               # 由 orchestrator 注入，P3 只依赖 port
```

**FormField（P3→P4 关键契约）**

```text
FormField:
  id: str
  name: str                  # 题干/标签
  field_type: text|date|number|single_choice|multi|other
  value: str | null
  original_value: str | null
  required: bool
  confidence: number | null
  sources: [{ doc_id?, snippet, score? }]
  status: empty|suggested|confirmed|rejected|manual
  # 版式
  layout: label_value | header_row_table
  # 多行
  row_group_id: str | null   # 同一数据表
  row_index: int | null      # 0-based 数据行
  column_key: str | null     # 表头名
  # 写回
  locator: ExcelLocator | WordLocator | PdfAcroLocator | PdfBboxLocator
  notes: str | null

ExcelLocator: { kind: excel_cell, sheet, row, col, merged_range? }
WordLocator:  { kind: word_cell, table_index, row, col } | { kind: word_bookmark, name }
PdfAcroLocator: { kind: pdf_acroform, field_name }
PdfBboxLocator: { kind: pdf_bbox, page, x0, y0, x1, y1 }
```

**多行策略（开放类型）**

1. 识别 `header_row_table`：headers[] + 空数据区。
2. 将「表名/周围标题 + headers」作为 **schema** 问 P2：  
   `请根据本人知识，列出符合该表结构的记录数组 JSON，无则 []`。
3. 模型推断行实体类型（工作/教育/项目/…不限枚举）。
4. 映射为多行 `FormField`（同一 `row_group_id`，不同 `row_index`）。
5. 单行 `label_value`：每字段独立 query 或批量 JSON。
6. **无证据 → value=null, confidence=0**，禁止瞎填。
7. 上限：`max_rows` 配置（默认 50），防爆。

**输出**

```text
ParseFormResult:
  job_id: str
  format: xlsx|docx|pdf
  fields: FormField[]
  structure_notes: string[]

FillResult:
  job_id: str
  fields: FormField[]        # 已填 suggested
  stats: { filled, empty, low_confidence }
```

**边界**

- P3 **不**写回文件、**不**直接碰 LightRAG 存储细节，只调 `RagPort.query`。
- P3 **不**做前端。

### P4 — Export + Web

**Export 输入**

```text
ExportRequest:
  job_id: str
  source_file: FileRef       # 原始表
  fields: FormField[]        # 用户确认后的值；必须含 locator
  options: { flatten_pdf?: bool }
```

**输出**

```text
ExportResult:
  job_id: str
  output: FileRef            # data/exports/...
  side_files?: FileRef[]     # 平面 PDF 可附填写清单 JSON
```

**Web 页面（占位 → 实现）**

1. 设置：模型 Provider / Key / Base / Embedding  
2. 知识库：上传、列表、状态（indexing/ready）、删除、简单问答探测  
3. 填表：上传 → 解析状态 → 自动填 → **预览编辑**（含多行网格）→ 导出下载  
4. 任务历史列表  

**边界**

- P4 不改图谱；不重新解析知识文件。  
- 回填严格按 `locator`；禁止丢版式整篇生成（除非 PDF 平面降级策略）。

### 编排层 / HTTP（薄层）

| API | 编排 |
|---|---|
| `POST /api/knowledge/upload` | 存盘 → P1.ingest → P2.upsert → 状态 |
| `DELETE /api/knowledge/{id}` | P2.delete + 元数据 |
| `POST /api/knowledge/query` | P2.query |
| `POST /api/forms/upload` | 存盘 → P3.parse → job |
| `POST /api/forms/jobs/{id}/fill` | P3.fill(rag=P2) |
| `PATCH /api/forms/jobs/{id}/fields` | 只更新 DB 中字段（用户编辑） |
| `POST /api/forms/jobs/{id}/export` | P4.export |
| `GET /api/forms/jobs/{id}/download` | 读 exports |
| `GET/PUT /api/settings` | 本机配置 |
| `GET /api/health` | ok |

异步：索引与 fill 用 job 状态机（SQLite）；轮询或 SSE 二选一（契约里先规定 `GET .../status`）。

---

## 关键场景（验收用）

### S1 新知识入库更新图谱

1. 用户上传 `resume.pdf` → P1 → Bundle  
2. P2 insert → 图谱出现「本人-就职-公司X」等节点  
3. 再上传 `certificate.docx`（新 doc_id）→ P2 insert → **原有节点保留并可能与新实体连边**  
4. 问答「我的证书」能命中新文档  

### S2 同文档更新

1. 用户再次上传覆盖同一知识条目（同 doc_id）  
2. P2：**删除旧文档贡献 → 再 insert**  
3. 旧公司名不再出现，新公司名出现  

### S3 标签-值表

1. 上传「姓名/手机/邮箱」空白 xlsx  
2. P3 parse → 3 个 label_value 字段  
3. P3 逐字段 query P2 → suggested  
4. 用户改手机号 → export → 手机为用户值（**不回写图谱**）  

### S4 表头多行开放类型

1. 表头：时间 | 组织 | 角色 | 说明  
2. P3 问图谱要 JSON 数组 → 映射多行字段  
3. 预览网格可改/删行 → P4 按行写回  

### S5 删除知识

1. DELETE 文档 → 图谱清理 → 原问题答不出已删事实  

---

## 技术选型（实现阶段）

| 层 | 选型 |
|---|---|
| 前端 | Next.js + TS + shadcn/ui |
| 后端 | FastAPI + Pydantic v2 |
| 契约 | JSON Schema + OpenAPI；可选 Python package `aff_contracts` |
| RAG | LightRAG 进程内嵌于 P2 |
| DB | SQLite 任务/文档元数据 |
| Excel | openpyxl |
| Word | python-docx |
| PDF | pypdf（AcroForm）+ pdfplumber（平面文本） |
| 部署 | Docker Compose（api+web；ollama 可选） |

---

## 分阶段任务

### 阶段 0 — 空骨架 + 契约 + 仓库规划（当前目标）

1. 创建目录树与 README/docs（规划、归属、契约、验收文档）。  
2. 写全 `packages/contracts` 的 JSON Schema + OpenAPI 路径骨架。  
3. 四个模块 `port.py` + `service.py`（未实现占位）+ 模块 README（仅说明输入输出）。  
4. FastAPI 路由挂上并返回 501；`GET /health` 返回 200。  
5. 前端四个占位页。  
6. 契约样例 JSON（成功/失败）供各人单测。  
7. 推送 GitHub；在 OWNERS 中写清谁实现哪一目录。

### 阶段 1 — Schema + 历史资料知识闭环

8. **2.1** Schema 初稿评审（全员对齐）。  
9. **1.1** 多源资料 → 统一表示 / DocumentBundle。  
10. **2.1** 抽取 + 图谱入库/删除/查询；验证 **S1/S2/S5**。  
11. **统筹** 设置页与知识库 UI、模型配置。  

### 阶段 2 — 任务理解 + Agent

12. **1.2** Word 优先：结构 + 填写位置。  
13. **1.3** 语义 + TaskSpec（对齐 Schema）。  
14. **2.2** Agent 检索/Prompt/建议填写；模型选型对比。  
15. **统筹** 任务状态与填表预览 API 串接。  

### 阶段 3 — 回填 + 前端闭环

16. **统筹** 写回 xlsx/docx/pdf；平面 PDF 降级。  
17. **统筹** 预览编辑 + 下载 E2E（S3）。  
18. 扩展 PDF/Excel 任务链路（S4）。  

### 阶段 4 — 打磨

19. Compose 一键启动；错误与脱敏日志；部署说明。  

---

## 风险与对策

| 风险 | 对策 |
|---|---|
| 多人接口漂移 | 契约包唯一真相；CI 校验样例 JSON ↔ schema（实现期加） |
| 开放多行不稳 | max_rows；预览必改；空数组合法；低置信度标色 |
| 图谱陈旧 | 同 doc_id 更新 = delete+insert；禁止只插不删 |
| 1.2 位置与回填 locator 不一致 | 1.2/统筹共同约定 locator；导出前校验 |
| 任务格式范围过大 | 1.2 先 Word，再 PDF/Excel |
| 云端 LLM 隐私 | 设置页明示；默认可走本地模型 |
| Schema 与语义漂移 | 2.1 门禁；1.3/2.2 变更会签 |

---

## 验收标准（MVP）

1. 仓库含完整 docs + contracts + 空模块，新人能按 OWNERS 开工。  
2. 上传 ≥2 份知识文档后问答能答本人事实；再上传新文档后答案**增加**新事实（图谱已更新）。  
3. 更新/删除文档后答案与图谱一致（无陈旧主事实）。  
4. xlsx/docx/pdf 均可走通：解析 → 填写 → 预览改 → 下载；Excel/Word/可填写 PDF 写回关键字段正确。  
5. 多行表能产出多于 1 行建议或合法空表；用户可编辑后导出。  
6. 填写确认值**不会**出现在后续无关知识问答中（无回写）。  
7. 无登录；本地可启动。  

---

## 可默认的开放问题

| 问题 | 默认 |
|---|---|
| 多行预览界面 | 表格网格编辑；有余力再加来源侧栏 |
| 任务队列 | SQLite 状态 + BackgroundTasks |
| LightRAG 存储 | 默认本地文件；文档中注明可替换 |
| OCR | 可选，默认关闭 |
| 编排层归属 | 统筹（SidTian） |
| 契约语言 | 以 JSON Schema 为主；后端用 Python Pydantic 镜像 |

---

## 实现注意事项（给编码 Agent / 协作者）

- 分工以 `docs/DIVISION.md` 为准；产品决策见本文。  
- **2.1** 必须实现「新文件 → 图谱增量合并」与「同 id 更新 → 先删后插」。  
- **1.1** 输出必须能被 2.1 直接消费（至少 `bundle.text` 非空）。  
- **2.2** 依赖图谱查询抽象，单测可 mock。  
- **统筹回填** 无 locator 则拒绝导出。  
- 日志脱敏：API Key、身份证等。  
