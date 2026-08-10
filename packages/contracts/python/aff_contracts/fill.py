from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from aff_contracts.common import FileRef, SourceRef


class FieldType(str, Enum):
    text = "text"
    date = "date"
    number = "number"
    single_choice = "single_choice"
    multi = "multi"
    other = "other"


class FieldStatus(str, Enum):
    empty = "empty"
    suggested = "suggested"
    confirmed = "confirmed"
    rejected = "rejected"
    manual = "manual"


class LayoutKind(str, Enum):
    label_value = "label_value"
    header_row_table = "header_row_table"


class ExcelLocator(BaseModel):
    kind: Literal["excel_cell"] = "excel_cell"
    sheet: str
    row: int = Field(ge=1)
    col: int = Field(ge=1)
    merged_range: str | None = None


class WordCellLocator(BaseModel):
    kind: Literal["word_cell"] = "word_cell"
    table_index: int = Field(ge=0)
    row: int = Field(ge=0)
    col: int = Field(ge=0)


class WordBookmarkLocator(BaseModel):
    kind: Literal["word_bookmark"] = "word_bookmark"
    name: str


class PdfAcroLocator(BaseModel):
    kind: Literal["pdf_acroform"] = "pdf_acroform"
    field_name: str


class PdfBboxLocator(BaseModel):
    kind: Literal["pdf_bbox"] = "pdf_bbox"
    page: int = Field(ge=0)
    x0: float
    y0: float
    x1: float
    y1: float


Locator = Annotated[
    ExcelLocator
    | WordCellLocator
    | WordBookmarkLocator
    | PdfAcroLocator
    | PdfBboxLocator,
    Field(discriminator="kind"),
]


class FormField(BaseModel):
    id: str
    name: str
    field_type: FieldType = FieldType.text
    value: str | None = None
    original_value: str | None = None
    required: bool = False
    confidence: float | None = Field(default=None, ge=0, le=1)
    sources: list[SourceRef] = Field(default_factory=list)
    status: FieldStatus = FieldStatus.empty
    layout: LayoutKind = LayoutKind.label_value
    row_group_id: str | None = None
    row_index: int | None = Field(default=None, ge=0)
    column_key: str | None = None
    locator: Locator
    notes: str | None = None


class FormJobStatus(str, Enum):
    pending = "pending"
    parsing = "parsing"
    filling = "filling"
    review = "review"
    exporting = "exporting"
    done = "done"
    failed = "failed"


class FormJob(BaseModel):
    id: str
    filename: str
    format: Literal["xlsx", "docx", "pdf"]
    status: FormJobStatus
    fields: list[FormField] = Field(default_factory=list)
    created_at: str
    updated_at: str
    error: str | None = None
    progress: dict[str, int | str] | None = None


class ParseFormRequest(BaseModel):
    job_id: str
    file: FileRef


class ParseFormResult(BaseModel):
    job_id: str
    format: Literal["xlsx", "docx", "pdf"]
    fields: list[FormField]
    structure_notes: list[str] = Field(default_factory=list)


class FillFormRequest(BaseModel):
    job_id: str
    fields: list[FormField]


class FillStats(BaseModel):
    filled: int = 0
    empty: int = 0
    low_confidence: int = 0


class FillResult(BaseModel):
    job_id: str
    fields: list[FormField]
    stats: FillStats
