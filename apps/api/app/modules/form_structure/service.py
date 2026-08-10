from __future__ import annotations

from typing import Any

from app.core.errors import NotImplementedModule
from app.modules.form_structure.port import FormStructurePort


class FormStructureService(FormStructurePort):
    def parse_structure(self, file_path: str, *, filename: str) -> dict[str, Any]:
        raise NotImplementedModule("form_structure", "parse_structure")


def get_form_structure_service() -> FormStructurePort:
    return FormStructureService()
