from __future__ import annotations

import functools
import json
import logging
import re
from typing import Any

from aff_contracts.settings import Settings

logger = logging.getLogger("fill.agent.runner")

# ------------------------------------------------------------------ #
#  创新点 2 TAPE：类型感知 Prompt 模板（对齐 summary_language=Chinese）
# ------------------------------------------------------------------ #
TEXT_TMPL = """你是填写助手。根据以下知识库证据，为字段【{name}】生成填写值。
类型约束：文本，不超过100字，不含换行。没有证据输出空字符串。严格只输出填写值本身，不要加解释。

证据片段：
{contexts}
"""

DATE_TMPL = """你是填写助手。根据以下知识库证据，为字段【{name}】生成填写值。
类型约束：日期，格式严格 YYYY-MM-DD。没有证据输出空字符串。严格只输出日期本身，不要加解释。

证据片段：
{contexts}
"""

NUMBER_TMPL = """你是填写助手。根据以下知识库证据，为字段【{name}】生成填写值。
类型约束：仅数字，可含小数点或负号。没有证据输出空字符串。严格只输出数字本身，不要加解释。

证据片段：
{contexts}
"""

SINGLE_CHOICE_TMPL = """你是填写助手。根据以下知识库证据，为字段【{name}】生成填写值。
类型约束：单选，必须从以下选项中选择一个：{options}。没有证据输出空字符串。严格只输出选项值本身，不要加解释。

证据片段：
{contexts}
"""

MULTI_TMPL = """你是填写助手。根据以下知识库证据，为字段【{name}】生成填写值。
类型约束：多选，从以下选项中选择一个或多个，用逗号分隔：{options}。没有证据输出空字符串。严格只输出选项值，不要加解释。

证据片段：
{contexts}
"""

MULTI_ROW_TMPL = """你是填写助手。根据以下知识库证据，按表头 [{headers}] 生成一张 JSON 数组。
每行一个对象，key 必须严格等于表头；最多 {max_rows} 行；没有证据输出 []。只输出 JSON 数组，不要加解释。

证据片段：
{contexts}
"""


def _parse_options(notes: str | None) -> list[str]:
    """从 FormField.notes 解析选项列表。

    支持格式："options: A|B|C" 或 "选项: A, B, C"
    """
    if not notes:
        return []
    m = re.search(r"(?:options|选项)\s*[:：]\s*(.+)", notes)
    if not m:
        return []
    raw = m.group(1)
    parts = re.split(r"[|,，、]", raw)
    return [p.strip() for p in parts if p.strip()]


def _format_contexts(contexts: list) -> str:
    """把 RagContext 列表拼成证据文本。"""
    if not contexts:
        return "（无证据）"
    parts = []
    for i, c in enumerate(contexts, 1):
        snippet = (c.content or "").strip()
        if snippet:
            parts.append(f"[{i}] {snippet}")
    return "\n".join(parts) if parts else "（无证据）"


# 没装 agent extra 时，import 不崩：用 Any 占位，运行时 mock 可过。
try:
    from openai import OpenAI  # type: ignore[import-untyped]
except Exception:  # pragma: no cover
    OpenAI = Any  # type: ignore[assignment,misc]


