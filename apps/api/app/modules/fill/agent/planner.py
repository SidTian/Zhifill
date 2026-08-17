from __future__ import annotations

import json
import logging
from dataclasses import dataclass

logger = logging.getLogger("fill.agent.planner")

# CSF 三因子权重 + 阈值（创新点 4：置信度工程合成）
LOW_CONF_THRESHOLD = 0.45  # < 此字段标 low_confidence
EMPTY_THRESHOLD = 0.30     # < 此字段强制置空
ALIGN_RETRY_THRESHOLD = 0.50  # 实体对齐 < 此值触发重试检索
MAX_RETRIES = 1               # 重试上限（避免无限循环 + 控制 RagPort 调用次数）
RETRIEVAL_WEIGHT = 0.40    # RagContext.score 权重
ENTITY_ALIGN_WEIGHT = 0.30  # 创新点 1：实体对齐 Jaccard 权重
TYPE_VALIDITY_WEIGHT = 0.30  # 创新点 2：类型合法度权重


@dataclass
class QueryPlan:
    """一个 group 的检索/生成方案。"""

    group_key: str
    coarse_query: str                           # mix 粗检索
    fine_queries: dict[str, str]                # field.id → local 细检索
    expected_schema: dict                       # JSONSchema 草稿（Day3 Runner 层补）


class QueryPlanner:
    """Day 2: 规划检索 + 打分工具集。"""

    @staticmethod
    def plan(group) -> QueryPlan:
        names = "、".join({f.name for f in group.fields if f.name}) or "未命名字段"
        coarse = f"本人知识库中关于：{names} 的事实。"
        fine = {
            f.id: f"本人的【{f.name}】（类型 {f.field_type.value}）具体取值与来源是什么？"
            for f in group.fields
        }
        return QueryPlan(
            group_key=group.key,
            coarse_query=coarse,
            fine_queries=fine,
            expected_schema={},  # 留到 Runner 层根据 field_type 组装 JSONSchema
        )

    @staticmethod
    def build_retry_query(field) -> str:
        """重试检索 query：比首次细检索更聚焦（加字段类型约束 + 精确取值）。"""
        return f"请精确查找【{field.name}】的{field.field_type.value}类型取值。"

    @staticmethod
    def entity_align_score(value: str, snippet: str, entities: list[str] | None = None) -> float:
        """创新点 1：候选值与证据 snippet 的 Jaccard（token 级）。

        无值/无片段 → 0；entities 可选作为额外词表。
        """
        if not value or not snippet:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("entity_align: value 或 snippet 为空 → 0.0")
            return 0.0
        v_tokens = set(value.replace(" ", ""))
        s_tokens = set(snippet.replace(" ", "")) | set((entities or []))
        inter = v_tokens & s_tokens
        union = v_tokens | s_tokens
        score = len(inter) / len(union) if union else 0.0
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "entity_align: value=%r snippet前30字=%r entities=%r\n"
                "  v_tokens=%s\n  s_tokens=%s\n  交集=%s 并集大小=%d\n"
                "  → align_score=%.4f",
                value[:30], snippet[:30], entities,
                sorted(v_tokens), sorted(s_tokens), sorted(inter), len(union), score,
            )
        return score

    @staticmethod
    def calc_confidence(
        retrieval_score: float | None,
        align_score: float,
        type_validity: float,
    ) -> float:
        """创新点 4：三因子合成 confidence ∈ [0,1]。"""
        r = retrieval_score or 0.0
        r_part = RETRIEVAL_WEIGHT * r
        a_part = ENTITY_ALIGN_WEIGHT * align_score
        t_part = TYPE_VALIDITY_WEIGHT * type_validity
        raw = r_part + a_part + t_part
        final = min(max(raw, 0.0), 1.0)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "calc_confidence:\n"
                "  retrieval:  %.4f × %.2f = %.4f\n"
                "  entity_align: %.4f × %.2f = %.4f\n"
                "  type_validity: %.4f × %.2f = %.4f\n"
                "  合计 raw=%.4f → clamp后=%.4f",
                r, RETRIEVAL_WEIGHT, r_part,
                align_score, ENTITY_ALIGN_WEIGHT, a_part,
                type_validity, TYPE_VALIDITY_WEIGHT, t_part,
                raw, final,
            )
        return final

    # --- Day 5: Multi-row Semantic Router (MSR) --- #

    # 多行表头可能对应的实体类型（工作/教育/项目等）
    _ENTITY_OPTIONS = ["工作经历", "教育经历", "项目经历", "证书", "获奖", "其他"]

    _ENTITY_TYPE_SCHEMA: dict = {
        "type": "object",
        "properties": {
            "entity_type": {
                "type": "string",
                "enum": _ENTITY_OPTIONS,
            },
            "query_hint": {
                "type": "string",
                "description": "检索 hint，用于补充 RagQuery 的查询前缀",
            },
        },
        "required": ["entity_type", "query_hint"],
        "additionalProperties": False,
    }

    _ENTITY_TYPE_PROMPT = """你是分类助手。根据以下表头信息，判断这张多行表最可能记录的是哪类实体。
表头列名：{headers}
分组名（如果有）：{group_name}

请选择一个最合适的类型，并给出检索提示词。
类型选项：{options}

只输出 JSON，不要加任何解释。"""

    @classmethod
    def build_entity_type_prompt(cls, headers: list[str], group_key: str) -> str:
        return cls._ENTITY_TYPE_PROMPT.format(
            headers="、".join(headers) if headers else "（无）",
            group_name=group_key,
            options=" | ".join(cls._ENTITY_OPTIONS),
        )

    @classmethod
    def pre_determine_entity_type(
        cls,
        group,
        llm_client,
    ) -> tuple[str, str]:
        """创新点 3 MSR 第一步：预问 LLM 该多行表的实体类型 + 检索 hint。

        返回 (entity_type, query_hint)。
        LLM 异常 / JSON 解析失败 → fallback: ("其他", headers.join)。
        """
        headers = group.headers or []
        fallback = ("其他", "、".join(headers) if headers else group.key)

        try:
            prompt = cls.build_entity_type_prompt(headers, group.key)
            raw = llm_client.complete(prompt, schema=cls._ENTITY_TYPE_SCHEMA, temperature=0.0)
        except Exception as e:  # pragma: no cover - LLM 异常直接 fallback
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("pre_determine_entity_type: LLM 异常 → fallback %r: %s", fallback, e)
            return fallback

        if not raw:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("pre_determine_entity_type: LLM 返回空 → fallback %r", fallback)
            return fallback

        try:
            data = json.loads(raw)
            et = data.get("entity_type") or "其他"
            qh = data.get("query_hint") or ("、".join(headers) if headers else group.key)
            if et not in cls._ENTITY_OPTIONS:
                et = "其他"
            result = (et, qh)
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("pre_determine_entity_type: group=%s → entity_type=%r, query_hint=%r",
                             group.key, et, qh)
            return result
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("pre_determine_entity_type: JSON 解析失败 %r → fallback %r", e, fallback)
            return fallback

    @staticmethod
    def build_multi_row_query(entity_type: str, hint: str, headers: list[str]) -> str:
        """MSR 第二步：用 entity_type + hint 组装定向 RagQuery。"""
        headers_str = "、".join(headers) if headers else "相关字段"
        if entity_type and entity_type != "其他":
            return f"本人的{entity_type}：{hint}。按列{headers_str}列出详细信息。"
        return f"本人关于 {hint} 的事实，按列 {headers_str}。"
