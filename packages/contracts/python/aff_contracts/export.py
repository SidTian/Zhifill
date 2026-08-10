from __future__ import annotations

from pydantic import BaseModel, Field

from aff_contracts.common import FileRef
from aff_contracts.fill import FormField


class ExportOptions(BaseModel):
    flatten_pdf: bool = False


class ExportRequest(BaseModel):
    job_id: str
    source_file: FileRef
    fields: list[FormField]
    options: ExportOptions = Field(default_factory=ExportOptions)


class ExportResult(BaseModel):
    job_id: str
    output: FileRef
    side_files: list[FileRef] = Field(default_factory=list)
