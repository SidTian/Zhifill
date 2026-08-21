"""1.2 用户任务文档结构解析契约。

与 packages/contracts/jsonschema/form_structure.schema.json 保持同步。

设计要点：
- fields[].locator 复用 fill.Locator 判别联合，保证全项目 locator 类型统一。
- FormStructureField 只含「位置 + 启发式标签」，不含业务语义（语义留给 1.3）。
- format 预留 docx/pdf/xlsx，便于后续扩展。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from aff_contracts.fill import Locator


class Heading(BaseModel):
    """标题段落。"""

    index: int = Field(ge=0, description="在文档段落列表中的下标")
    level: int = Field(ge=1, description="标题层级，1 为最高")
    text: str = Field(min_length=1)
    style: str = Field(description="段落样式名，如 'Heading 1' / '标题 2'")


class Paragraph(BaseModel):
    """正文段落（含标题，按原文顺序，便于定位）。"""

    index: int = Field(ge=0)
    text: str
    style: str = "Normal"


class TableCell(BaseModel):
    """表格单元格。合并块只在左上角记录一次，rowspan/colspan > 1 表示合并。"""

    row: int = Field(ge=0)
    col: int = Field(ge=0)
    text: str = ""
    merged: bool = Field(default=False, description="是否属于一个 >1 格的合并块")
    rowspan: int | None = Field(default=None, ge=1, description="合并跨行数（仅 merged=True 时有值）")
    colspan: int | None = Field(default=None, ge=1, description="合并跨列数（仅 merged=True 时有值）")


class MergedRange(BaseModel):
    """合并单元格的边界范围（左上到右下）。"""

    min_row: int = Field(ge=0)
    min_col: int = Field(ge=0)
    max_row: int = Field(ge=0)
    max_col: int = Field(ge=0)


class TableStructure(BaseModel):
    """单个表格的结构化表示。"""

    index: int = Field(ge=0, description="文档中第几个表格（0 基）")
    rows: int = Field(ge=0)
    cols: int = Field(ge=0)
    cells: list[TableCell] = Field(default_factory=list)
    merged_ranges: list[MergedRange] = Field(default_factory=list)
    header_rows: int = Field(
        default=0,
        ge=0,
        description="启发式推断的表头行数。多级表头时 >1；form 式标签同行表为 0；"
        "配合 merged_ranges 可还原多级表头层级",
    )


class FormStructureField(BaseModel):
    """结构层可填写位置：定位坐标 + 启发式标签 + 填写类型。

    name 为空时表示无法从邻近单元格推断标签，业务语义判断交给 1.3。
    fill_kind 区分纯空格填写位与带固定提示文字的填空栏（日期/地址/盖章等），
    供 1.3 语义层与前端选择合适控件（如日期选择器）。
    """

    id: str = Field(min_length=1, description="位置唯一标识，如 'word_t0_r0_c1'")
    name: str = Field(default="", description="启发式推断的标签（向左/向上扫描最近表头文字）")
    fill_kind: Literal["empty", "template"] = Field(
        default="empty",
        description="empty=纯空格填写位；template=带固定提示文字的填空栏（年月日/省市县/盖章等）",
    )
    locator: Locator


class FormStructureResult(BaseModel):
    """1.2 待填任务文件的结构解析结果。

    由 FormStructurePort.parse_structure 产出，供 1.3 语义层与统筹回填使用。
    """

    format: Literal["docx", "pdf", "xlsx"]
    filename: str
    title: str
    headings: list[Heading] = Field(default_factory=list)
    paragraphs: list[Paragraph] = Field(default_factory=list)
    tables: list[TableStructure] = Field(default_factory=list)
    fields: list[FormStructureField] = Field(default_factory=list)
    structure_notes: list[str] = Field(default_factory=list)
