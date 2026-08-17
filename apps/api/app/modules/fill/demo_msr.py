"""Day 5 MSR 完整流程本地 demo。

构造一个混合请求：
  - 1 个 label_value 单字段（姓名）
  - 1 个 header_row_table 工作经历表（时间/组织/角色 × 2 行）
  - 1 个 header_row_table 证书表（证书名称/发证机构/发证日期 × 1 行）

用 FakeLLMClient 模拟 LLM 返回，用 MockRag 模拟知识图谱检索结果。
"""
from __future__ import annotations

import json
import logging
import sys
import os

# 确保可以 import aff_contracts 和 app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "packages", "contracts", "python"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from aff_contracts import FillFormRequest, FillResult, FormField
from aff_contracts.fill import (
    ExcelLocator,
    FieldStatus,
    FieldType,
    LayoutKind,
)
from aff_contracts.rag import RagContext, RagQueryResult, RagQueryRequest


# ---------- Mock 依赖（与 test_fill_agent.py 一致） ---------- #

class MockRag:
    """内存 mock RagPort，按 query 关键字匹配返回 RagQueryResult。"""

    def __init__(self, results: dict[str, RagQueryResult] | None = None) -> None:
        self.results = results or {}
        self.calls: list[str] = []

    def query(self, req: RagQueryRequest) -> RagQueryResult:
        self.calls.append(req.query)
        for key, r in self.results.items():
            if key in req.query:
                return r
        return RagQueryResult(answer="", contexts=[])

    def upsert(self, *a, **kw):
        raise AssertionError("fill() 不得调用 upsert")

    def delete(self, *a, **kw):
        raise AssertionError("fill() 不得调用 delete")


class FakeLLMClient:
    """按关键字匹配 prompt 返回预设响应。"""

    def __init__(self, response_map: dict[str, str]) -> None:
        self._response_map = response_map
        self.calls: list[str] = []

    def complete(self, prompt: str, *, schema=None, temperature=0.0) -> str:
        self.calls.append(prompt[:80])
        for keyword, resp in self._response_map.items():
            if keyword in prompt:
                return resp
        return ""


# ---------- 构造 mock 数据 ---------- #

