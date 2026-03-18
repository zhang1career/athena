"""Sklearn-based strategy (example)"""
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from platform_core.strategy.base import Strategy, PredictResult, StrategySchema
from platform_core.strategy.registry import register_strategy


@register_strategy("sklearn_rf")
class SklearnStrategy(Strategy):
    """Random Forest classifier via scikit-learn."""

    def __init__(self, n_estimators: int = 100, max_depth: int = 5, **kwargs):
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self._model = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            **kwargs,
        )

    def fit(self, X, y, **kwargs) -> None:
        X = np.asarray(X)
        y = np.asarray(y)
        self._model.fit(X, y, **kwargs)

    def predict(self, X, **kwargs) -> PredictResult:
        X = np.asarray(X)
        preds = self._model.predict(X)
        proba = self._model.predict_proba(X) if hasattr(self._model, "predict_proba") else None
        return PredictResult(predictions=preds, proba=proba, metadata={})

    def get_params(self) -> dict:
        return {"n_estimators": self.n_estimators, "max_depth": self.max_depth}

    def set_params(self, **params) -> None:
        if "n_estimators" in params:
            self.n_estimators = int(params["n_estimators"])
        if "max_depth" in params:
            self.max_depth = int(params["max_depth"])
        self._model = RandomForestClassifier(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
        )

    @classmethod
    def get_schema(cls) -> StrategySchema:
        return StrategySchema(
            name="SklearnRandomForest",
            version="0.1.0",
            params_schema={
                "n_estimators": {"type": "integer", "default": 100, "minimum": 1},
                "max_depth": {"type": "integer", "default": 5},
            },
        )
