from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class FormStructurePort(Protocol):
    """1.2: 待填任务文件 → 结构树 + 填写位置（locator 基础）。"""

    def parse_structure(self, file_path: str, *, filename: str) -> dict[str, Any]:
        """返回机器可理解的文档结构（标题/段落/表格区域/填写位置）。

        已支持 Word(.docx) 与 Excel(.xlsx)；PDF 后续扩展。
        输出 schema 见 packages/contracts 的 FormStructureResult。
        """
        ...
