"""Simple ELO-based baseline: predict from feature ratio (placeholder)."""
import numpy as np
from platform_core.strategy.base import Strategy, PredictResult, StrategySchema
from platform_core.strategy.registry import register_strategy


@register_strategy("elo_baseline", description="基于 ELO 实力差的简单基线，用于比赛胜平负预测，无需训练。")
class EloBaselineStrategy(Strategy):
    """Baseline: use f1-f2 ratio to predict 1/X/2. 0=home, 1=draw, 2=away."""

    def __init__(self, threshold: float = 0.1, **kwargs):
        self.threshold = threshold

    def fit(self, X, y, **kwargs) -> None:
        pass  # No training

    def predict(self, X, **kwargs) -> PredictResult:
        X = np.asarray(X)
        # Assume cols 0,1 are home/away strength; predict from diff
        if X.shape[1] >= 2:
            diff = X[:, 0] - X[:, 1]
        else:
            diff = np.zeros(len(X))
        preds = np.ones(len(X), dtype=int)
        preds[diff > self.threshold] = 0
        preds[diff < -self.threshold] = 2
        return PredictResult(predictions=preds, metadata={})

    def get_params(self) -> dict:
        return {"threshold": self.threshold}

    def set_params(self, **params) -> None:
        if "threshold" in params:
            self.threshold = float(params["threshold"])

    @classmethod
    def get_schema(cls) -> StrategySchema:
        return StrategySchema(
            name="EloBaseline",
            version="0.1.0",
            params_schema={
                "threshold": {"type": "number", "default": 0.1},
            },
            supported_tasks=["match_1x2"],
        )
