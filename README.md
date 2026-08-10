# 智填 ZhiFill

个人知识图谱自动填表：历史资料 → 知识图谱 → 任务文件理解 → Agent 填报 → 预览确认 → 回填下载。

> **第一阶段**：个人用户知识库（Personal KB）路线验证；企业知识库后续扩展。  
> **协作主文档**：[docs/DIVISION.md](docs/DIVISION.md)

## 文档

| 文档 | 说明 |
|------|------|
| [docs/DIVISION.md](docs/DIVISION.md) | **第一阶段架构与 6 人分工（主文档）** |
| [docs/OWNERS.md](docs/OWNERS.md) | 目录归属与认领 |
| [docs/PLAN.md](docs/PLAN.md) | 产品决策与阶段计划 |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 模块边界与数据流 |
| [docs/CONTRACTS.md](docs/CONTRACTS.md) | 契约索引与版本规则 |
| [docs/ACCEPTANCE.md](docs/ACCEPTANCE.md) | 验收清单 |
| [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md) | Python / Node / 依赖约束 |

## 人员（6 人）

| 编号 | 职责 | 目录 |
|------|------|------|
| **统筹（SidTian）** | 规划 · 前端 · 自动回填 · 系统集成 | `docs/`、`apps/web/`、`export/`、编排与 Compose |
| **1.1** | 历史资料统一表示 | `modules/ingest/` |
| **1.2** | 任务文档结构解析（先 Word） | `modules/form_structure/` |
| **1.3** | 语义理解与任务需求建模 | `modules/task_semantics/` |
| **2.1** | Schema + 知识抽取与图谱 | `modules/rag/` |
| **2.2** | Agent 检索 / Prompt / 生成 | `modules/fill/` |

跨模块只依赖 `packages/contracts` 与各模块 `port.py`。

## 环境约束（必读）

详见 **[docs/ENVIRONMENT.md](docs/ENVIRONMENT.md)**。

| 项 | 版本 |
|----|------|
| Python | **3.12.x**（`>=3.12,<3.14`） |
| Node.js | **20.x** |
| 后端锁 | `apps/api/requirements.lock` |
| 依赖声明 | `apps/api/pyproject.toml` |

## 快速启动（骨架）

### API

```bash
cd apps/api
python3.12 -m venv .venv
source .venv/bin/activate
pip install -U pip setuptools wheel
pip install -e ../../packages/contracts/python
pip install -r requirements.lock
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

- Health: `GET http://127.0.0.1:8000/api/health`
- 业务路由当前可能返回 **501**（待各方向实现）

### Web

```bash
cd apps/web
node -v    # v20.x
npm install
npm run dev
```

### Docker（可选）

```bash
cp .env.example .env
docker compose up --build
```

## 契约

- JSON Schema: `packages/contracts/jsonschema/`
- OpenAPI: `packages/contracts/openapi/openapi.yaml`
- 样例: `packages/contracts/fixtures/`
- Python 类型: `packages/contracts/python/aff_contracts/`

变更契约必须 bump 版本并在 PR 中说明。

## 数据目录

运行时文件落在 `data/`（内容 gitignore，保留 `.gitkeep`）。
