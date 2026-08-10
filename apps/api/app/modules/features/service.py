from __future__ import annotations

from app.core.errors import NotImplementedModule
from app.modules.features.port import (
    FeatureExtractRequest,
    FeatureExtractResult,
    FeaturesPort,
)


class FeaturesService(FeaturesPort):
    def extract(self, request: FeatureExtractRequest) -> FeatureExtractResult:
        raise NotImplementedModule("features", "extract")


def get_features_service() -> FeaturesPort:
    return FeaturesService()
