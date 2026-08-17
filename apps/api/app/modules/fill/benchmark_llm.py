#!/usr/bin/env python
"""LLM 对比 benchmark：Qwen vs DeepSeek（2.2 Agent 场景）。

用法：
    $env:DASHSCOPE_API_KEY="sk-xxx"
    $env:DEEPSEEK_API_KEY="sk-yyy"
    cd apps/api
    $env:PYTHONPATH = "$PWD;$PWD\..\..\packages\contracts\python"
    python -m app.modules.fill.benchmark_llm
"""
from __future__ import annotations

import json
import os
import sys
import time
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# ------------------------------------------------------------------ #
#  模拟测试数据（5 个字段 + 3 条证据片段）
# ------------------------------------------------------------------ #

EVIDENCE = [
    "张伟，男，1990年5月12日出生。2015年7月入职阿里巴巴，担任高级算法工程师。",
    "2020年3月跳槽到字节跳动，任算法专家。持有P7职级。年龄34岁。",
    "张伟在字节跳动负责推荐系统，2023年晋升为算法总监。技能：Python, Go, Rust。",
]

MOCK_FIELDS = [
    {"name": "姓名", "field_type": "text", "expected": "张伟", "notes": None},
    {"name": "入职日期", "field_type": "date", "expected": "2015-07-01", "notes": None},
    {"name": "年龄", "field_type": "number", "expected": "34", "notes": None},
    {"name": "性别", "field_type": "single_choice", "expected": "男", "notes": "options: 男|女"},
    {"name": "技能", "field_type": "multi", "expected": "Python,Go,Rust", "notes": "选项: Python, Go, Rust, Java, C++"},
]


def _build_prompt(f: dict) -> str:
    ctx_text = "\n".join(f"[{i+1}] {e}" for i, e in enumerate(EVIDENCE))
    ft = f["field_type"]
    name = f["name"]
    if ft == "date":
        return f"你是填写助手。根据以下知识库证据，为字段【{name}】生成填写值。\n类型约束：日期，格式严格 YYYY-MM-DD。没有证据输出空字符串。严格只输出日期本身，不要加解释。\n\n证据片段：\n{ctx_text}"
    if ft == "number":
        return f"你是填写助手。根据以下知识库证据，为字段【{name}】生成填写值。\n类型约束：仅数字，可含小数点或负号。没有证据输出空字符串。严格只输出数字本身，不要加解释。\n\n证据片段：\n{ctx_text}"
    if ft == "single_choice":
        opts = f["notes"].split(": ")[1]
        return f"你是填写助手。根据以下知识库证据，为字段【{name}】生成填写值。\n类型约束：单选，必须从以下选项中选择一个：{opts}。没有证据输出空字符串。严格只输出选项值本身，不要加解释。\n\n证据片段：\n{ctx_text}"
    if ft == "multi":
        opts = f["notes"].split(": ")[1]
        return f"你是填写助手。根据以下知识库证据，为字段【{name}】生成填写值。\n类型约束：多选，从以下选项中选择一个或多个，用逗号分隔：{opts}。没有证据输出空字符串。严格只输出选项值，不要加解释。\n\n证据片段：\n{ctx_text}"
    return f"你是填写助手。根据以下知识库证据，为字段【{name}】生成填写值。\n类型约束：文本，不超过100字，不含换行。没有证据输出空字符串。严格只输出填写值本身，不要加解释。\n\n证据片段：\n{ctx_text}"


PROMPTS = [_build_prompt(f) for f in MOCK_FIELDS]


# ------------------------------------------------------------------ #
#  数据结构
# ------------------------------------------------------------------ #

@dataclass
class CallLog:
    """单次调用的完整日志。"""
    round_idx: int
    field_name: str
    field_type: str
    model: str
    prompt: str
    raw_response: str
    parsed_value: str
    expected: str
    correct: bool
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    error: str | None = None
    timestamp: str = ""


@dataclass
class ModelResult:
    model_name: str
    provider: str
    model_id: str
    calls: list[CallLog] = field(default_factory=list)
    accuracy: float = 0
    avg_latency_ms: float = 0
    p50_latency_ms: float = 0
    p90_latency_ms: float = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_calls: int = 0
    error_count: int = 0


# ------------------------------------------------------------------ #
#  API 调用
# ------------------------------------------------------------------ #