def build_demo() -> tuple[FakeLLMClient, MockRag, list[FormField]]:
    """构造 FakeLLM + MockRag + 表单字段。"""

    # --- LLM 响应表（按 prompt 关键字匹配，顺序敏感） ---
    # 1) label_value 单字段路径：姓名
    # 2) MSR 工作经历：分类助手 → 工作经历 / JSON 数组 → 2 行
    # 3) MSR 证书：分类助手 → 证书 / JSON 数组 → 1 行（但 LLM 同一个 prompt，需要区分）
    #
    # 注意：FakeLLMClient 按 dict 插入顺序匹配，第一个命中的就返回。
    # 两个 header_row_table 的「分类助手」prompt 内容不同（headers 不同），
    # 但关键字都是「分类助手」 → 会返回同一条。
    # 这里用更精确的关键字区分：
    #   - "公司" / "组织" → 工作经历分类
    #   - "证书名称" → 证书分类
    # 但 planner 的 prompt 模板把 headers 拼进去，所以可以靠 header 区分。
    #
    # 实际 prompt 示例（build_entity_type_prompt）：
    #   "你是分类助手。根据以下表头信息，判断这张多行表最可能记录的是哪类实体。
    #    表头列名：公司、职位、时间
    #    分组名（如果有）：exp1"
    #
    # 所以关键字用 header 名就能区分两个 MSR 调用。
    # 关键字匹配策略（FakeLLMClient 按 dict 插入顺序，第一个命中即返回）：
    #   headers 经 FieldGrouper 排序后：
    #     工作经历 → ["公司", "时间", "职位"]（字母序）
    #     证书     → ["发证日期", "发证机构", "证书名称"]（字母序）
    #   - Step1 分类助手 prompt 含 "表头列名：公司、时间、职位" / "表头列名：发证日期、发证机构、证书名称"
    #   - Step3 批量生成 prompt 含 "按表头 [公司, 时间, 职位]" / "按表头 [发证日期, 发证机构, 证书名称]"
    # 用各组独有的 header 前缀做关键字区分
    llm = FakeLLMClient({
        # === 单字段：姓名（label_value 路径，build_prompt 模板含【姓名】） ===
        "【姓名】": "张三",

        # === 工作经历 MSR Step1：分类助手 prompt 含「表头列名：公司」 ===
        "表头列名：公司": json.dumps(
            {"entity_type": "工作经历", "query_hint": "工作经历、任职记录"},
            ensure_ascii=False,
        ),
        # === 证书 MSR Step1：分类助手 prompt 含「表头列名：发证日期」（排序后第一个 header） ===
        "表头列名：发证日期": json.dumps(
            {"entity_type": "证书", "query_hint": "职业资格证书"},
            ensure_ascii=False,
        ),

        # === MSR Step3：批量 JSON 数组 ===
        # 工作经历 prompt 含 "按表头 [公司, 时间, 职位]"
        # 证书 prompt 含 "按表头 [发证日期, 发证机构, 证书名称]"
        "按表头 [公司": json.dumps([
            {"时间": "2020-07-01", "公司": "ACME Corp", "职位": "算法工程师"},
            {"时间": "2023-03-15", "公司": "Beta Labs", "职位": "高级算法工程师"},
        ], ensure_ascii=False),
        "按表头 [发证日期": json.dumps([
            {"证书名称": "PMP项目管理认证", "发证机构": "PMI", "发证日期": "2021-05-20"},
        ], ensure_ascii=False),
    })

    # --- RagPort mock：按 entity_type 匹配 ---
    rag = MockRag({
        # 工作经历检索（MSR Step2 的 query 含「工作经历」）
        "工作经历": RagQueryResult(
            answer="",
            contexts=[
                RagContext(
                    content=(
                        "张三的工作经历：2020年7月至2023年2月在 ACME Corp 担任算法工程师，"
                        "负责推荐系统；2023年3月至今在 Beta Labs 任高级算法工程师，负责大模型推理优化。"
                    ),
                    doc_id="resume_work.pdf",
                    score=0.95,
                    entities=["ACME Corp", "Beta Labs", "算法工程师", "高级算法工程师"],
                ),
            ],
        ),
        # 证书检索（MSR Step2 的 query 含「证书」）
        "证书": RagQueryResult(
            answer="",
            contexts=[
                RagContext(
                    content="张三于2021年5月取得 PMI 颁发的 PMP项目管理认证证书，证书编号 PMP-2021-0520。",
                    doc_id="cert_pmp.pdf",
                    score=0.92,
                    entities=["PMP项目管理认证", "PMI", "PMP-2021-0520"],
                ),
            ],
        ),
        # label_value 单字段：姓名
        "姓名": RagQueryResult(
            answer="",
            contexts=[
                RagContext(
                    content="张三，英文名 Bob，2020年入职 ACME Corp 任算法工程师。",
                    doc_id="resume_basic.pdf",
                    score=0.93,
                    entities=["张三", "Bob", "ACME Corp"],
                ),
            ],
        ),
    })

    # --- 表单字段 ---
    fields: list[FormField] = []

    # 1) 单字段：姓名
    fields.append(FormField(
        id="s-name", name="姓名", field_type=FieldType.text,
        layout=LayoutKind.label_value,
        locator=ExcelLocator(sheet="基本信息", row=1, col=1),
    ))

    # 2) 工作经历多行表：3 列 × 2 行
    work_headers = ["时间", "公司", "职位"]
    for row_i in range(2):
        for col_key in work_headers:
            ft = FieldType.date if col_key == "时间" else FieldType.text
            fields.append(FormField(
                id=f"work-r{row_i}-{col_key}",
                name=col_key,
                field_type=ft,
                layout=LayoutKind.header_row_table,
                row_group_id="work_exp",
                row_index=row_i,
                column_key=col_key,
                locator=ExcelLocator(sheet="工作经历", row=4 + row_i, col=work_headers.index(col_key) + 1),
            ))

    # 3) 证书多行表：3 列 × 1 行
    cert_headers = ["证书名称", "发证机构", "发证日期"]
    for col_key in cert_headers:
        ft = FieldType.date if col_key == "发证日期" else FieldType.text
        fields.append(FormField(
            id=f"cert-r0-{col_key}",
            name=col_key,
            field_type=ft,
            layout=LayoutKind.header_row_table,
            row_group_id="cert_exp",
            row_index=0,
            column_key=col_key,
            locator=ExcelLocator(sheet="证书", row=4, col=cert_headers.index(col_key) + 1),
        ))

    return llm, rag, fields


# ---------- 打印辅助 ---------- #

def print_separator(title: str) -> None:
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")


def print_field(f: FormField, indent: str = "  ") -> None:
    src_count = len(f.sources)
    src_preview = f.sources[0].snippet[:50] + "..." if f.sources else "(无)"
    src_doc = f.sources[0].doc_id if f.sources else "-"
    print(f"{indent}- [{f.layout.value}] {f.name} (id={f.id})")
    if f.layout == LayoutKind.header_row_table:
        print(f"{indent}    row_group={f.row_group_id}  row_index={f.row_index}  column_key={f.column_key}")
    print(f"{indent}    value      = {f.value!r}")
    print(f"{indent}    confidence = {f.confidence}")
    print(f"{indent}    status     = {f.status.value}")
    print(f"{indent}    sources    = {src_count} 条 | doc={src_doc} | snippet={src_preview}")


