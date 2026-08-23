"""1.2 用户任务文档结构解析 —— Word(.docx) / Excel(.xlsx) 实现。

职责：把待填文件解析成「结构树 + 填写位置(locator)」。
- Word：标题(headings) + 段落(paragraphs) + 表格(tables) + 填写位
- Excel：工作表(sheets) + 填写位
- 可填写位置(fields)：空单元格 + 模板填空栏 → locator，供统筹回填

不做：字段业务语义匹配(1.3)、写回文件(统筹)。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from docx import Document
from docx.document import Document as DocxDocument
from docx.table import Table
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from aff_contracts import FormStructureResult

from app.modules.form_structure.port import FormStructurePort


# Word 中标题样式的常见前缀（中英文）
_HEADING_STYLE_PREFIXES = ("Heading", "标题", "Title")

# 填空模板正则：日期、地址、盖章等固定提示文字
_DATE_TEMPLATE = re.compile(r"年\s+月\s+日")
_ADDR_TEMPLATE = re.compile(r"省\s+市\s+[县区]")
_SEAL_PATTERN = re.compile(r"盖章|签字|签名|签收")
# 格式说明词（短词，表示填写格式要求，非数据也非标签）
_FORMAT_HINT_WORDS = {"全称", "简称", "原名", "中文名", "英文名", "中文", "英文"}
# 真正的格式示例：括号内「数字%」或「数字/数字」，或纯「X/Y」形式
# 只匹配 2/50（4%）、3/100（5%）这类，排除列头说明「（100字）」「（按序填写）」
_FORMAT_EXAMPLE_PATTERN = re.compile(
    r"[\(（]\s*\d+\s*%|[\(（]\s*\d+\s*/\s*\d+|^\s*\d+\s*/\s*\d+\s*$"
)


def _is_format_hint(text: str) -> bool:
    """检测格式提示文字（告诉用户怎么填的简短说明，本身不是数据）。

    例：「全称」（要求填全称）、「2/50（4%）」（格式示例）。
    区别于预填数据：「4课时」是已填好的值，不含括号也不是格式词。
    """
    if text in _FORMAT_HINT_WORDS:
        return True
    if _FORMAT_EXAMPLE_PATTERN.search(text):
        return True
    return False


def _is_instruction_text(text: str) -> bool:
    """检测填写说明文字（有文字但是填写区，不是纯标签）。

    纯标签如「姓名」「项目名称」不含句子标点和指令词；
    填写说明如「大学期间获得的校级及以上奖励，如果无校级及以上，则院级也可以」
    「时间段＋具体岗位」含指令词/标点/填写提示符。
    """
    # 含填写提示符（全角/半角加号表示并列填写项）
    if re.search(r"[＋+]", text):
        return True
    # 含条件/建议指令词
    if any(kw in text for kw in ("如果", "如无", "请填写", "请写", "请如实")):
        return True
    # 含中文句子标点 + 长度>10 → 说明书/提示语
    if len(text) > 10 and re.search(r"[，。；]", text):
        return True
    return False


def _is_fillable_template(text: str) -> bool:
    """检测单元格是否是带固定提示文字的填空栏（非空但需要填写）。

    例：「年  月  日」「省  市  县  镇  村」「盖章：\\n年  月  日」
    「辅导员签字：」「大学期间获得的校级及以上奖励，...」
    这些单元格有文字但本质是填写区，不能当纯标签跳过。
    """
    if not text:
        return False
    if _DATE_TEMPLATE.search(text):
        return True
    if _ADDR_TEMPLATE.search(text):
        return True
    if _SEAL_PATTERN.search(text):
        return True
    if re.search(r"_{2,}", text):  # 下划线占位
        return True
    if _is_instruction_text(text):
        return True
    if _is_format_hint(text):
        return True
    return False


def _is_heading(style_name: str) -> bool:
    """判断段落样式是否是标题。"""
    return any(style_name.startswith(p) for p in _HEADING_STYLE_PREFIXES)


def _heading_level(style_name: str) -> int:
    """从样式名提取标题层级，如 'Heading 2' / '标题 1' → 2 / 1。取不到数字时按 1 级。"""
    for token in style_name.split():
        if token.isdigit():
            return int(token)
    return 1


def _extract_headings(doc: DocxDocument) -> list[dict[str, Any]]:
    """提取所有标题段落。"""
    headings: list[dict[str, Any]] = []
    for idx, para in enumerate(doc.paragraphs):
        style = para.style.name if para.style else ""
        text = para.text.strip()
        if not text:
            continue
        if _is_heading(style):
            headings.append(
                {
                    "index": idx,
                    "level": _heading_level(style),
                    "text": text,
                    "style": style,
                }
            )
    return headings


def _extract_paragraphs(doc: DocxDocument) -> list[dict[str, Any]]:
    """提取所有非空正文段落（含标题，按原文顺序，便于定位）。"""
    paragraphs: list[dict[str, Any]] = []
    for idx, para in enumerate(doc.paragraphs):
        text = para.text.strip()
        style = para.style.name if para.style else "Normal"
        paragraphs.append({"index": idx, "text": text, "style": style})
    return paragraphs


def _build_tc_grid(table: Table, num_rows: int, num_cols: int) -> list[list[Any]]:
    """预读所有 cell 的 _tc 引用并保持存活，防止 GC 导致 id() 地址复用。

    python-docx 的 table.cell(r,c) 每次返回新的 _Cell 包装对象；
    若不保持引用，旧对象被回收后 id() 会被新对象复用，造成「假合并」。
    合并单元格的多个 (r,c) 会指向同一个底层 <w:tc> 元素（_tc 相同）。
    """
    grid: list[list[Any]] = []
    for r in range(num_rows):
        row: list[Any] = []
        for c in range(num_cols):
            cell = table.cell(r, c)
            # 同时保持 cell 和 _tc 引用存活
            row.append({"cell": cell, "tc": cell._tc, "text": cell.text.strip()})
        grid.append(row)
    return grid


def _detect_header_rows(grid: list[list[dict[str, Any]]], num_rows: int, num_cols: int) -> int:
    """启发式推断表头行数（含多级表头）。

    规则：
    - 找到第一个含空单元格的行 → 该行之前都是表头（返回该行号）
    - form 式标签同行表（标签与空格同行）→ 返回 0（无独立表头行）
    - 无空单元格的展示表 → 返回 1（约定首行为表头）
    - 空表 → 返回 0

    配合 merged_ranges 可还原多级表头：header_rows > 1 且首行有 colspan 合并
    即为多级表头。
    """
    if num_rows == 0:
        return 0
    for r in range(num_rows):
        for c in range(num_cols):
            text = grid[r][c]["text"]
            if not text or _is_fillable_template(text):
                return r  # 第 r 行有可填写格，之前都是表头
    return 1  # 无可填写格，约定首行为表头


def _extract_table(table: Table, table_index: int) -> dict[str, Any]:
    """解析单个表格：单元格内容 + 合并单元格范围 + 表头行数。

    依赖 _build_tc_grid 保持所有 _tc 引用存活，此时 id(_tc) 稳定可靠：
    合并单元格的多个 (r,c) 拥有相同 id(_tc)，非合并的各不相同。
    """
    num_rows = len(table.rows)
    num_cols = len(table.columns) if num_rows else 0
    grid = _build_tc_grid(table, num_rows, num_cols)
    header_rows = _detect_header_rows(grid, num_rows, num_cols)

    cells: list[dict[str, Any]] = []
    # id(tc) → 该合并块的边界信息
    ranges: dict[int, dict[str, Any]] = {}

    for r in range(num_rows):
        for c in range(num_cols):
            info = grid[r][c]
            tc_id = id(info["tc"])
            text = info["text"]
            if tc_id not in ranges:
                # 首次见到这个 _tc（合并块的左上角）
                ranges[tc_id] = {
                    "min_row": r,
                    "min_col": c,
                    "max_row": r,
                    "max_col": c,
                }
                cells.append(
                    {
                        "row": r,
                        "col": c,
                        "text": text,
                        "merged": False,  # 是否被合并（>1 格）
                        "_tc_id": tc_id,  # 内部字段，输出前清理
                    }
                )
            else:
                # 同一个 _tc 的其它位置：扩展合并范围
                ranges[tc_id]["max_row"] = max(ranges[tc_id]["max_row"], r)
                ranges[tc_id]["max_col"] = max(ranges[tc_id]["max_col"], c)

    # 标记被合并的单元格，整理合并范围
    merged_ranges: list[dict[str, Any]] = []
    for cell_info in cells:
        rng = ranges[cell_info["_tc_id"]]
        span_rows = rng["max_row"] - rng["min_row"] + 1
        span_cols = rng["max_col"] - rng["min_col"] + 1
        if span_rows > 1 or span_cols > 1:
            cell_info["merged"] = True
            cell_info["rowspan"] = span_rows
            cell_info["colspan"] = span_cols
            merged_ranges.append(rng)
        cell_info.pop("_tc_id", None)  # 清理内部字段，不进输出

    return {
        "index": table_index,
        "rows": num_rows,
        "cols": num_cols,
        "cells": cells,
        "merged_ranges": merged_ranges,
        "header_rows": header_rows,
    }


def _clean_label(text: str) -> str:
    """清理标签文字：去除换行和首尾空白。"""
    return text.replace("\n", "").replace("\r", "").strip()


def _is_vertically_merged(
    grid: list[list[dict[str, Any]]], row: int, col: int
) -> bool:
    """检测单元格是否是纵向合并的延续部分（即上方行同列是同一个 <w:tc>）。

    纵向合并的栏目标题（如「家庭成员情况」跨行 4-10）会在每行都返回相同文字，
    但它本质是「小节标题」而非「逐行标签」，扫描时应跳过。
    """
    return row > 0 and grid[row][col]["tc"] is grid[row - 1][col]["tc"]


def _find_hmerge_origin_text(
    grid: list[list[dict[str, Any]]], row: int, col: int
) -> str:
    """如果 (row, col) 是横向合并的延续格（text 为空），向左找到源头格的文字。

    例：行4 col10-12 合并为「年收入（元）」，col11 的 text 为空，
    本函数向左扫描找到 col10 的「年收入（元）」。
    """
    if grid[row][col]["text"]:
        return ""
    for c in range(col - 1, -1, -1):
        if grid[row][c]["tc"] is grid[row][col]["tc"] and grid[row][c]["text"]:
            return grid[row][c]["text"]
    return ""


def _scan_for_label(
    grid: list[list[dict[str, Any]]], row: int, col: int, num_cols: int
) -> str:
    """向上 + 向左扫描最近的有意义标签文字，作为字段名。

    扫描顺序：
    1. 同行向左（跳过空格、模板文字、纵向合并的小节标题）—— 适用于「标签 | 填写格」同行布局
    2. 同列向上（跳过空格和模板文字；空格时查找横合并源头）—— 适用于表头在上方多行处
    3. 同行 col0（跳过纵向合并）—— 适用于「意见」类栏目
    4. 向上扫 col0（跳过纵向合并）—— 兜底
    """
    # 1. 同行向左（跳过纵向合并的小节标题）
    for c in range(col - 1, -1, -1):
        text = grid[row][c]["text"]
        if not text or _is_fillable_template(text):
            continue
        if _is_vertically_merged(grid, row, c):
            continue  # 纵向合并 → 小节标题，跳过
        return _clean_label(text)
    # 2. 同列向上（空格时查找横合并源头）
    for r in range(row - 1, -1, -1):
        text = grid[r][col]["text"]
        if text and not _is_fillable_template(text):
            return _clean_label(text)
        # 空格 → 可能是横合并的延续格，向左找源头
        hmerge_text = _find_hmerge_origin_text(grid, r, col)
        if hmerge_text and not _is_fillable_template(hmerge_text):
            return _clean_label(hmerge_text)
    # 3. 同行 col0（跳过纵向合并的小节标题）
    if col > 0:
        text = grid[row][0]["text"]
        if text and not _is_fillable_template(text):
            if not _is_vertically_merged(grid, row, 0):
                return _clean_label(text)
    # 4. 向上扫 col0（跳过纵向合并）
    for r in range(row - 1, -1, -1):
        text = grid[r][0]["text"]
        if text and not _is_fillable_template(text):
            if not _is_vertically_merged(grid, r, 0):
                return _clean_label(text)
    return ""


def _extract_fields_from_tables(
    tables: list[Table],
) -> list[dict[str, Any]]:
    """识别可填写位置：空单元格 + 模板填空栏 → WordCellLocator。

    可填写判定：
    - 单元格为空 → 可填写
    - 单元格含模板提示文字（日期/地址/盖章等）→ 可填写
    - 单元格是纯标签文字 → 不可填写（跳过）

    字段名用 _scan_for_label 向上向左扫描最近标签，消除(未知)。
    """
    fields: list[dict[str, Any]] = []
    for t_idx, table in enumerate(tables):
        num_rows = len(table.rows)
        num_cols = len(table.columns) if num_rows else 0
        grid = _build_tc_grid(table, num_rows, num_cols)  # 保持 _tc 引用存活
        seen_tcs: set[int] = set()  # 已处理过的 _tc 元素 id
        for r in range(num_rows):
            for c in range(num_cols):
                info = grid[r][c]
                tc_id = id(info["tc"])
                # 只在每个合并块的左上角处理一次
                if tc_id in seen_tcs:
                    continue
                seen_tcs.add(tc_id)
                text = info["text"]
                # 纵向合并的延续格（非左上角）→ 不是独立可填写位，跳过
                if _is_vertically_merged(grid, r, c):
                    continue
                # 空格 → 可填写；模板文字 → 可填写；纯标签 → 跳过
                if text and not _is_fillable_template(text):
                    continue  # 纯标签，不是可填写位
                name = _scan_for_label(grid, r, c, num_cols)
                fill_kind = "template" if text else "empty"
                fields.append(
                    {
                        "id": f"word_t{t_idx}_r{r}_c{c}",
                        "name": name,
                        "fill_kind": fill_kind,
                        "locator": {
                            "kind": "word_cell",
                            "table_index": t_idx,
                            "row": r,
                            "col": c,
                        },
                    }
                )
    return fields


# ---------------------------------------------------------------------------
# Excel(.xlsx) 解析
# ---------------------------------------------------------------------------


def _build_excel_grid(
    ws: Worksheet,
) -> tuple[list[list[dict[str, Any]]], int, int]:
    """构建 0-based 网格：grid[r][c] = {"text": str, "origin": (or, oc) | None}。

    origin 是合并块左上角的 0-based 坐标；非合并格为 None。
    合并块内除左上角外的位置 value 在 openpyxl 中为 None，但 origin 指向源头，
    便于扫描时跳过延续格并向左溯源标签。
    """
    num_rows = ws.max_row or 0
    num_cols = ws.max_column or 0
    # (r0, c0) -> (origin_r0, origin_c0)
    merge_map: dict[tuple[int, int], tuple[int, int]] = {}
    for mr in ws.merged_cells.ranges:
        for r in range(mr.min_row, mr.max_row + 1):
            for c in range(mr.min_col, mr.max_col + 1):
                merge_map[(r - 1, c - 1)] = (mr.min_row - 1, mr.min_col - 1)

    grid: list[list[dict[str, Any]]] = []
    for r in range(num_rows):
        row: list[dict[str, Any]] = []
        for c in range(num_cols):
            val = ws.cell(row=r + 1, column=c + 1).value
            text = "" if val is None else str(val).strip()
            row.append({"text": text, "origin": merge_map.get((r, c))})
        grid.append(row)
    return grid, num_rows, num_cols


def _try_int(text: str) -> int | None:
    """把单元格文本解析为正整数；非纯数字返回 None。"""
    if not text:
        return None
    t = text.strip()
    if not re.fullmatch(r"\d+", t):
        return None
    try:
        return int(t)
    except ValueError:
        return None


def _detect_serial_columns(
    grid: list[list[dict[str, Any]]], num_rows: int, num_cols: int
) -> set[int]:
    """识别纯数字逐行递增的序号列（返回 0-based 列号集合）。

    判定：一列中存在连续 >= 3 个单元格为纯数字且逐行 +1（如 1,2,3 或 5,6,7）。
    序号列的单元格不是字段标签，扫描字段名时应跳过，改由列头向上继承，
    避免把「1/2/3」误当作字段名。
    """
    min_run = 3
    serial_cols: set[int] = set()
    for c in range(num_cols):
        longest = 0
        cur = 0
        prev: int | None = None
        for r in range(num_rows):
            num = _try_int(grid[r][c]["text"])
            if num is None:
                cur = 0
                prev = None
                continue
            if prev is not None and num == prev + 1:
                cur += 1
            else:
                cur = 1
            prev = num
            if cur > longest:
                longest = cur
        if longest >= min_run:
            serial_cols.add(c)
    return serial_cols


_EXAMPLE_KEYWORDS = ("示例", "样例", "样张", "样表", "例子")


def _detect_example_rows(
    grid: list[list[dict[str, Any]]], num_rows: int, num_cols: int
) -> set[int]:
    """识别示例数据行（返回 0-based 行号集合）。

    判定（满足任一）：
    A) 该行 col0 文本含示例关键词（「示例/样例/样张/样表/例子」）—— 强信号
    B) 数据行特征（无关键词样板行）：同时满足
       - 数据密集：已填值列数 >= max(2, num_cols//3)
       - 含多个数值数据：纯数字单元格 >= 2（学号/身份证/电话/金额等）
       - 其下连续 >= 2 行为空数据行（已填值 < 上述阈值）

    纯数字阈值是区分示例行与列头行的关键：列头行单元格是文字字段名
    （0 个纯数字），示例行含多个具体数值。避免「数据密集+下方空行」
    弱特征单独使用误判列头行。示例行是填写样板，扫描字段名时跳过，
    继续向上找真正列头。
    """
    example_rows: set[int] = set()
    fill_thresh = max(2, num_cols // 3)
    num_thresh = 2
    min_empty_run = 2
    for r in range(num_rows):
        # A) col0 示例关键词
        head = grid[r][0]["text"].strip() if grid[r][0]["text"] else ""
        if head and any(kw in head for kw in _EXAMPLE_KEYWORDS):
            example_rows.add(r)
            continue
        # B) 数据行特征：数据密集 + 多个纯数字值 + 下方连续空数据行
        filled = 0
        num_count = 0
        for c in range(num_cols):
            t = grid[r][c]["text"]
            if t and not _is_fillable_template(t):
                filled += 1
                if _try_int(t) is not None:
                    num_count += 1
        if filled < fill_thresh or num_count < num_thresh:
            continue
        empty_run = 0
        rr = r + 1
        while rr < num_rows:
            f_rr = sum(
                1
                for c in range(num_cols)
                if grid[rr][c]["text"]
                and not _is_fillable_template(grid[rr][c]["text"])
            )
            if f_rr < fill_thresh:
                empty_run += 1
                rr += 1
            else:
                break
        if empty_run >= min_empty_run:
            example_rows.add(r)
    return example_rows


_NOTE_ROW_KEYWORDS = (
    "填表说明", "填表须知", "填表要求", "注意事项", "注：", "备注：", "说明：",
)


def _is_full_row_note(text: str, colspan: int) -> bool:
    """整行合并的说明/签字行文字（不当填写位）。

    特征：横跨多列合并（colspan >= 3）+ 下列之一：
    - 含说明关键词（填表说明/注意事项等）
    - 指令性长文本
    - 签字/盖章等模板提示（整行合并的签字说明区，非逐格填写位）
    区别于正常填写说明区（单格不合并）和表头标题（非指令性、非说明关键词）。
    """
    if colspan < 3 or not text:
        return False
    if any(kw in text for kw in _NOTE_ROW_KEYWORDS):
        return True
    if _is_instruction_text(text):
        return True
    return _is_fillable_template(text)


def _is_excel_vmerge_continuation(
    grid: list[list[dict[str, Any]]], row: int, col: int
) -> bool:
    """纵向合并的延续格（origin 行 < 当前行）——本质是小节标题的延续，扫描时跳过。"""
    origin = grid[row][col]["origin"]
    return origin is not None and origin[0] < row


def _find_excel_hmerge_origin_text(
    grid: list[list[dict[str, Any]]], row: int, col: int
) -> str:
    """横向合并延续格（text 为空）向左找到源头格的文字。"""
    if grid[row][col]["text"]:
        return ""
    origin = grid[row][col]["origin"]
    if origin is None:
        return ""
    for c in range(col - 1, -1, -1):
        if grid[row][c]["origin"] == origin and grid[row][c]["text"]:
            return grid[row][c]["text"]
    return ""


def _scan_excel_label(
    grid: list[list[dict[str, Any]]],
    row: int,
    col: int,
    num_cols: int,
    serial_cols: set[int],
    example_rows: set[int],
    header_rows: set[int],
) -> str:
    """向上 + 向左扫描最近的有意义标签文字，作为字段名（与 Word 版逻辑对齐）。

    扫描顺序：
    1. 同行向左（仅表头行：横向合并表头延续格向左找源头；数据行的同行值是数据不是列名）
    2. 同列向上：只取表头行列名，跳过数据行（含示例行）的已填值
    3. 同行 col0（跳过纵向合并；col0 是序号列则整步跳过）
    4. 向上扫 col0（跳过纵向合并；col0 是序号列则整步跳过；跳过示例数据行）
    5. 兜底：上方最近的非空行，从当前列向左找列头

    serial_cols 中的列视为序号列：其单元格不是字段标签，扫描时跳过，
    迫使走「同列向上」路径从列头继承字段名。
    example_rows 中的行视为示例数据行：兜底扫描（步骤4/5）时跳过。
    header_rows 中的行视为表头行：步骤1/2 只从表头行取列名，
    避免数据行的已填值/示例值（如「先进制造」）被误当字段名。
    """
    # 1. 同行向左（仅表头行：横向合并表头延续格向左找源头）
    if row in header_rows:
        for c in range(col - 1, -1, -1):
            if c in serial_cols:
                continue
            text = grid[row][c]["text"]
            if not text or _is_fillable_template(text):
                continue
            if _is_excel_vmerge_continuation(grid, row, c):
                continue
            return _clean_label(text)
    # 2. 同列向上：只取表头行列名，跳过数据行与示例行的已填值
    for r in range(row - 1, -1, -1):
        if r not in header_rows or r in example_rows:
            continue  # 数据行/示例行的值是已填数据/样板值，不是列名
        text = grid[r][col]["text"]
        if col in serial_cols and _try_int(text) is not None:
            continue  # 序号列的数字不是字段名
        if text and not _is_fillable_template(text):
            return _clean_label(text)
        htext = _find_excel_hmerge_origin_text(grid, r, col)
        if htext and not _is_fillable_template(htext):
            return _clean_label(htext)
    # 3. 同行 col0（序号列则跳过）
    if col > 0 and 0 not in serial_cols:
        text = grid[row][0]["text"]
        if text and not _is_fillable_template(text):
            if not _is_excel_vmerge_continuation(grid, row, 0):
                return _clean_label(text)
    # 4. 兜底：上方最近的表头行，从当前列向左找列头
    #    覆盖「该列无列头但紧邻列有列头」的列尾空列（如备注列延伸的空列）
    #    优先于 col0 小节标题，确保列尾空列继承紧邻列头
    for r in range(row - 1, -1, -1):
        if r not in header_rows or r in example_rows:
            continue  # 只从表头行找列头，避免数据行值污染
        row_has_value = any(
            grid[r][cc]["text"] and not _is_fillable_template(grid[r][cc]["text"])
            for cc in range(num_cols)
        )
        if not row_has_value:
            continue
        for c in range(col - 1, -1, -1):
            if c in serial_cols:
                continue
            text = grid[r][c]["text"]
            if text and not _is_fillable_template(text):
                if not _is_excel_vmerge_continuation(grid, r, c):
                    return _clean_label(text)
        break  # 只在最近一个表头行查找
    # 5. 向上扫 col0（序号列则跳过；跳过示例数据行；最后兜底）
    if 0 not in serial_cols:
        for r in range(row - 1, -1, -1):
            if r in example_rows:
                continue
            text = grid[r][0]["text"]
            if text and not _is_fillable_template(text):
                if not _is_excel_vmerge_continuation(grid, r, 0):
                    return _clean_label(text)
    return ""


def _is_whole_row_merged(
    grid: list[list[dict[str, Any]]], r: int, num_cols: int
) -> bool:
    """整行（或近整行）合并的说明行：首格是合并左上角且合并覆盖≥2/3 列。

    典型场景：表标题行（A1:H1）、签字/盖章行（A2:H2）。
    这类行的单元格虽非空但属于整行说明，既不算表头列名也不算数据填写位。
    合并未必覆盖到末列（如 A1:L1 在 14 列表里只覆盖 12 列），故按覆盖比例判定。
    """
    if num_cols < 3:
        return False
    first = grid[r][0]
    if not first["text"] or first["origin"] != (r, 0):
        return False
    span = sum(1 for c in range(num_cols) if grid[r][c]["origin"] == (r, 0))
    return span >= max(3, num_cols * 2 // 3)


def _detect_excel_header_rows(
    grid: list[list[dict[str, Any]]],
    num_rows: int,
    num_cols: int,
    example_rows: set[int] | None = None,
) -> int:
    """启发式推断表头行数（数据填写行起始的 0-based 行号）。

    - 跳过整行合并说明行（标题/签字）
    - 表头行：有效列标题数 ≥ 半数（即使有少量空白列仍属表头，如表头行末尾的空列）
    - 示例行（example_rows）直接当数据填写行起始（用户规则1：示例值仍属填写位）
    - 数据行：有空白且有效值 < 半数 → 返回该行
    - 无可填写格 → 返回 1（约定首行为表头）
    - 空表 → 返回 0

    可选参数 example_rows：若调用方已算出，直接复用避免重复计算。
    """
    if num_rows == 0:
        return 0
    if example_rows is None:
        example_rows = _detect_example_rows(grid, num_rows, num_cols)
    threshold = max(1, num_cols // 2)
    for r in range(num_rows):
        if _is_whole_row_merged(grid, r, num_cols):
            continue  # 整行合并说明行不算表头也不算数据
        if r in example_rows:
            return r  # 示例数据行（如 col0='示例'）作为数据填写行起始
        value_count = 0
        has_blank = False
        for c in range(num_cols):
            origin = grid[r][c]["origin"]
            if origin is not None and origin != (r, c):
                continue  # 合并延续格跳过
            text = grid[r][c]["text"]
            if not text or _is_fillable_template(text):
                has_blank = True
            else:
                value_count += 1
        # 数据行：有空白且有效列标题不足半数；表头行通常多列有值
        if has_blank and value_count < threshold:
            return r
    return 1


def _detect_select_cols(
    grid: list[list[dict[str, Any]]], header_rows: set[int], num_cols: int
) -> set[int]:
    """识别下拉选择列：表头行某列含「须下拉选择」提示。

    这类列的填写位 field_type 输出 "select"，其余为 "text"。
    """
    select_cols: set[int] = set()
    for c in range(num_cols):
        for r in header_rows:
            text = grid[r][c]["text"]
            if text and "须下拉选择" in text:
                select_cols.add(c)
                break
    return select_cols


def _detect_textarea_cols(
    grid: list[list[dict[str, Any]]], header_rows: set[int], num_cols: int
) -> set[int]:
    """识别长文本备注列：表头行某列含「备注」提示。

    这类列的填写位 field_type 输出 "textarea"，区别于普通信息列的 "text"。
    """
    textarea_cols: set[int] = set()
    for c in range(num_cols):
        for r in header_rows:
            text = grid[r][c]["text"]
            if text and "备注" in text:
                textarea_cols.add(c)
                break
    return textarea_cols


def _detect_logical_merge_groups(
    grid: list[list[dict[str, Any]]],
    header_rows: set[int],
    num_cols: int,
    textarea_cols: set[int],
    select_cols: set[int],
    serial_cols: set[int],
) -> dict[int, int]:
    """识别「主列+紧邻连续空表头子列」的逻辑合并组（业务上视为1个填写格子）。

    业务场景：表头某列含字段名（如「备注」），紧邻右侧连续 N 列在所有
    表头行都是空，业务上视为同一填写格子（物理上未做 merge_cells）。
    返回 {子列: 主列} 映射；主列不在映射里（主列自己输出 1 条），子列在
    字段循环里直接跳过，禁止生成多条记录。

    严格条件防止误判普通孤立空列：
    - 主列必须在 textarea_cols（即表头含「备注」等长文本提示）
    - 主列不在 select_cols/serial_cols
    - 紧邻右侧连续空表头列在所有 header_rows 都是空（任一行有值即停止扩展）
    - 子列不在 select_cols/serial_cols/textarea_cols（子列被其他特殊列占用即停止）
    """
    if not textarea_cols or not header_rows:
        return {}
    sorted_headers = sorted(header_rows)
    child_to_master: dict[int, int] = {}
    for master in sorted(textarea_cols):
        if master in select_cols or master in serial_cols:
            continue
        for child in range(master + 1, num_cols):
            if (
                child in select_cols
                or child in serial_cols
                or child in textarea_cols
            ):
                break  # 子列被其他特殊列占用，停止扩展
            # 子列表头在所有表头行都必须为空，否则视为下一字段列
            if any(grid[r][child]["text"] for r in sorted_headers):
                break
            child_to_master[child] = master
    return child_to_master


def _extract_excel_sheet(
    ws: Worksheet,
    sheet_index: int,
    grid: list[list[dict[str, Any]]],
    num_rows: int,
    num_cols: int,
    *,
    example_rows: set[int] | None = None,
) -> dict[str, Any]:
    """解析单个工作表：单元格内容 + 合并范围 + 表头行数。

    合并块只在左上角输出一次 cell（merged=True，带 rowspan/colspan）。
    可选 example_rows：若已提前算出，传入后 header_rows 识别可复用，
    确保 sheet['header_rows'] 输出与字段识别中使用的 header_end 严格一致。
    """
    cells: list[dict[str, Any]] = []
    merged_ranges: list[dict[str, Any]] = []
    # 合并范围表，用于按 origin 查跨度
    span_by_origin: dict[tuple[int, int], tuple[int, int]] = {}
    for mr in ws.merged_cells.ranges:
        origin = (mr.min_row - 1, mr.min_col - 1)
        span_rows = mr.max_row - mr.min_row + 1
        span_cols = mr.max_col - mr.min_col + 1
        span_by_origin[origin] = (span_rows, span_cols)
        merged_ranges.append(
            {
                "min_row": mr.min_row,
                "min_col": mr.min_col,
                "max_row": mr.max_row,
                "max_col": mr.max_col,
            }
        )

    seen_origins: set[tuple[int, int]] = set()
    for r in range(num_rows):
        for c in range(num_cols):
            origin = grid[r][c]["origin"]
            if origin is not None:
                if origin != (r, c):
                    continue  # 延续格跳过
                if origin in seen_origins:
                    continue
                seen_origins.add(origin)
            text = grid[r][c]["text"]
            merged = False
            rowspan: int | None = None
            colspan: int | None = None
            if origin is not None:
                span_rows, span_cols = span_by_origin.get(origin, (1, 1))
                if span_rows > 1 or span_cols > 1:
                    merged = True
                    rowspan = span_rows
                    colspan = span_cols
            cells.append(
                {
                    "row": r + 1,  # 输出 1-based，符合 ExcelLocator 契约
                    "col": c + 1,
                    "text": text,
                    "merged": merged,
                    "rowspan": rowspan,
                    "colspan": colspan,
                }
            )

    return {
        "index": sheet_index,
        "name": ws.title,
        "rows": num_rows,
        "cols": num_cols,
        "cells": cells,
        "merged_ranges": merged_ranges,
        "header_rows": _detect_excel_header_rows(
            grid, num_rows, num_cols, example_rows=example_rows
        ),
    }


def _extract_fields_from_excel_sheets(
    sheets_info: list[tuple[Worksheet, list[list[dict[str, Any]]], int, int, set[int]]],
) -> list[dict[str, Any]]:
    """识别 Excel 可填写位置：空单元格 + 模板填空栏 → ExcelLocator。

    sheets_info 每个元素为 (ws, grid, num_rows, num_cols, example_rows)，
    example_rows 由调用方预计算并在 sheet 输出和字段识别间共享，
    确保 header_rows / header_end 严格一致且避免重复计算。

    判定规则：
    - 表头行的纯标签（列名）→ 跳过，不当填写位
    - 数据行的空格 → empty 填写位
    - 数据行的有值格（下拉示例/预置默认值，如「先进制造」）→ template 填写位
    - 示例数据行的有值格（用户规则1）→ template 填写位（不整行排除）
    - 整行合并的说明/签字行 → 跳过，不当填写位
    合并块只处理左上角一次；字段名用 _scan_excel_label 只从表头行继承列名，
    避免数据行的已填值污染字段名。序号列、示例数据行、下拉列在扫描前预识别。
    """
    fields: list[dict[str, Any]] = []
    for s_idx, (ws, grid, num_rows, num_cols, example_rows) in enumerate(sheets_info):
        # 跳过全空 sheet（无任何非空单元格，如新建未填的 Sheet2/Sheet3）
        non_empty = sum(
            1 for r in range(num_rows) for c in range(num_cols) if grid[r][c]["text"]
        )
        if non_empty == 0:
            continue
        # origin -> merged_range 字符串（如 "A1:C3"）+ colspan
        range_str_by_origin: dict[tuple[int, int], str] = {}
        colspan_by_origin: dict[tuple[int, int], int] = {}
        for mr in ws.merged_cells.ranges:
            origin = (mr.min_row - 1, mr.min_col - 1)
            range_str_by_origin[origin] = str(mr)
            colspan_by_origin[origin] = mr.max_col - mr.min_col + 1

        # 预识别序号列、表头行、下拉列（example_rows 已由调用方传入复用）
        serial_cols = _detect_serial_columns(grid, num_rows, num_cols)
        header_end = _detect_excel_header_rows(
            grid, num_rows, num_cols, example_rows=example_rows
        )
        # 表头行集合（排除整行合并的标题/签字说明行：它们不是列名来源；
        #               排除示例数据行：示例行的值是预填数据，不是列名）
        header_rows: set[int] = (
            {
                r for r in range(header_end)
                if not _is_whole_row_merged(grid, r, num_cols)
                and r not in example_rows
            }
            if header_end > 0
            else set()
        )
        select_cols = _detect_select_cols(grid, header_rows, num_cols)
        textarea_cols = _detect_textarea_cols(grid, header_rows, num_cols)
        # 逻辑合并组：主列(如「备注」)+紧邻连续空表头子列 → 业务上视为1个填写格子
        # 子列在循环里直接跳过，只在主列输出 1 条记录
        logical_groups = _detect_logical_merge_groups(
            grid, header_rows, num_cols, textarea_cols, select_cols, serial_cols
        )
        # 主列 → 合并组宽度（含主列+所有子列）
        master_to_width: dict[int, int] = {}
        for child, master in logical_groups.items():
            master_to_width[master] = max(
                master_to_width.get(master, 1), child - master + 1
            )

        seen_origins: set[tuple[int, int]] = set()
        for r in range(num_rows):
            for c in range(num_cols):
                # 逻辑合并组的子列直接跳过（只在主列输出 1 条）
                if c in logical_groups:
                    continue
                origin = grid[r][c]["origin"]
                if origin is not None:
                    if origin != (r, c):
                        continue
                    if origin in seen_origins:
                        continue
                    seen_origins.add(origin)
                if _is_excel_vmerge_continuation(grid, r, c):
                    continue
                # 整行合并的说明行（标题/签字）整行不当填写位，含合并外的空格
                if _is_whole_row_merged(grid, r, num_cols):
                    continue
                # 示例数据行（col0='示例'+预填值，如附件3行3/论文统计行3-5）
                # 整行跳过不算填写位（用户规则：示例行仅作填表演示，非真实填写位）
                if r in example_rows:
                    continue
                text = grid[r][c]["text"]
                # 整行合并的说明/签字行不当填写位
                colspan = colspan_by_origin.get(origin, 1) if origin is not None else 1
                if text and _is_full_row_note(text, colspan):
                    continue
                # 表头行的纯标签（列名）跳过
                if text and r in header_rows and not _is_fillable_template(text):
                    continue
                # 非下拉列的数据行有值格当纯标签跳过；
                # 下拉列（select_cols）的预置示例值（如「先进制造」）判 template 填写位
                if (
                    text
                    and r not in header_rows
                    and c not in select_cols
                    and not _is_fillable_template(text)
                ):
                    continue
                name = _scan_excel_label(
                    grid, r, c, num_cols, serial_cols, example_rows, header_rows
                )
                # 下拉列的列名清洗掉「（须下拉选择）」提示，下拉语义由 field_type 表达
                if c in select_cols:
                    name = re.sub(r"[（(]\s*须下拉选择\s*[)）]", "", name).strip()
                fill_kind = "template" if text else "empty"
                if c in select_cols:
                    field_type = "select"
                elif c in textarea_cols or "备注" in name:
                    field_type = "textarea"
                else:
                    field_type = "text"
                merged_range_str = (
                    range_str_by_origin.get(origin) if origin is not None else None
                )
                # 逻辑合并组的主列：构造虚拟合并范围字符串（如 "L2:N2"），
                # 让下游（1.3语义匹配/1.4回填）能感知到这是跨多列的1个填写格子
                if merged_range_str is None and c in master_to_width:
                    width = master_to_width[c]
                    if width > 1:
                        merged_range_str = (
                            f"{get_column_letter(c + 1)}{r + 1}:"
                            f"{get_column_letter(c + width)}{r + 1}"
                        )
                fields.append(
                    {
                        "id": f"xlsx_s{s_idx}_r{r + 1}_c{c + 1}",
                        "name": name,
                        "fill_kind": fill_kind,
                        "field_type": field_type,
                        "locator": {
                            "kind": "excel_cell",
                            "sheet": ws.title,
                            "row": r + 1,
                            "col": c + 1,
                            "merged_range": merged_range_str,
                        },
                    }
                )
    return fields


class FormStructureService(FormStructurePort):
    """1.2 用户任务文档结构解析服务（Word/Excel）。"""

    def parse_structure(self, file_path: str, *, filename: str) -> dict[str, Any]:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        ext = path.suffix.lower()
        if ext == ".docx":
            return self._parse_docx(path, filename)
        if ext == ".xlsx":
            return self._parse_xlsx(path, filename)
        if ext == ".doc":
            raise ValueError(
                "旧版 .doc 格式不支持，请另存为 .docx 后再上传"
            )
        raise ValueError(
            f"1.2 当前支持 Word(.docx) 与 Excel(.xlsx)，收到: {ext}"
        )

    def _parse_docx(self, path: Path, filename: str) -> dict[str, Any]:
        """Word(.docx)：标题 + 段落 + 表格 + 填写位。"""
        doc = Document(str(path))

        headings = _extract_headings(doc)
        paragraphs = _extract_paragraphs(doc)
        tables_raw = list(doc.tables)
        tables = [_extract_table(t, i) for i, t in enumerate(tables_raw)]
        fields = _extract_fields_from_tables(tables_raw)

        notes: list[str] = []
        if not headings:
            notes.append("未检测到标题段落（可能使用了自定义样式）")
        if not tables_raw:
            notes.append("文档无表格，无可填写位置")
        else:
            notes.append(f"共解析 {len(tables_raw)} 个表格，识别 {len(fields)} 个可填写位置")

        result = {
            "format": "docx",
            "filename": filename,
            "title": headings[0]["text"] if headings else path.stem,
            "headings": headings,
            "paragraphs": paragraphs,
            "tables": tables,
            "sheets": [],
            "fields": fields,
            "structure_notes": notes,
        }
        # 契约校验：实现与 FormStructureResult 契约漂移时立即报错
        return FormStructureResult(**result).model_dump()

    def _parse_xlsx(self, path: Path, filename: str) -> dict[str, Any]:
        """Excel(.xlsx)：工作表 + 填写位。

        data_only=True 读取公式缓存值；待填表单空单元格为 None。
        每个工作表构建 0-based 网格，记录合并块 origin，复用 Word 的
        _is_fillable_template / _clean_label 判定与标签扫描逻辑。
        """
        wb = load_workbook(str(path), data_only=True)

        sheets_info: list[
            tuple[Worksheet, list[list[dict[str, Any]]], int, int, set[int]]
        ] = []
        sheets: list[dict[str, Any]] = []
        for i, ws in enumerate(wb.worksheets):
            grid, num_rows, num_cols = _build_excel_grid(ws)
            # 跳过全空 sheet（如新建未填的 Sheet2/Sheet3）：不纳入结构、不解析填写位
            non_empty = sum(
                1 for r in range(num_rows) for c in range(num_cols) if grid[r][c]["text"]
            )
            if non_empty == 0:
                continue
            # 每个 sheet 预计算一次 example_rows，sheet 输出和字段识别复用同一份，
            # 确保 header_rows / header_end 严格一致且避免重复计算
            example_rows = _detect_example_rows(grid, num_rows, num_cols)
            sheets_info.append((ws, grid, num_rows, num_cols, example_rows))
            sheets.append(
                _extract_excel_sheet(
                    ws, len(sheets), grid, num_rows, num_cols,
                    example_rows=example_rows,
                )
            )

        fields = _extract_fields_from_excel_sheets(sheets_info)

        notes: list[str] = []
        if not sheets:
            notes.append("工作簿无工作表")
        else:
            notes.append(
                f"共解析 {len(sheets)} 个工作表，识别 {len(fields)} 个可填写位置"
            )

        title = wb.sheetnames[0] if wb.sheetnames else path.stem
        result = {
            "format": "xlsx",
            "filename": filename,
            "title": title,
            "headings": [],
            "paragraphs": [],
            "tables": [],
            "sheets": sheets,
            "fields": fields,
            "structure_notes": notes,
        }
        # 契约校验：实现与 FormStructureResult 契约漂移时立即报错
        return FormStructureResult(**result).model_dump()


def get_form_structure_service() -> FormStructurePort:
    return FormStructureService()
