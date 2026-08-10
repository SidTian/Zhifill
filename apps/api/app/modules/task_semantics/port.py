from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class TaskSemanticsPort(Protocol):
    """1.3: 结构 → 字段语义 + TaskSpec（供 2.2 Agent）。"""

    def build_task_spec(
        self,
        structure: dict[str, Any],
        *,
        schema_ref: str | None = None,
    ) -> dict[str, Any]:
        """结合 2.1 Schema，产出任务需求表示与带语义的字段信息。

        具体 schema 由契约 PR 固化（TaskSpec）。
        """
        ...
