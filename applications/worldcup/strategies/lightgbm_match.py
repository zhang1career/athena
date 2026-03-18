"""LightGBM strategy for match outcome prediction (1/X/2)."""
import numpy as np
import pandas as pd
from platform_core.strategy.base import Strategy, PredictResult, StrategySchema
from platform_core.strategy.registry import register_strategy


@register_strategy("lightgbm_match")
class LightGBMMatchStrategy(Strategy):
    """LightGBM classifier for match result (1/X/2)."""

    def __init__(self, n_estimators: int = 100, max_depth: int = 5, learning_rate: float = 0.1, **kwargs):
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self._model = None

    def _get_model(self):
        if self._model is None:
            import lightgbm as lgb
            self._model = lgb.LGBMClassifier(
                n_estimators=self.n_estimators,
                max_depth=self.max_depth,
                learning_rate=self.learning_rate,
            )
        return self._model

    def fit(self, X, y, **kwargs) -> None:
        X = np.asarray(X)
        y = np.asarray(y)
        self._get_model().fit(X, y, **kwargs)

    def predict(self, X, **kwargs) -> PredictResult:
        X = np.asarray(X)
        m = self._get_model()
        # Avoid sklearn warning: pass DataFrame with feature names if model was fitted with them
        if hasattr(m, "feature_names_in_") and m.feature_names_in_ is not None and getattr(X, "shape", None):
            n_cols = X.shape[1] if len(X.shape) > 1 else 0
            if n_cols == len(m.feature_names_in_):
                X = pd.DataFrame(X, columns=m.feature_names_in_)
        preds = m.predict(X)
        proba = m.predict_proba(X) if hasattr(m, "predict_proba") else None
        return PredictResult(predictions=preds, proba=proba, metadata={})

    def get_params(self) -> dict:
        return {
            "n_estimators": self.n_estimators,
            "max_depth": self.max_depth,
            "learning_rate": self.learning_rate,
        }

    def set_params(self, **params) -> None:
        if "n_estimators" in params:
            self.n_estimators = int(params["n_estimators"])
        if "max_depth" in params:
            self.max_depth = int(params["max_depth"])
        if "learning_rate" in params:
            self.learning_rate = float(params["learning_rate"])
        self._model = None

    @classmethod
    def get_schema(cls) -> StrategySchema:
        return StrategySchema(
            name="LightGBMMatch",
            version="0.1.0",
            params_schema={
                "n_estimators": {"type": "integer", "default": 100},
                "max_depth": {"type": "integer", "default": 5},
                "learning_rate": {"type": "number", "default": 0.1},
            },
            supported_tasks=["match_1x2"],
        )
