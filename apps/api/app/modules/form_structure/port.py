from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class FormStructurePort(Protocol):
    """1.2: 待填任务文件 → 结构树 + 填写位置（locator 基础）。"""

    def parse_structure(self, file_path: str, *, filename: str) -> dict[str, Any]:
        """返回机器可理解的文档结构（标题/段落/表格区域/填写位置）。

        第一阶段优先 Word；PDF/Excel 后续扩展。
        具体 schema 由契约 PR 固化（FormStructureResult）。
        """
        ...
