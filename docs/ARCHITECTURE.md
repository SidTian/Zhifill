# 系统架构

## 第一阶段定位

个人知识库（Personal KB）路线验证：

**历史资料 → 统一表示(1.1) → 抽取与图谱(2.1) → 任务结构(1.2) → 任务语义(1.3) → Agent(2.2) → 前端预览与回填（统筹）**

企业知识库为后续扩展。Schema 由 **2.1** 设计，全系统共用。

## 总览

```
历史资料 ──► [1.1 统一表示] ──DocumentBundle──► [2.1 抽取+LightRAG] ──► 个人知识图谱
                                                      ▲
当前任务 ──► [1.2 结构解析] ──结构+位置──► [1.3 语义/TaskSpec] ──► [2.2 Agent] ──query─┘
                                                      │
                                                      ▼
                                            建议填写结果 FillResult
                                                      │
                                                      ▼
                              [统筹：前端预览确认] ──► [统筹：export 回填] ──► 下载
```

人员与任务见 `docs/DIVISION.md`。

## 模块划分

| 编号 | 模块目录 | 输入 | 输出 |
|------|----------|------|------|
| 1.1 | `modules/ingest` | 历史资料文件 | `DocumentBundle`（或扩展统一格式） |
| 1.2 | `modules/form_structure` | 待填 Word/PDF/Excel | 结构树 + 填写位置 |
| 1.3 | `modules/task_semantics` | 结构树 + Schema | 字段语义 + **TaskSpec** |
| 2.1 | `modules/rag` | Bundle；query | 图谱增删；`RagQueryResult`；**Schema** |
| 2.2 | `modules/fill` | TaskSpec + 字段 + RagPort | `FillResult` |
| 统筹 | `apps/web` + `export` + 编排 | 用户操作；确认字段 | UI；导出文件；可运行部署 |

编排层（统筹，`orchestrator` + `api`）只做：

- HTTP 入参校验、文件落盘、任务状态机
- 调用各模块 **port**，不深入对方内部实现

## 知识图谱更新语义（2.1）

| 事件 | 行为 |
|------|------|
| 首次上传（新 `doc_id`） | 插入 → 实体/关系 **合并** 进现有图谱 |
| 同一 `doc_id` 更新 | **先删**旧贡献再 **插入** 新内容 |
| 新 `doc_id` | 仅插入并与已有实体连边 |
| 删除 | 删除文档贡献并清理受影响子图 |
| 查询 | 默认宜支持混合检索；Agent 可要求结构化输出 |

约束：

- 工作目录建议：`data/lightrag`
- 2.1 不解析原始办公文件，只消费 1.1 产出
- Embedding 更换需全量重建（设置页破坏性确认）
- **新上传知识文件必须更新图谱节点/关系**

## 填表数据流

1. 上传任务文件 → 1.2 结构 + 位置（locator 基础）
2. 1.3 语义对齐 Schema → 产出 TaskSpec 与带语义的字段清单
3. 2.2 按 TaskSpec 查 2.1 → FillResult
4. 前端预览修改；**不回写图谱**
5. export 按 locator 写回 → 下载

### 任务文件优先级（1.2）

1. Word（第一阶段优先）  
2. PDF  
3. Excel  

### locator 规则

可写回字段必须具备稳定 locator；导出时拒绝缺失 locator 的写回项。

## 运行时目录

```
data/
  knowledge/raw/     # 历史资料
  forms/raw/         # 当前任务文件
  exports/           # 回填输出
  lightrag/          # 图谱工作目录
  app.db             # 元数据（实现期）
```

## 技术栈（实现期）

- API：FastAPI + Pydantic v2  
- 图谱：LightRAG（或 2.1 论证的等价方案）  
- 文档：python-docx / pypdf / openpyxl / pdfplumber 等  
- 前端：Next.js + TypeScript  
- 模型：OpenAI 兼容 API 或 Ollama（2.2 负责选型对比）  

## 异步任务

索引与 Agent 填写耗时长：任务记录 + 状态轮询。骨架可用内存占位，实现期 SQLite。