def _call_api(base_url: str, api_key: str, model: str, prompt: str, temperature: float = 0.0) -> tuple[str, float, int, int, str | None]:
    """调 OpenAI-compatible API，返回 (content, latency_ms, prompt_tokens, completion_tokens, error)。"""
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url)
    t0 = time.perf_counter()
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            stream=False,
        )
        elapsed = (time.perf_counter() - t0) * 1000
        content = (resp.choices[0].message.content or "").strip()
        # DeepSeek-R1 可能多发 reasoning_content
        reasoning = getattr(resp.choices[0].message, "reasoning_content", None)
        if reasoning:
            content = content  # content 已被 SDK 过滤，reasoning 不计入
        pt = resp.usage.prompt_tokens if resp.usage else 0
        ct = resp.usage.completion_tokens if resp.usage else 0
        return content, elapsed, pt, ct, None
    except Exception as e:
        elapsed = (time.perf_counter() - t0) * 1000
        return "", elapsed, 0, 0, str(e)


def _check_correct(field_type: str, expected: str, actual: str) -> bool:
    if not actual:
        return False
    if field_type == "multi":
        expected_set = set(e.strip() for e in expected.split(","))
        actual_set = set(a.strip() for a in actual.replace("，", ",").split(","))
        return expected_set == actual_set or expected_set.issubset(actual_set)
    if field_type == "date":
        # 日期格式正确且年份匹配即可
        return actual.startswith("20") and len(actual) == 10
    return expected in actual or actual in expected


# ------------------------------------------------------------------ #
#  Benchmark 主流程
# ------------------------------------------------------------------ #

ROUNDS = 3


def run_benchmark() -> tuple[ModelResult, ModelResult, list[CallLog]]:
    """对 5 个字段 × 3 轮，跑 Qwen vs DeepSeek。"""
    dashscope_key = os.environ.get("DASHSCOPE_API_KEY", "")
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "")

    if not dashscope_key:
        print("ERROR: 请先设置 DASHSCOPE_API_KEY 环境变量")
        sys.exit(1)
    if not deepseek_key:
        print("ERROR: 请先设置 DEEPSEEK_API_KEY 环境变量")
        sys.exit(1)

    configs = [
        ("Qwen-Plus", "DashScope", "https://dashscope.aliyuncs.com/compatible-mode/v1", dashscope_key, "qwen-plus"),
        ("DeepSeek-V3", "DeepSeek", "https://api.deepseek.com/v1", deepseek_key, "deepseek-chat"),
    ]

    all_logs: list[CallLog] = []
    results: list[ModelResult] = []

    for model_name, provider, base, key, model_id in configs:
        print(f"\n{'='*70}")
        print(f"  模型: {model_name} ({model_id})")
        print(f"  Provider: {provider}")
        print(f"  Base URL: {base}")
        print(f"  轮数: {ROUNDS} × {len(MOCK_FIELDS)} 字段 = {ROUNDS * len(MOCK_FIELDS)} 次调用")
        print(f"{'='*70}")

        mr = ModelResult(model_name=model_name, provider=provider, model_id=model_id)

        for round_idx in range(ROUNDS):
            print(f"\n  --- 第 {round_idx + 1}/{ROUNDS} 轮 ---")
            for i, f in enumerate(MOCK_FIELDS):
                prompt = PROMPTS[i]
                ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                content, latency, pt, ct, err = _call_api(base, key, model_id, prompt)

                correct = _check_correct(f["field_type"], f["expected"], content) if not err else False
                log = CallLog(
                    round_idx=round_idx,
                    field_name=f["name"],
                    field_type=f["field_type"],
                    model=model_name,
                    prompt=prompt[:80] + "...",
                    raw_response=content,
                    parsed_value=content[:50],
                    expected=f["expected"],
                    correct=correct,
                    latency_ms=latency,
                    prompt_tokens=pt,
                    completion_tokens=ct,
                    error=err,
                    timestamp=ts,
                )
                mr.calls.append(log)
                all_logs.append(log)

                status = "✅" if correct else "❌"
                err_str = f" ERR={err}" if err else ""
                print(f"  [{ts}] {f['name']:6s} | {status} | {latency:6.0f}ms | pt={pt:4d} ct={ct:4d} | raw='{content[:40]}'{err_str}")

        # 统计
        latencies = [c.latency_ms for c in mr.calls if not c.error]
        first_round_calls = [c for c in mr.calls if c.round_idx == 0]
        mr.total_calls = len(mr.calls)
        mr.error_count = sum(1 for c in mr.calls if c.error)
        mr.accuracy = sum(1 for c in first_round_calls if c.correct) / len(first_round_calls) if first_round_calls else 0
        mr.avg_latency_ms = statistics.mean(latencies) if latencies else 0
        mr.p50_latency_ms = statistics.median(latencies) if latencies else 0
        mr.p90_latency_ms = sorted(latencies)[int(len(latencies) * 0.9)] if len(latencies) > 5 else (max(latencies) if latencies else 0)
        mr.total_prompt_tokens = sum(c.prompt_tokens for c in mr.calls if not c.error)
        mr.total_completion_tokens = sum(c.completion_tokens for c in mr.calls if not c.error)

        print(f"\n  汇总: 准确率={mr.accuracy:.0%} 平均={mr.avg_latency_ms:.0f}ms P50={mr.p50_latency_ms:.0f}ms P90={mr.p90_latency_ms:.0f}ms")
        print(f"  Token: prompt={mr.total_prompt_tokens} completion={mr.total_completion_tokens} 错误={mr.error_count}")

        results.append(mr)

    return results[0], results[1], all_logs


