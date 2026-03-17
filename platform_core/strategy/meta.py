"""Meta / combination strategies per DESIGN_SPECIFICATIONS §1.3"""
from typing import List

from platform_core.strategy.base import Strategy, PredictResult, StrategySchema


class MetaStrategy(Strategy):
    """Base class for strategies that combine sub-strategies."""

    def __init__(self, sub_strategies: List[Strategy], combiner_config: dict):
        self.sub_strategies = sub_strategies
        self.combiner_config = combiner_config

    def fit(self, X, y, **kwargs) -> None:
        for s in self.sub_strategies:
            s.fit(X, y, **kwargs)

    def predict(self, X, **kwargs) -> PredictResult:
        raise NotImplementedError

    @classmethod
    def get_schema(cls) -> StrategySchema:
        return StrategySchema(
            name=cls.__name__,
            version="0.1.0",
            params_schema={
                "sub_strategies": {"type": "array", "description": "List of strategy IDs"},
                "combiner_config": {"type": "object", "description": "Combiner configuration"},
            },
        )


class WeightedEnsemble(MetaStrategy):
    """Weighted average of sub-strategy predictions."""

    def predict(self, X, **kwargs) -> PredictResult:
        import numpy as np
        weights = self.combiner_config.get("weights")
        if not weights or len(weights) != len(self.sub_strategies):
            weights = [1.0 / len(self.sub_strategies)] * len(self.sub_strategies)
        total_w = sum(weights)
        weights = [w / total_w for w in weights]

        preds_list = []
        for s, w in zip(self.sub_strategies, weights):
            r = s.predict(X, **kwargs)
            p = np.asarray(r.predictions)
            preds_list.append(p * w)
        combined = sum(preds_list)
        return PredictResult(
            predictions=combined,
            proba=None,
            metadata={"sub_predictions": [r.predictions for r in [s.predict(X, **kwargs) for s in self.sub_strategies]]},
        )

    @classmethod
    def get_schema(cls) -> StrategySchema:
        return StrategySchema(
            name="WeightedEnsemble",
            version="0.1.0",
            params_schema={
                "sub_strategies": {"type": "array", "description": "Strategy IDs"},
                "weights": {"type": "array", "items": {"type": "number"}, "description": "Weights per sub-strategy"},
            },
        )


class StackingStrategy(MetaStrategy):
    """Stacking: meta-model learns to combine sub-strategy outputs. Placeholder."""

    def predict(self, X, **kwargs) -> PredictResult:
        # Placeholder: simple average for now
        import numpy as np
        preds = [s.predict(X, **kwargs).predictions for s in self.sub_strategies]
        combined = np.mean(preds, axis=0)
        return PredictResult(predictions=combined, metadata={})

    @classmethod
    def get_schema(cls) -> StrategySchema:
        return StrategySchema(
            name="StackingStrategy",
            version="0.1.0",
            params_schema={
                "sub_strategies": {"type": "array"},
                "meta_model": {"type": "string", "description": "Meta model type"},
            },
        )
