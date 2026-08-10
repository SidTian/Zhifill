# 环境约束

全员开发与 CI 必须遵守本文档，避免「我这边能跑」问题。

## 运行时版本

| 组件 | 约束 | 说明 |
|------|------|------|
| **Python** | **3.12.x**（推荐）；允许 `>=3.12,<3.14` | 官方基准为 3.12；3.13 可用但不作为 CI 主版本 |
| Node.js | **20.x LTS** | 前端 Next.js 14 |
| npm | 随 Node 20 自带即可 | 锁定用 `package-lock.json`（有则必须提交） |
| Docker 基础镜像 | `python:3.12-slim` / `node:20-alpine` | 与上表一致 |

### 检查 Python 版本

```bash
python3 --version   # 应为 Python 3.12.x（或 3.13.x）
# 若过低/过高：
# pyenv install 3.12.8 && pyenv local 3.12.8
```

安装后端依赖时，pip 会校验 `requires-python`；不符合会直接失败。

## 后端包管理

- 清单：`apps/api/pyproject.toml`（唯一声明来源）
- 契约包：`packages/contracts/python/pyproject.toml`
- **版本锁定文件**：`apps/api/requirements.lock`（阶段 0 基线；改依赖后需同步更新）

### 安装（推荐）

```bash
cd apps/api
python3.12 -m venv .venv          # 明确用 3.12
source .venv/bin/activate
pip install -U "pip>=24.0" "setuptools>=68" "wheel"
pip install -e ../../packages/contracts/python
pip install -r requirements.lock  # 锁定版本
pip install -e ".[dev]"           # 可编辑安装本包 + 开发依赖
```

仅开发骨架、可接受解析范围时：

```bash
pip install -e ../../packages/contracts/python
pip install -e ".[dev]"
```

### 依赖分组（实现阶段按角色安装）

| extra | 用途 | 主要包（见 pyproject） |
|-------|------|------------------------|
| （默认） | API 骨架 | fastapi, uvicorn, pydantic… |
| `dev` | 测试 | pytest, httpx, jsonschema |
| `ingest` | 1.1 历史资料解析 | pypdf, python-docx, openpyxl, markdown… |
| `rag` | 2.1 知识图谱 | lightrag-hku 等 |
| `fill` | 1.2/1.3/2.2 任务侧与 Agent | openpyxl, python-docx, pypdf, pdfplumber |
| `export` | 统筹回填 | 与文档写回相关库 |
| `all` | 本地全量 | 上述全部 |

**规则**：默认依赖保持精简；业务库进对应 extra，禁止在未声明的情况下 `pip install` 新包并提交代码。新增包必须改 `pyproject.toml` 并更新 `requirements.lock`。

### 更新锁定文件

```bash
cd apps/api
source .venv/bin/activate
pip install -e ../../packages/contracts/python
pip install -e ".[dev]"
pip freeze | grep -vE '^-e |^aff-contracts|^zhifill|# Editable' > requirements.lock
# 在文件头补上注释说明（参考现有 requirements.lock 头部）
```

有 [uv](https://github.com/astral-sh/uv) 时更推荐：

```bash
uv pip compile pyproject.toml --extra dev -o requirements.lock --python-version 3.12
```

## 前端包管理

- 清单：`apps/web/package.json`
- 引擎：`engines.node = ">=20 <21"`（见 package.json）
- 安装：`npm ci`（有 lock 时）或 `npm install`

```bash
cd apps/web
node -v   # v20.x
npm install
```

## 禁止事项

1. 使用 Python **3.11 及以下** 或 **3.14+**（未验证）
2. 在业务 PR 中引入未写入 `pyproject.toml` / `package.json` 的依赖
3. 提交本机绝对路径的 venv、`.env` 真密钥
4. 随意放宽 `requires-python` 或依赖上界而不在 PR 说明原因

## 与角色的关系

| 小节 | 至少安装 |
|------|----------|
| 全员骨架 | `pip install -e ".[dev]"` + contracts |
| 统筹 前端 | Node 20 + `apps/web` |
| 统筹 回填/部署 | `.[dev,export]` + Docker |
| 1.1 资料统一表示 | `.[dev,ingest]` |
| 1.2 结构解析 | `.[dev,fill]`（docx 等） |
| 1.3 语义/TaskSpec | `.[dev]` + 按需 LLM 客户端 |
| 2.1 知识图谱 | `.[dev,rag]` |
| 2.2 Agent | `.[dev,fill]` + LLM |

## Docker

`docker compose` 使用镜像内的 Python 3.12 / Node 20，不依赖宿主机版本。  
本地混用时仍建议宿主机 Python 与文档一致，便于非 Docker 调试。
