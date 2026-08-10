# 负责人与目录归属

项目：**智填 ZhiFill**  
共 **6 人**：统筹（SidTian）+ **1.1 / 1.2 / 1.3 / 2.1 / 2.2**。  
详细任务见 **[DIVISION.md](./DIVISION.md)**。

## 统筹（SidTian）

| 职责 | 目录 / 范围 |
|------|-------------|
| 总体规划、契约评审、联调验收 | `docs/`、`packages/contracts/`（变更把关） |
| 前端实现 | `apps/web/` |
| 数据回填与导出 | `apps/api/app/modules/export/` |
| 系统集成 / API 编排 / 部署 | `apps/api/app/api/`、`modules/orchestrator/`、`core/`、`docker-compose.yml` |

## 五人研究方向

| 编号 | 方向 | 负责人（GitHub） | 负责目录 |
|------|------|------------------|----------|
| **1.1** | 资料统一表示（历史资料） | _待填写_ | `apps/api/app/modules/ingest/` |
| **1.2** | 任务文档结构解析 | _宋瑞_ | `apps/api/app/modules/form_structure/` |
| **1.3** | 语义理解与任务需求建模 | _待填写_ | `apps/api/app/modules/task_semantics/` |
| **2.1** | 知识抽取与知识图谱（含 Schema） | _待填写_ | `apps/api/app/modules/rag/` |
| **2.2** | Agent 智能推理与填报生成 | _待填写_ | `apps/api/app/modules/fill/`（Agent/填写逻辑） |

契约包 `packages/contracts/`：**全员只读使用**；修改须 **单独 PR**，统筹 review，相关方向会签。

## PR 边界

- 功能 PR **只修改** 本人目录及对应测试。
- **1.2 / 1.3 / 2.2** 数据依次交接：结构 → 语义/TaskSpec → FillResult；勿互相覆盖 `service` 职责。
- 新建目录时同步补 `port.py` 与契约，走契约评审。
- 禁止在未结对情况下实现他人业务逻辑。

## 各角色优先阅读

| 编号 | 从这些文件开始 |
|------|----------------|
| 统筹 | `DIVISION.md`、`openapi.yaml`、`export/port.py`、`apps/web/` |
| 1.1 | `modules/ingest/port.py`，`document_bundle.schema.json` |
| 1.2 | `DIVISION.md` §1.2，`form_field` locator 约定 |
| 1.3 | `DIVISION.md` §1.3，待增 `TaskSpec` 契约；2.1 Schema |
| 2.1 | `modules/rag/port.py`，`rag_query` schema，`ARCHITECTURE.md` 图谱语义 |
| 2.2 | `modules/fill/port.py`，`fill_result` schema；1.3 任务需求格式 |