class LLMClient:
    """Day 3: 统一 OpenAI-compatible SDK 调用封装（Qwen DashScope / Ollama / DeepSeek 皆可）。"""

    def __init__(self, settings: Settings) -> None:
        self.model = settings.query_model or settings.llm_model
        self._provider = settings.llm_provider
        # Ollama 默认起的 base_url 可能是 "http://127.0.0.1:11434"，SDK 需要 /v1
        base = settings.llm_api_base
        if settings.llm_provider == "ollama" and not base.endswith("/v1"):
            base = base.rstrip("/") + "/v1"
        # ollama 场景下 key 无意义但 SDK 要非空
        key = settings.llm_api_key if settings.llm_provider != "ollama" else (settings.llm_api_key or "ollama")
        # OpenAI 类如果仍是 Any（没装依赖），给个可 call 的占位对象，免得单测 mock 前就崩
        if OpenAI is Any:
            self._client: Any = None  # 实际运行由调用方注入 mock；此分支仅兜底
        else:
            self._client = OpenAI(api_key=key or None, base_url=base)

    @staticmethod
    def build_prompt(field, contexts: list, settings: Settings) -> str:
        """创新点 2 TAPE：按 field_type 选模板并注入参数 → 返回完整 prompt。"""
        ft = field.field_type.value
        ctx_text = _format_contexts(contexts)

        if ft == "date":
            return DATE_TMPL.format(name=field.name, contexts=ctx_text)
        if ft == "number":
            return NUMBER_TMPL.format(name=field.name, contexts=ctx_text)
        if ft == "single_choice":
            options = _parse_options(getattr(field, "notes", None))
            opts_str = " | ".join(options) if options else "（未提供选项）"
            return SINGLE_CHOICE_TMPL.format(name=field.name, options=opts_str, contexts=ctx_text)
        if ft == "multi":
            options = _parse_options(getattr(field, "notes", None))
            opts_str = " | ".join(options) if options else "（未提供选项）"
            return MULTI_TMPL.format(name=field.name, options=opts_str, contexts=ctx_text)
        # 默认 text
        return TEXT_TMPL.format(name=field.name, contexts=ctx_text)

    @staticmethod
    def build_multi_row_prompt(headers: list[str], contexts: list, settings: Settings) -> str:
        """多行表专用 prompt（创新点 3 MSR 批量生成）。"""
        ctx_text = _format_contexts(contexts)
        return MULTI_ROW_TMPL.format(
            headers=", ".join(headers),
            max_rows=settings.max_table_rows,
            contexts=ctx_text,
        )

    def complete(
        self,
        prompt: str,
        *,
        schema: dict | None = None,
        temperature: float = 0.0,
    ) -> str:
        """单轮非流式完成。

        schema: Ollama 用 format=<schema> 走 GBNF grammar（token 级 100% 合法 JSON）；
                OpenAI-compatible 用 response_format=json_schema。
        """
        if self._client is None:
            # 未装 openai 依赖或走 mock 分支；由上层 FakeLLMClient 替代
            return ""
        kwargs: dict[str, Any] = dict(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            stream=False,
        )

        # 创新点 2：grammar 约束（不靠提示词约束 JSON，token 级保证合法）
        if schema is not None:
            if self._provider == "ollama":
                kwargs["extra_body"] = {"format": schema}
            else:
                kwargs["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {"name": "fill_result", "schema": schema, "strict": True},
                }

        resp = self._client.chat.completions.create(**kwargs)
        # DeepSeek-R1 会额外发 reasoning_content，SDK 取 content 会自动过滤
        content = (resp.choices[0].message.content or "") if hasattr(resp, "choices") else ""
        return content.strip()


def validate_type(field_type: str, value: str, notes: str | None = None) -> tuple[bool, float]:
    """创新点 2：类型合法度校验。

    返回 (是否通过, 合法度分数 ∈ {0.0, 0.5, 1.0})：
      - 完全通过 → (True, 1.0)
      - 部分通过（文本超长/带换行） → (False, 0.5)
      - 空串或完全非法 → (False, 0.0)
    """
    if value == "":
        return False, 0.0
    if field_type == "date":
        from datetime import datetime
        try:
            datetime.strptime(value, "%Y-%m-%d")
            return True, 1.0
        except ValueError:
            return False, 0.0
    if field_type == "number":
        try:
            float(value)
            return True, 1.0
        except ValueError:
            return False, 0.0
    if field_type == "text":
        ok_len = len(value) <= 100
        ok_line = "\n" not in value
        if ok_len and ok_line:
            return True, 1.0
        # 内容有意义但格式差一点：给半分
        return False, 0.5
    if field_type == "single_choice":
        options = _parse_options(notes)
        if not options:
            # 无选项列表时降级为非空校验
            return True, 1.0
        if value.strip() in options:
            return True, 1.0
        return False, 0.0
    if field_type == "multi":
        options = _parse_options(notes)
        if not options:
            return True, 1.0
        parts = [p.strip() for p in re.split(r"[,，、]", value) if p.strip()]
        if parts and all(p in options for p in parts):
            return True, 1.0
        if parts and any(p in options for p in parts):
            # 部分匹配：给半分
            return False, 0.5
        return False, 0.0
    # other：非空即通过
    return True, 1.0


