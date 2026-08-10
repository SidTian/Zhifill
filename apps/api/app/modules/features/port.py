from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class FeatureExtractRequest(BaseModel):
    """3.2 输入：用户资料文本（可来自 3.3 DocumentBundle.text）。"""

    doc_id: str
    text: str = Field(min_length=1)
    language: str = "zh"


class FeatureExtractResult(BaseModel):
    """3.2 输出：结构化特征 + 可选增强文本，供 3.4 入库。"""

    doc_id: str
    key_values: dict[str, str] = Field(default_factory=dict)
    bullet_points: list[str] = Field(default_factory=list)
    enhanced_text: str | None = None
    raw: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)


@runtime_checkable
class FeaturesPort(Protocol):
    """M2 / 3.2: 用户信息大模型特征提取。"""

    def extract(self, request: FeatureExtractRequest) -> FeatureExtractResult:
        """基于 LLM 抽取要点；无依据时返回空特征，禁止编造。"""
        ...
