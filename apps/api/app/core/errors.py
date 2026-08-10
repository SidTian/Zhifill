from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from fastapi.responses import JSONResponse


class NotImplementedModule(Exception):
    def __init__(self, module: str, operation: str) -> None:
        self.module = module
        self.operation = operation
        super().__init__(f"{module}.{operation} is not implemented")


def error_body(code: str, message: str, detail: Any = None) -> dict[str, Any]:
    body: dict[str, Any] = {"code": code, "message": message}
    if detail is not None:
        body["detail"] = detail
    return body


def not_implemented(module: str, operation: str) -> JSONResponse:
    return JSONResponse(
        status_code=501,
        content=error_body(
            "not_implemented",
            f"{module}.{operation} is not implemented (Phase 0 skeleton)",
            {"module": module, "operation": operation},
        ),
    )


def http_not_implemented(module: str, operation: str) -> HTTPException:
    return HTTPException(
        status_code=501,
        detail=error_body(
            "not_implemented",
            f"{module}.{operation} is not implemented (Phase 0 skeleton)",
            {"module": module, "operation": operation},
        ),
    )