# ------------------------------------------------------------------ #
#  Day 5: generate_multi_row() — 批量 JSON 生成（MSR 第三步）
# ------------------------------------------------------------------ #

@functools.lru_cache(maxsize=64)
def build_multi_row_schema(headers: tuple[str, ...]) -> dict:
    """根据 headers 构造 JSON 数组的 JSONSchema（每行 key=header）。

    LRU 缓存：同 headers 的 schema 只构建一次（避免重复构造 dict）。
    注意：入参为 tuple（hashable），调用方需 list→tuple 转换。
    """
    item_props = {}
    required = []
    for h in headers:
        # 所有列都用 string 类型，允许 null（无值时）
        item_props[h] = {"type": ["string", "null"]}
        required.append(h)
    return {
        "type": "array",
        "items": {
            "type": "object",
            "properties": item_props,
            "required": required,
            "additionalProperties": False,
        },
    }


class MultiRowResult:
    """批量生成的结构化结果，便于 service 层回写字段。"""

    def __init__(self, rows: list[dict], contexts: list) -> None:
        # rows: [{header: value (or None)}, ...] 已按 max_rows 截断
        self.rows = rows
        self.contexts = contexts

    def __len__(self) -> int:
        return len(self.rows)


def generate_multi_row(
    llm_client,
    headers: list[str],
    contexts: list,
    settings: Settings,
    *,
    entity_type: str | None = None,
    hint: str | None = None,
) -> MultiRowResult:
    """Day 5 MSR 第三步：一次 LLM 调用批量生成多行 JSON 数组。

    - 走 response_format=json_object / Ollama format=JSONSchema（grammar 锁）
    - 按 settings.max_table_rows 截断
    - 解析失败或空数组 → 返回 []
    """
    max_rows = settings.max_table_rows or 50

    # Step 1: 构造带 entity_type/hint 前缀的增强模板
    ctx_text = _format_contexts(contexts)
    prefix_parts = []
    if entity_type and entity_type != "其他":
        prefix_parts.append(f"实体类型：{entity_type}")
    if hint:
        prefix_parts.append(f"检索线索：{hint}")
    prefix = "\n".join(prefix_parts) + "\n\n" if prefix_parts else ""

    enhanced_prompt = (
        prefix
        + MULTI_ROW_TMPL.format(
            headers=", ".join(headers),
            max_rows=max_rows,
            contexts=ctx_text,
        )
    )

    # Step 2: 带 JSONSchema 约束调用 LLM
    schema = build_multi_row_schema(tuple(headers))
    try:
        raw = llm_client.complete(enhanced_prompt, schema=schema, temperature=0.0)
    except Exception as e:  # pragma: no cover
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("generate_multi_row: LLM 异常 → 返回空行: %s", e)
        return MultiRowResult(rows=[], contexts=contexts)

    # Step 3: 解析 JSON → list[dict]
    if not raw:
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("generate_multi_row: LLM 返回空 → 0 行")
        return MultiRowResult(rows=[], contexts=contexts)

    rows: list[dict] = []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            rows = parsed
        elif isinstance(parsed, dict) and "rows" in parsed and isinstance(parsed["rows"], list):
            # 兼容外层包一层 { "rows": [...] } 的写法
            rows = parsed["rows"]
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("generate_multi_row: JSON 解析失败 %r → 0 行", e)
        rows = []

    # 过滤非 dict 行，确保每行都是 dict 且 key 在 headers 内
    cleaned: list[dict] = []
    header_set = set(headers)
    for r in rows:
        if not isinstance(r, dict):
            continue
        # 只保留 headers 里的 key；缺的补 None
        cleaned_row = {h: (r.get(h, None) if r.get(h, None) is None or isinstance(r.get(h), str) else str(r.get(h))) for h in headers}
        cleaned.append(cleaned_row)

    # Step 4: 按 max_table_rows 截断（保险锁，LLM 模板里也提示了）
    if len(cleaned) > max_rows:
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("generate_multi_row: rows=%d 超过 max_rows=%d → 截断", len(cleaned), max_rows)
        cleaned = cleaned[:max_rows]

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("generate_multi_row: headers=%s, entity_type=%r, hint=%r → %d 行（max=%d）",
                     headers, entity_type, hint, len(cleaned), max_rows)

    return MultiRowResult(rows=cleaned, contexts=contexts)
