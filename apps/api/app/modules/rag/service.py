from __future__ import annotations

import asyncio
import json
from functools import partial
from pathlib import Path
from typing import Any

import numpy as np
from aff_contracts import (
    DeleteDocumentRequest,
    DocumentBundle,
    RagContext,
    RagQueryRequest,
    RagQueryResult,
    UpsertDocumentRequest,
    UpsertDocumentResult,
)

from app.core.errors import NotImplementedModule
from app.core.paths import lightrag_dir
from app.core.settings_store import load_settings
from app.modules.rag.port import RagPort

_SCHEMA_PATH = Path(__file__).with_name("personal_kb.schema.json")
_client: Any | None = None
_signature: tuple[str, ...] | None = None
_lock = asyncio.Lock()


def contexts_from_query_raw(raw: dict[str, Any]) -> list[RagContext]:
    data = raw.get("data") if isinstance(raw.get("data"), dict) else {}
    entities = [
        str(item.get("entity_name") or item.get("entity") or "").strip()
        for item in data.get("entities") or []
        if isinstance(item, dict)
    ]
    entities = [name for name in entities if name][:12]
    contexts: list[RagContext] = []
    for chunk in data.get("chunks") or []:
        if not isinstance(chunk, dict):
            continue
        content = str(chunk.get("content") or chunk.get("text") or "").strip()
        if not content:
            continue
        score = chunk.get("score")
        contexts.append(
            RagContext(
                content=content[:500],
                doc_id=str(chunk.get("file_path") or "").strip() or None,
                score=float(score) if isinstance(score, (int, float)) else None,
                entities=entities or None,
            )
        )
    if not contexts and entities:
        contexts.append(RagContext(content="、".join(entities), entities=entities))
    return contexts[:8]


def answer_from_query_raw(raw: dict[str, Any]) -> str:
    llm = raw.get("llm_response") if isinstance(raw.get("llm_response"), dict) else {}
    content = llm.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    message = raw.get("message")
    if isinstance(message, str) and message.strip():
        return message.strip()
    return "图谱没有返回答案"


def bundle_to_text(bundle: DocumentBundle) -> str:
    title = bundle.title.strip()
    body = bundle.text.strip()
    if title and not body.startswith(title):
        return f"{title}\n\n{body}"
    return body


def _entity_types() -> list[str]:
    data = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    names = [str(item["name"]) for item in data.get("entities", []) if item.get("name")]
    if "技能" not in names:
        names.append("技能")
    return names


def _api_key() -> str:
    settings = load_settings()
    if settings.llm_provider == "ollama":
        return settings.llm_api_key or "ollama"
    if not settings.llm_api_key:
        raise RuntimeError("未配置 llm_api_key，无法写入图谱")
    return settings.llm_api_key


async def _probe_embedding_dim(model: str, base_url: str, api_key: str) -> int:
    from lightrag.llm.openai import openai_embed

    sample = await openai_embed.func(
        ["probe"],
        model=model,
        base_url=base_url,
        api_key=api_key,
    )
    return int(sample.shape[1])


async def get_graph_client() -> Any:
    global _client, _signature
    settings = load_settings()
    signature = (
        str(lightrag_dir()),
        settings.llm_api_base,
        settings.llm_model,
        settings.embedding_model,
        settings.summary_language,
    )
    async with _lock:
        if _client is not None and _signature == signature:
            return _client
        if _client is not None:
            await _client.finalize_storages()
            _client = None
        from lightrag import LightRAG
        from lightrag.llm.openai import openai_complete_if_cache, openai_embed
        from lightrag.utils import EmbeddingFunc

        api_key = _api_key()
        base_url = settings.llm_api_base
        model = settings.extract_model or settings.llm_model
        embedding_model = settings.embedding_model
        dim = await _probe_embedding_dim(embedding_model, base_url, api_key)

        async def llm_model_func(
            prompt: str,
            system_prompt: str | None = None,
            history_messages: list[dict[str, Any]] | None = None,
            **kwargs: Any,
        ) -> str:
            return await openai_complete_if_cache(
                model,
                prompt,
                system_prompt=system_prompt,
                history_messages=history_messages,
                api_key=api_key,
                base_url=base_url,
                timeout=180,
                **kwargs,
            )

        client = LightRAG(
            working_dir=str(lightrag_dir()),
            llm_model_func=llm_model_func,
            embedding_func=EmbeddingFunc(
                embedding_dim=dim,
                max_token_size=8192,
                model_name=embedding_model,
                func=partial(
                    openai_embed.func,
                    model=embedding_model,
                    base_url=base_url,
                    api_key=api_key,
                ),
            ),
            addon_params={
                "language": settings.summary_language or "Chinese",
                "entity_types": _entity_types(),
            },
        )
        await client.initialize_storages()
        _client = client
        _signature = signature
        return client