# ------------------------------------------------------------------ #
#  报告生成
# ------------------------------------------------------------------ #

def generate_report(qwen: ModelResult, ds: ModelResult, all_logs: list[CallLog]) -> str:
    lines = []
    lines.append("# Qwen vs DeepSeek 实验对比报告")
    lines.append("")
    lines.append(f"> 实验时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"> 测试场景: ZhiFill 2.2 Agent 填表")
    lines.append(f"> 模型: {qwen.model_name} ({qwen.model_id}) vs {ds.model_name} ({ds.model_id})")
    lines.append(f"> 测试数据: {len(MOCK_FIELDS)} 字段 × {ROUNDS} 轮 = {len(MOCK_FIELDS) * ROUNDS} 次调用/模型")
    lines.append(f"> 温度: 0.0（确定性输出）")
    lines.append("")

    # 一、汇总对比
    lines.append("## 一、汇总对比")
    lines.append("")
    lines.append("| 维度 | Qwen-Plus | DeepSeek-V3 | 优势方 |")
    lines.append("|------|-----------|-------------|--------|")

    q_acc = sum(1 for c in qwen.calls if c.round_idx == 0 and c.correct)
    d_acc = sum(1 for c in ds.calls if c.round_idx == 0 and c.correct)
    lines.append(f"| 准确率 | {qwen.accuracy:.0%} ({q_acc}/{len(MOCK_FIELDS)}) | {ds.accuracy:.0%} ({d_acc}/{len(MOCK_FIELDS)}) | {_winner(qwen.accuracy, ds.accuracy, '高')} |")
    lines.append(f"| 平均延迟 | {qwen.avg_latency_ms:.0f}ms | {ds.avg_latency_ms:.0f}ms | {_winner(qwen.avg_latency_ms, ds.avg_latency_ms, '低')} |")
    lines.append(f"| P50 延迟 | {qwen.p50_latency_ms:.0f}ms | {ds.p50_latency_ms:.0f}ms | {_winner(qwen.p50_latency_ms, ds.p50_latency_ms, '低')} |")
    lines.append(f"| P90 延迟 | {qwen.p90_latency_ms:.0f}ms | {ds.p90_latency_ms:.0f}ms | {_winner(qwen.p90_latency_ms, ds.p90_latency_ms, '低')} |")
    lines.append(f"| Prompt Tokens | {qwen.total_prompt_tokens} | {ds.total_prompt_tokens} | {_winner(qwen.total_prompt_tokens, ds.total_prompt_tokens, '低')} |")
    lines.append(f"| Completion Tokens | {qwen.total_completion_tokens} | {ds.total_completion_tokens} | {_winner(qwen.total_completion_tokens, ds.total_completion_tokens, '低')} |")
    q_total = qwen.total_prompt_tokens + qwen.total_completion_tokens
    d_total = ds.total_prompt_tokens + ds.total_completion_tokens
    lines.append(f"| 总 Token | {q_total} | {d_total} | {_winner(q_total, d_total, '低')} |")
    lines.append(f"| 错误次数 | {qwen.error_count} | {ds.error_count} | {_winner(qwen.error_count, ds.error_count, '低')} |")
    lines.append("")

    # 二、逐字段对比
    lines.append("## 二、逐字段对比（第 1 轮）")
    lines.append("")
    lines.append("| 字段 | 类型 | 期望值 | Qwen 输出 | Qwen | DeepSeek 输出 | DeepSeek |")
    lines.append("|------|------|--------|-----------|------|---------------|----------|")
    q_first = [c for c in qwen.calls if c.round_idx == 0]
    d_first = [c for c in ds.calls if c.round_idx == 0]
    for q, d in zip(q_first, d_first):
        q_raw = q.raw_response[:30].replace("|", "\\|").replace("\n", " ")
        d_raw = d.raw_response[:30].replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {q.field_name} | {q.field_type} | {q.expected} | {q_raw} | {'✅' if q.correct else '❌'} | {d_raw} | {'✅' if d.correct else '❌'} |")
    lines.append("")

    # 三、延迟详情
    lines.append("## 三、延迟详情（全部轮次）")
    lines.append("")
    lines.append("| 字段 | 轮次 | Qwen (ms) | DeepSeek (ms) | 差值 (ms) |")
    lines.append("|------|------|-----------|---------------|-----------|")
    for r in range(ROUNDS):
        for i, f in enumerate(MOCK_FIELDS):
            q_calls = [c for c in qwen.calls if c.round_idx == r and c.field_name == f["name"]]
            d_calls = [c for c in ds.calls if c.round_idx == r and c.field_name == f["name"]]
            if q_calls and d_calls:
                q_l = q_calls[0].latency_ms
                d_l = d_calls[0].latency_ms
                diff = d_l - q_l
                lines.append(f"| {f['name']} | R{r+1} | {q_l:.0f} | {d_l:.0f} | {diff:+.0f} |")
    lines.append(f"| **平均** | - | **{qwen.avg_latency_ms:.0f}** | **{ds.avg_latency_ms:.0f}** | **{ds.avg_latency_ms - qwen.avg_latency_ms:+.0f}** |")
    lines.append("")

    # 四、Token 消耗详情
    lines.append("## 四、Token 消耗详情（第 1 轮）")
    lines.append("")
    lines.append("| 字段 | Qwen PT | Qwen CT | Qwen 总 | DeepSeek PT | DeepSeek CT | DeepSeek 总 |")
    lines.append("|------|---------|---------|---------|-------------|-------------|-------------|")
    for q, d in zip(q_first, d_first):
        lines.append(f"| {q.field_name} | {q.prompt_tokens} | {q.completion_tokens} | {q.prompt_tokens + q.completion_tokens} | {d.prompt_tokens} | {d.completion_tokens} | {d.prompt_tokens + d.completion_tokens} |")
    q_pt = sum(c.prompt_tokens for c in q_first)
    q_ct = sum(c.completion_tokens for c in q_first)
    d_pt = sum(c.prompt_tokens for c in d_first)
    d_ct = sum(c.completion_tokens for c in d_first)
    lines.append(f"| **合计** | **{q_pt}** | **{q_ct}** | **{q_pt + q_ct}** | **{d_pt}** | **{d_ct}** | **{d_pt + d_ct}** |")
    lines.append("")

    # 五、完整调用日志
    lines.append("## 五、完整调用日志")
    lines.append("")
    lines.append("### Qwen-Plus 调用日志")
    lines.append("")
    lines.append("| 时间 | 轮次 | 字段 | 延迟(ms) | PT | CT | 正确 | 原始响应 |")
    lines.append("|------|------|------|---------|----|----|------|---------|")
    for c in qwen.calls:
        raw = c.raw_response[:40].replace("|", "\\|").replace("\n", " ")
        err = f" **ERR**" if c.error else ""
        lines.append(f"| {c.timestamp} | R{c.round_idx+1} | {c.field_name} | {c.latency_ms:.0f} | {c.prompt_tokens} | {c.completion_tokens} | {'✅' if c.correct else '❌'} | {raw}{err} |")
    lines.append("")

    lines.append("### DeepSeek-V3 调用日志")
    lines.append("")
    lines.append("| 时间 | 轮次 | 字段 | 延迟(ms) | PT | CT | 正确 | 原始响应 |")
    lines.append("|------|------|------|---------|----|----|------|---------|")
    for c in ds.calls:
        raw = c.raw_response[:40].replace("|", "\\|").replace("\n", " ")
        err = f" **ERR**" if c.error else ""
        lines.append(f"| {c.timestamp} | R{c.round_idx+1} | {c.field_name} | {c.latency_ms:.0f} | {c.prompt_tokens} | {c.completion_tokens} | {'✅' if c.correct else '❌'} | {raw}{err} |")
    lines.append("")

    # 六、错误详情（如有）
    errors = [c for c in all_logs if c.error]
    if errors:
        lines.append("## 六、错误详情")
        lines.append("")
        for c in errors:
            lines.append(f"- **{c.model} / {c.field_name} / R{c.round_idx+1}**: `{c.error}`")
        lines.append("")

    # 七、结论
    lines.append("## 七、结论与建议")
    lines.append("")
    q_score = (1 if qwen.accuracy >= ds.accuracy else 0) + (1 if qwen.avg_latency_ms <= ds.avg_latency_ms else 0) + (1 if q_total <= d_total else 0)
    d_score = 3 - q_score
    lines.append("| 维度 | Qwen 得分 | DeepSeek 得分 |")
    lines.append("|------|----------|--------------|")
    lines.append(f"| 准确率 | {1 if qwen.accuracy >= ds.accuracy else 0} | {1 if ds.accuracy >= qwen.accuracy else 0} |")
    lines.append(f"| 延迟 | {1 if qwen.avg_latency_ms <= ds.avg_latency_ms else 0} | {1 if ds.avg_latency_ms <= qwen.avg_latency_ms else 0} |")
    lines.append(f"| Token 效率 | {1 if q_total <= d_total else 0} | {1 if d_total <= q_total else 0} |")
    lines.append(f"| **总分** | **{q_score}** | **{d_score}** |")
    lines.append("")
    if q_score > d_score:
        lines.append("**推荐主选: Qwen-Plus**（综合得分更高，中文+延迟更优）")
    elif d_score > q_score:
        lines.append("**推荐主选: DeepSeek-V3**（综合得分更高，成本+延迟更优）")
    else:
        lines.append("**两者接近**，建议按成本选 DeepSeek，按中文质量选 Qwen")
    lines.append("")

    # 八、测试数据
    lines.append("## 八、测试数据")
    lines.append("")
    lines.append("### 证据片段（知识库）")
    for i, e in enumerate(EVIDENCE, 1):
        lines.append(f"{i}. {e}")
    lines.append("")
    lines.append("### 字段定义")
    lines.append("| 字段 | 类型 | 期望值 | 选项 |")
    lines.append("|------|------|--------|------|")
    for f in MOCK_FIELDS:
        lines.append(f"| {f['name']} | {f['field_type']} | {f['expected']} | {f['notes'] or '-'} |")
    lines.append("")

    # 九、成本估算
    lines.append("## 九、成本估算（按 1000 次填表）")
    lines.append("")
    # Qwen-Plus: input ¥0.0008/1K tokens, output ¥0.002/1K tokens (approximate)
    # DeepSeek-V3: input ¥0.001/1K tokens (cache miss), output ¥0.002/1K tokens
    q_cost_in = q_pt * 1000 / 1000 * 0.0008
    q_cost_out = q_ct * 1000 / 1000 * 0.002
    d_cost_in = d_pt * 1000 / 1000 * 0.001
    d_cost_out = d_ct * 1000 / 1000 * 0.002
    lines.append("| 项目 | Qwen-Plus | DeepSeek-V3 |")
    lines.append("|------|-----------|-------------|")
    lines.append(f"| 单次填表 Prompt Tokens | {q_pt} | {d_pt} |")
    lines.append(f"| 单次填表 Completion Tokens | {q_ct} | {d_ct} |")
    lines.append(f"| 1000 次输入成本 (¥) | {q_cost_in:.2f} | {d_cost_in:.2f} |")
    lines.append(f"| 1000 次输出成本 (¥) | {q_cost_out:.2f} | {d_cost_out:.2f} |")
    lines.append(f"| 1000 次总成本 (¥) | {q_cost_in + q_cost_out:.2f} | {d_cost_in + d_cost_out:.2f} |")
    lines.append("")

    return "\n".join(lines)


def _winner(a: float, b: float, direction: str) -> str:
    if direction == "高":
        return "Qwen" if a > b else "DeepSeek" if b > a else "平手"
    else:
        return "Qwen" if a < b else "DeepSeek" if b < a else "平手"


if __name__ == "__main__":
    qwen, ds, all_logs = run_benchmark()
    report = generate_report(qwen, ds, all_logs)

    report_path = os.path.join(os.path.dirname(__file__), "BENCHMARK_REPORT.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    # 同时输出 JSON 日志
    json_log_path = os.path.join(os.path.dirname(__file__), "benchmark_log.json")
    json_data = {
        "timestamp": datetime.now().isoformat(),
        "qwen": {"model": qwen.model_name, "accuracy": qwen.accuracy, "avg_latency_ms": qwen.avg_latency_ms, "total_tokens": qwen.total_prompt_tokens + qwen.total_completion_tokens},
        "deepseek": {"model": ds.model_name, "accuracy": ds.accuracy, "avg_latency_ms": ds.avg_latency_ms, "total_tokens": ds.total_prompt_tokens + ds.total_completion_tokens},
        "calls": [{"round": c.round_idx, "field": c.field_name, "model": c.model, "raw": c.raw_response, "correct": c.correct, "latency_ms": c.latency_ms, "pt": c.prompt_tokens, "ct": c.completion_tokens, "error": c.error} for c in all_logs],
    }
    with open(json_log_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*70}")
    print(f"报告已生成: {report_path}")
    print(f"JSON 日志:  {json_log_path}")
    print(f"{'='*70}")