def print_rag_calls(rag: MockRag) -> None:
    print_separator("RagPort 调用记录（仅 query，无 upsert/delete）")
    for i, q in enumerate(rag.calls, 1):
        print(f"  [{i:2d}] {q[:80]}")
    print(f"\n  共 {len(rag.calls)} 次 query 调用")


def print_llm_calls(llm: FakeLLMClient) -> None:
    print_separator("LLM 调用记录")
    for i, p in enumerate(llm.calls, 1):
        print(f"  [{i:2d}] {p[:80]}...")
    print(f"\n  共 {len(llm.calls)} 次 LLM 调用")


# ---------- 主流程 ---------- #

def main() -> None:
    # 开启 DEBUG 日志，看 CSF 三维打分详情
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # 把 stdout 重定向到文件，避免 Windows GBK 终端编码问题
    output_file = os.path.join(os.path.dirname(__file__), "demo_msr_output.txt")
    sys.stdout = open(output_file, "w", encoding="utf-8")

    print_separator("Day 5 MSR 完整流程 Demo")
    print("  场景：一份简历表格，包含")
    print("    1) label_value 单字段：姓名")
    print("    2) header_row_table 工作经历表：时间/公司/职位 × 2 行")
    print("    3) header_row_table 证书表：证书名称/发证机构/发证日期 × 1 行")

    # 构造 mock 数据
    llm, rag, fields = build_demo()

    print_separator("输入：FormField[] (待填写)")
    for f in fields:
        print_field(f)

    # 注入 FakeLLM 到 FillService
    from app.modules.fill.service import FillService
    from aff_contracts.settings import Settings

    settings = Settings(max_table_rows=5)  # 限制最多 5 行
    svc = FillService(settings)
    svc._llm = llm  # 替换为 FakeLLMClient

    # 执行 fill()
    print_separator("执行 FillService.fill() ...")
    req = FillFormRequest(job_id="demo-001", fields=fields)
    res = svc.fill(req, rag)

    # 打印结果
    print_separator(f"输出：FillResult (job_id={res.job_id})")
    print(f"\n  stats: filled={res.stats.filled}  empty={res.stats.empty}  low_confidence={res.stats.low_confidence}")

    print_separator("各字段填写详情")
    # 按布局分组打印
    singles = [f for f in res.fields if f.layout == LayoutKind.label_value]
    work_fields = [f for f in res.fields if f.row_group_id == "work_exp"]
    cert_fields = [f for f in res.fields if f.row_group_id == "cert_exp"]

    if singles:
        print("\n  【单字段 label_value】")
        for f in singles:
            print_field(f)

    if work_fields:
        print("\n  【工作经历多行表 header_row_table】 (row_group_id=work_exp)")
        # 按 row_index 分组
        for ri in sorted({f.row_index for f in work_fields}):
            row_fields = sorted([f for f in work_fields if f.row_index == ri], key=lambda x: x.column_key or "")
            print(f"\n    --- Row {ri} ---")
            for f in row_fields:
                print_field(f, indent="      ")

    if cert_fields:
        print("\n  【证书多行表 header_row_table】 (row_group_id=cert_exp)")
        for ri in sorted({f.row_index for f in cert_fields}):
            row_fields = sorted([f for f in cert_fields if f.row_index == ri], key=lambda x: x.column_key or "")
            print(f"\n    --- Row {ri} ---")
            for f in row_fields:
                print_field(f, indent="      ")

    # 打印 RagPort / LLM 调用记录
    print_rag_calls(rag)
    print_llm_calls(llm)

    # 红线校验
    print_separator("红线校验")
    print(f"  [OK] RagPort.upsert 未被调用（MockRag.upsert 触发即 AssertionError）")
    print(f"  [OK] RagPort.delete 未被调用（MockRag.delete 触发即 AssertionError）")
    print(f"  [OK] max_table_rows = {settings.max_table_rows}（工作经历 2 行未超限，证书 1 行未超限）")

    print_separator("Demo 完成")
    print(f"\n  结果：{res.stats.filled} 个字段已填，{res.stats.empty} 个空，{res.stats.low_confidence} 个低置信度")
    print(f"  填写率：{res.stats.filled}/{len(res.fields)} = {res.stats.filled / len(res.fields) * 100:.0f}%")

    sys.stdout.close()
    sys.stdout = sys.__stdout__
    print(f"Demo 输出已写入: {output_file}")


if __name__ == "__main__":
    main()