class RagService(RagPort):
    async def aupsert(self, request: UpsertDocumentRequest) -> UpsertDocumentResult:
        text = bundle_to_text(request.bundle)
        if not text.strip():
            return UpsertDocumentResult(
                doc_id=request.bundle.doc_id,
                status="failed",
                error="DocumentBundle.text 为空",
            )
        try:
            client = await get_graph_client()
            if request.mode == "reindex":
                deleted = await client.adelete_by_doc_id(request.bundle.doc_id)
                if deleted.status in {"fail", "not_allowed"}:
                    return UpsertDocumentResult(
                        doc_id=request.bundle.doc_id,
                        status="failed",
                        error=deleted.message,
                    )
            filename = str(request.bundle.metadata.get("filename") or request.bundle.title)
            track_id = await client.ainsert(
                text,
                ids=request.bundle.doc_id,
                file_paths=filename,
            )
        except Exception as exc:
            return UpsertDocumentResult(
                doc_id=request.bundle.doc_id,
                status="failed",
                error=str(exc),
            )
        return UpsertDocumentResult(
            doc_id=request.bundle.doc_id,
            status="ready",
            stats={"mode": request.mode, "chars": len(text), "track_id": track_id},
        )

    def upsert(self, request: UpsertDocumentRequest) -> UpsertDocumentResult:
        raise NotImplementedModule("rag", "upsert")

    async def adelete(self, request: DeleteDocumentRequest) -> None:
        client = await get_graph_client()
        deleted = await client.adelete_by_doc_id(request.doc_id)
        if deleted.status == "fail":
            raise RuntimeError(deleted.message)

    def delete(self, request: DeleteDocumentRequest) -> None:
        raise NotImplementedModule("rag", "delete")

    async def _run_query(
        self,
        query: str,
        *,
        mode: str = "mix",
        user_prompt: str | None = None,
    ) -> RagQueryResult:
        from lightrag import QueryParam

        client = await get_graph_client()
        raw = await client.aquery_llm(
            query,
            param=QueryParam(
                mode=mode,
                stream=False,
                include_references=True,
                user_prompt=user_prompt,
            ),
        )
        if not isinstance(raw, dict):
            raw = {"message": str(raw)}
        return RagQueryResult(
            answer=answer_from_query_raw(raw),
            contexts=contexts_from_query_raw(raw),
            raw={
                "status": raw.get("status"),
                "message": raw.get("message"),
            },
        )

    async def aquery(self, request: RagQueryRequest) -> RagQueryResult:
        return await self._run_query(request.query, mode=request.mode)

    async def aquery_value(self, query: str, *, attribute: str | None = None) -> RagQueryResult:
        label = attribute or "该字段"
        return await self._run_query(
            query,
            user_prompt=(
                f"只输出{label}的值本身，一个短语或数字。"
                "不要写根据材料，不要解释，不要引用编号，不要加粗。"
                "没有就只输出无。"
            ),
        )

    def query(self, request: RagQueryRequest) -> RagQueryResult:
        raise NotImplementedModule("rag", "query")


def get_rag_service() -> RagService:
    return RagService()
