from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TaskField(BaseModel):
    field_id: str
    label: str
    entity: str | None = None
    attribute: str | None = None
    query: str | None = None
    status: Literal["aligned", "unaligned"]
    row_index: int | None = None


class TaskSpec(BaseModel):
    schema_ref: str
    fields: list[TaskField] = Field(default_factory=list)
