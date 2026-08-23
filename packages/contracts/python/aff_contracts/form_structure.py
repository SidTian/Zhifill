from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class FormStructureResult(BaseModel):
    """1.2 模块输出契约：待填任务文件 → 结构树 + 填写位置(locator 基础)。

    顶层字段在 docx/xlsx 间统一；格式相关子结构按需填充：
    - docx：headings / paragraphs / tables 有值，sheets 为空
    - xlsx：sheets 有值，headings / paragraphs / tables 为空

    fields 是 1.2 的简化填写位（id/name/fill_kind/locator），
    其中 locator 须具备稳定可写回坐标（WordCellLocator / ExcelLocator），
    供 1.3 语义匹配与统筹回填使用；1.4 导出时拒绝缺失稳定 locator 的项。
    具体子结构（cell/merged_range/heading 等）由实现保持稳定，
    契约此处只保证顶层字段齐备，避免过早固化内部细节造成漂移。
    """

    format: Literal["docx", "xlsx", "pdf"]
    filename: str
    title: str
    headings: list[dict[str, Any]] = Field(default_factory=list)
    paragraphs: list[dict[str, Any]] = Field(default_factory=list)
    tables: list[dict[str, Any]] = Field(default_factory=list)
    sheets: list[dict[str, Any]] = Field(default_factory=list)
    fields: list[dict[str, Any]] = Field(default_factory=list)
    structure_notes: list[str] = Field(default_factory=list)
