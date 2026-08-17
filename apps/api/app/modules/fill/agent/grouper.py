from __future__ import annotations

from dataclasses import dataclass, field

from aff_contracts.fill import FormField, LayoutKind


@dataclass
class FieldGroup:
    """一组待一起检索/生成的字段。

    layout=label_value:  key = f"single-{field.id}"，通常每个 group 一个字段
    layout=header_row_table: key = row_group_id，同 group 字段共享一次 bulk 生成
    """

    key: str
    layout: LayoutKind
    fields: list[FormField] = field(default_factory=list)
    headers: list[str] | None = None  # header_row_table: 汇总唯一 column_key


class FieldGrouper:
    """Day 2: 按 row_group_id + layout + field_type 分组的预处理器。"""

    @staticmethod
    def group(fields: list[FormField]) -> list[FieldGroup]:
        by_key: dict[str, FieldGroup] = {}
        for f in fields:
            if f.layout == LayoutKind.header_row_table and f.row_group_id:
                key = f.row_group_id
            else:
                key = f"single-{f.id}"
            if key not in by_key:
                by_key[key] = FieldGroup(key=key, layout=f.layout)
            by_key[key].fields.append(f)

        for g in by_key.values():
            if g.layout == LayoutKind.header_row_table:
                col_keys = sorted({f.column_key for f in g.fields if f.column_key})
                g.headers = col_keys or None
        return list(by_key.values())
