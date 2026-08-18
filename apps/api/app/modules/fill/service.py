from __future__ import annotations

import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from aff_contracts import FillResult, ParseFormRequest, ParseFormResult
from aff_contracts.common import SourceRef
from aff_contracts.fill import FillFormRequest, FillStats, FieldStatus, LayoutKind
from aff_contracts.settings import Settings

from app.core.errors import NotImplementedModule
from app.modules.fill.agent.grouper import FieldGrouper
from app.modules.fill.agent.planner import (
    ALIGN_RETRY_THRESHOLD as _RETRY,
    EMPTY_THRESHOLD as _EMPTY,
    LOW_CONF_THRESHOLD as _LOW,
    MAX_RETRIES as _MAX_RETRIES,
    QueryPlanner,
)
from app.modules.fill.agent.runner import (
    LLMClient,
    generate_multi_row,
    validate_type,
)
from app.modules.fill.port import FillPort
from app.modules.rag.port import RagPort

logger = logging.getLogger("fill.service")


class FillService(FillPort):
    """P3 fill() 入口：4 组件 Pipeline（见 IMPLEMENTATION_PLAN.md §三）。

    parse() → 1.2/1.3 职责，2.2 不实现（OWNERS.md L31）。
    fill()  → 仅读 RagPort.query()，绝不回写图谱（ACCEPTANCE.md §7）。
    """

    def __init__(self, settings: Settings | None = None) -> None:
        """settings 为 None 时用契约默认值（本地 Ollama qwen2.5:7b）。"""
        self._settings = settings or Settings()
        self._llm = LLMClient(self._settings)

    def _score_field(self, f, ctx):
        """对单个字段打分，返回 (raw_value, conf, align, tv, top)。"""
        top = ctx.contexts[0] if ctx.contexts else None

        # 创新点 2 TAPE：按 field_type 选模板 → 拼 prompt → 调 LLM
        prompt = LLMClient.build_prompt(f, ctx.contexts[:3], self._settings)
        raw_value = self._llm.complete(prompt) if (top and top.content) else ""

        _, tv = validate_type(f.field_type.value, raw_value, getattr(f, "notes", None))
        retrieval_score = top.score if top else None
        align = QueryPlanner.entity_align_score(
            raw_value,
            top.content if top else "",
            getattr(top, "entities", None) if top else None,
        )
        conf = QueryPlanner.calc_confidence(retrieval_score, align, tv)
        return raw_value, conf, align, tv, top

    def parse(self, request: ParseFormRequest) -> ParseFormResult:
        raise NotImplementedModule("fill", "parse")

    def _apply_value_to_field(self, f, raw_value, conf, ctx, stats) -> None:
        """把生成值 + 上下文写入单个 FormField（统一 threshold/sources/stats 逻辑）。

        conf 由调用方（_score_field / MSR 后处理）提前算好传入，此处不再二次计算，
        避免 mock 场景下 top 是 Mock 导致的崩溃，也保证算法只走一次。
        """
        if conf < _EMPTY or raw_value == "" or raw_value is None:
            f.value = None
            f.confidence = 0.0
            f.status = FieldStatus.empty
            if f.original_value is not None:
                stats.empty += 1
            logger.info("[PostProc] 字段[%s] → EMPTY (conf=%.4f < %.2f 或无值), raw=%r",
                        f.name, conf, _EMPTY, raw_value[:50] if raw_value else raw_value)
        else:
            f.value = raw_value
            f.confidence = round(float(conf), 3)
            f.status = FieldStatus.suggested
            if conf < _LOW:
                stats.low_confidence += 1
                logger.info("[PostProc] 字段[%s] → LOW_CONFIDENCE (conf=%.4f ∈ [%.2f, %.2f)), value=%r",
                            f.name, conf, _EMPTY, _LOW, raw_value[:50])
            else:
                logger.info("[PostProc] 字段[%s] → SUGGESTED (conf=%.4f ≥ %.2f), value=%r",
                            f.name, conf, _LOW, raw_value[:50])
            stats.filled += 1

        # sources 去重
        seen: set[str] = set()
        deduped: list[SourceRef] = []
        for c in ctx.contexts[:3]:
            key = f"{c.doc_id}|{c.content[:50]}"
            if key not in seen:
                seen.add(key)
                deduped.append(SourceRef(snippet=c.content, doc_id=c.doc_id, score=c.score))
        f.sources = deduped

    def _fill_single_fields(self, group, coarse, fine_ctxs, rag, stats, _log_debug) -> None:
        """label_value 分支：逐字段 score + retry（沿用 Day 2-4 逻辑）。"""
        from aff_contracts.rag import RagQueryRequest

        logger.info("[label_value] 开始处理 group=%s, 字段数=%d", group.key, len(group.fields))

        for f in group.fields:
            ctx = fine_ctxs.get(f.id, coarse)
            raw_value, conf, align, tv, top = self._score_field(f, ctx)
            logger.info("[label_value] 字段[%s] 首次打分: conf=%.4f align=%.4f tv=%.2f retrieval=%s raw=%r",
                        f.name, conf, align, tv,
                        (top.score if top else None),
                        raw_value[:50] if raw_value else raw_value)

            # ---- 重试机制：align < 阈值时循环重检索，最多 MAX_RETRIES 次 ----
            for _attempt in range(_MAX_RETRIES):
                if align >= _RETRY:
                    break
                logger.info("[label_value] 字段[%s] 触发重试#%d: align=%.4f < %.2f",
                            f.name, _attempt + 1, align, _RETRY)
                retry_q = QueryPlanner.build_retry_query(f)
                retry_ctx = rag.query(
                    RagQueryRequest(query=retry_q, mode="local")
                )
                rv2, conf2, align2, tv2, top2 = self._score_field(f, retry_ctx)
                if _log_debug:
                    logger.debug(
                        "字段[%s] 重试#%d: align=%.4f < %.2f → 重检索\n"
                        "  首次 conf=%.4f align=%.4f | 重试 conf=%.4f align=%.4f",
                        f.name, _attempt + 1, align, _RETRY, conf, align, conf2, align2,
                    )
                if conf2 > conf:
                    raw_value, conf, align, tv, top, ctx = (
                        rv2, conf2, align2, tv2, top2, retry_ctx,
                    )
                    logger.info("[label_value] 字段[%s] 重试#%d 采纳: conf %.4f → %.4f",
                                f.name, _attempt + 1, conf - (conf2 - conf), conf)
                    if _log_debug:
                        logger.debug("字段[%s] 重试#%d 采纳: conf → %.4f", f.name, _attempt + 1, conf)
                else:
                    logger.info("[label_value] 字段[%s] 重试#%d 未采纳: 首次 conf=%.4f 仍更优",
                                f.name, _attempt + 1, conf)
                    if _log_debug:
                        logger.debug("字段[%s] 重试#%d 未采纳: 首次 conf=%.4f 仍更优", f.name, _attempt + 1, conf)
                    break

            if _log_debug:
                if conf < _EMPTY or raw_value == "":
                    verdict = "EMPTY（强制置空）"
                elif conf < _LOW:
                    verdict = "LOW_CONFIDENCE（标黄）"
                else:
                    verdict = "SUGGESTED（正常建议）"
                logger.debug(
                    "字段[%s] 最终判定: confidence=%.4f → %s\n"
                    "  retrieval_score=%s  align=%.4f  type_validity=%.2f\n"
                    "  阈值: EMPTY<%.2f  LOW<%.2f",
                    f.name, conf, verdict,
                    (top.score if top else None), align, tv,
                    _EMPTY, _LOW,
                )

            self._apply_value_to_field(f, raw_value, conf, ctx, stats)

    def _fill_header_row_table(self, group, rag, stats, _log_debug) -> None:
        """Day 5 MSR 分支：header_row_table 批量生成。

        步骤：
          1. pre_determine_entity_type → (entity_type, query_hint)
          2. build_multi_row_query → 定向检索 mix
          3. generate_multi_row → 一次 LLM 调用，批量 JSON 数组
          4. 按 row_index / column_key 把值回写到 group.fields
          5. 若生成行数 > group 已分配字段行数 → 不再额外扩列（只填已有的 FormField）
          6. 若生成行数 < group 已分配字段行数 → 剩余字段按 EMPTY 处理
        """
        from aff_contracts.rag import RagQueryRequest, RagQueryResult

        headers = group.headers or []
        if not headers:
            logger.info("[MSR] group=%s: headers 为空，降级空处理 %d 字段", group.key, len(group.fields))
            if _log_debug:
                logger.debug("group=%s: headers 为空，MSR 跳过（降级空处理）", group.key)
            # 降级：把所有字段置空
            for f in group.fields:
                empty_ctx = RagQueryResult(answer="", contexts=[])
                self._apply_value_to_field(f, "", 0.0, empty_ctx, stats)
            return

        logger.info("[MSR] group=%s 开始, headers=%s, 字段数=%d", group.key, headers, len(group.fields))

        # --- MSR Step 1: entity_type 预问 ---
        entity_type, query_hint = QueryPlanner.pre_determine_entity_type(group, self._llm)
        logger.info("[MSR] Step1 entity_type=%r, query_hint=%r", entity_type, query_hint)
        if _log_debug:
            logger.debug("group=%s MSR Step1: entity_type=%r, query_hint=%r",
                         group.key, entity_type, query_hint)

        # --- MSR Step 2: 定向检索（一次 mix 检索代替粗+细） ---
        msr_query = QueryPlanner.build_multi_row_query(entity_type, query_hint, headers)
        msr_ctx = rag.query(RagQueryRequest(query=msr_query, mode="mix", response_format="json_object"))
        logger.info("[MSR] Step2 检索完成: contexts=%d, query=%r", len(msr_ctx.contexts), msr_query[:60])
        if _log_debug:
            logger.debug("group=%s MSR Step2: query=%r → contexts=%d",
                         group.key, msr_query[:50], len(msr_ctx.contexts))

        # --- MSR Step 3: 批量 JSON 生成（一次 LLM 调用） ---
        mr_result = generate_multi_row(
            self._llm,
            headers,
            msr_ctx.contexts[:5],  # 最多喂 5 段上下文，省 token
            self._settings,
            entity_type=entity_type,
            hint=query_hint,
        )
        generated_rows = mr_result.rows
        logger.info("[MSR] Step3 批量生成: %d 行 (max_table_rows=%d, 喂入 contexts=%d)",
                    len(generated_rows), self._settings.max_table_rows, min(len(msr_ctx.contexts), 5))
        if _log_debug:
            logger.debug("group=%s MSR Step3: 生成 %d 行 (max_table_rows=%d)",
                         group.key, len(generated_rows), self._settings.max_table_rows)

        # --- MSR Step 4: 回写值到 FormField（按 row_index + column_key 对齐） ---
        # 先把 group.fields 按 (row_index, column_key) 建索引
        field_by_coord: dict[tuple[int | None, str | None], "object"] = {}
        # 按 row_index 分组的 column_key 映射
        fields_by_row: dict[int, dict[str, "object"]] = defaultdict(dict)
        for f in group.fields:
            if f.row_index is not None and f.column_key:
                fields_by_row[f.row_index][f.column_key] = f
            coord = (f.row_index, f.column_key)
            field_by_coord[coord] = f

        # 已分配的最大 row_index（现有字段的）
        existing_row_indices = sorted(fields_by_row.keys())
        max_existing_row = max(existing_row_indices) if existing_row_indices else -1

        used_contexts = msr_ctx.contexts  # 批量生成的所有行共享同一组 sources
        top_ctx = used_contexts[0] if used_contexts else None

        # 对每一行生成结果 → 填入对应 row_index 的字段
        for row_i, row_data in enumerate(generated_rows):
            if row_i > max_existing_row:
                # 生成的行数超过现有字段的行数上限 → 不扩表，直接忽略后续行
                if _log_debug:
                    logger.debug("group=%s: 生成行#%d 超过现有 max_existing_row=%d → 忽略",
                                 group.key, row_i, max_existing_row)
                break
            # row_data: {column_key -> value_str_or_None}
            if row_i not in fields_by_row:
                continue
            for col_key, raw_value in row_data.items():
                f = fields_by_row[row_i].get(col_key)
                if f is None:
                    continue
                val = raw_value if isinstance(raw_value, str) else ("" if raw_value is None else str(raw_value))
                # MSR 路径：对每个 cell 计算一次 CSF（批量生成共用 top_ctx）
                _, tv = validate_type(f.field_type.value, val, getattr(f, "notes", None))
                retrieval_score = top_ctx.score if top_ctx else None
                align = QueryPlanner.entity_align_score(
                    val,
                    top_ctx.content if top_ctx else "",
                    getattr(top_ctx, "entities", None) if top_ctx else None,
                )
                conf = QueryPlanner.calc_confidence(retrieval_score, align, tv)
                self._apply_value_to_field(f, val, conf, msr_ctx, stats)
                if _log_debug:
                    logger.debug("group=%s 回写: row=%d col=%s → value=%r (status=%s, conf=%s)",
                                 group.key, row_i, col_key, f.value, f.status, f.confidence)

        # 对没被填到的剩余字段（existing 但 generated rows 不够，或 generated 没覆盖到）→ 置空
        for f in group.fields:
            if f.value is not None or f.status != FieldStatus.empty:
                # 已经被上面填过 suggested/empty 了，跳过
                continue
            # 原有值可能被清过 → 统一走 EMPTY 路径保证 sources 注入 (conf=0 → EMPTY)
            self._apply_value_to_field(f, "", 0.0, msr_ctx, stats)

    def fill(self, request: FillFormRequest, rag: RagPort) -> FillResult:
        from aff_contracts.rag import RagQueryRequest, RagQueryResult

        groups = FieldGrouper.group(request.fields)
        stats = FillStats()
        _log_debug = logger.isEnabledFor(logging.DEBUG)

        logger.info("[fill] 开始: job_id=%s, 字段总数=%d, 分组数=%d",
                    request.job_id, len(request.fields), len(groups))

        for group in groups:
            logger.info("[fill] 分组: key=%s, layout=%s, 字段=%d, headers=%s",
                        group.key, group.layout.value, len(group.fields), group.headers)
            if _log_debug:
                logger.debug("=" * 60)
                logger.debug("处理 group: key=%s, layout=%s, fields=%d, headers=%s",
                             group.key, group.layout.value, len(group.fields), group.headers)

            if group.layout == LayoutKind.header_row_table:
                # ---- Day 5 MSR 路径：一次预问 + 一次定向检索 + 一次批量生成（3 次 round-trip，而不是 N*M 次） ----
                logger.info("[fill] → 走 MSR 多行表路径")
                self._fill_header_row_table(group, rag, stats, _log_debug)
            else:
                # ---- 原有逐字段路径（label_value） ----
                logger.info("[fill] → 走 label_value 单行路径")
                plan = QueryPlanner.plan(group)
                coarse = rag.query(RagQueryRequest(query=plan.coarse_query, mode="mix"))

                # 并行细检索：同一字段组内的多个 fine_queries 用线程池并发
                fine_queries = plan.fine_queries
                fine_ctxs: dict[str, "object"] = {}
                if len(fine_queries) <= 1:
                    # 单字段无需线程池开销
                    for fid, q in fine_queries.items():
                        fine_ctxs[fid] = rag.query(RagQueryRequest(query=q, mode="local"))
                else:
                    logger.info("[fill] 并行细检索: %d 个 fine_queries, workers=%d",
                                len(fine_queries), min(len(fine_queries), 4))
                    with ThreadPoolExecutor(max_workers=min(len(fine_queries), 4)) as pool:
                        futures = {
                            pool.submit(rag.query, RagQueryRequest(query=q, mode="local")): fid
                            for fid, q in fine_queries.items()
                        }
                        for fut in futures:
                            fine_ctxs[futures[fut]] = fut.result()

                self._fill_single_fields(group, coarse, fine_ctxs, rag, stats, _log_debug)

        logger.info("[fill] 完成: job_id=%s, stats={filled=%d, empty=%d, low_confidence=%d}",
                    request.job_id, stats.filled, stats.empty, stats.low_confidence)
        if _log_debug:
            logger.debug("=" * 60)
            logger.debug("fill() 结束: stats={filled=%d, empty=%d, low_confidence=%d}",
                         stats.filled, stats.empty, stats.low_confidence)

        return FillResult(
            job_id=request.job_id, fields=request.fields, stats=stats
        )


def get_fill_service(settings: Settings | None = None) -> FillPort:
    return FillService(settings)
