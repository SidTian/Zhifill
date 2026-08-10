# API（FastAPI）— 智填 ZhiFill

阶段 0 骨架。业务只实现在 `app/modules/*/service.py`（及 parsers/writers）。

## 环境

- Python **3.12.x**（见仓库 `docs/ENVIRONMENT.md`、根目录 `.python-version`）
- 依赖声明：`pyproject.toml`；锁定：`requirements.lock`

## 启动

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

按角色额外安装：`pip install -e ".[ingest]"` / `.[rag]` / `.[fill]` / `.[export]` / `.[all]`

- Swagger: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/api/health

## 测试

```bash
pytest
```
