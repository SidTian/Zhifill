from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.api import forms, health, knowledge, settings
from app.core.errors import NotImplementedModule, error_body

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="智填 ZhiFill API",
    version="0.1.0",
    description="阶段 0 骨架 — 业务模块实现前返回 501。",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(settings.router)
app.include_router(knowledge.router)
app.include_router(forms.router)


@app.exception_handler(NotImplementedModule)
async def not_implemented_handler(_, exc: NotImplementedModule) -> JSONResponse:
    return JSONResponse(
        status_code=501,
        content=error_body(
            "not_implemented",
            str(exc),
            {"module": exc.module, "operation": exc.operation},
        ),
    )


@app.get("/", include_in_schema=False)
def root() -> FileResponse:
    """浏览器打开 http://127.0.0.1:8000 时的简易首页。"""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api", include_in_schema=False)
def api_info() -> dict[str, str]:
    return {
        "name": "zhifill",
        "title": "智填 ZhiFill",
        "phase": "0-skeleton",
        "home": "/",
        "docs": "/docs",
        "health": "/api/health",
    }
