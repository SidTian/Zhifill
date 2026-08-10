from __future__ import annotations

from typing import Any

from app.core.errors import NotImplementedModule
from app.modules.task_semantics.port import TaskSemanticsPort


class TaskSemanticsService(TaskSemanticsPort):
    def build_task_spec(
        self,
        structure: dict[str, Any],
        *,
        schema_ref: str | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedModule("task_semantics", "build_task_spec")


def get_task_semantics_service() -> TaskSemanticsPort:
    return TaskSemanticsService()
