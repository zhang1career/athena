"""Meta / combination strategies per DESIGN_SPECIFICATIONS §1.3"""
from typing import List, Optional, Union

from platform_core.strategy.base import Strategy, PredictResult, StrategySchema
from platform_core.strategy.registry import register_strategy


class MetaStrategy(Strategy):
    """Base class for strategies that combine sub-strategies."""

    def __init__(self, sub_strategies: Optional[List[Strategy]] = None, combiner_config: Optional[dict] = None):
        self.sub_strategies = sub_strategies or []
        self.combiner_config = combiner_config or {}

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


@register_strategy("weighted_ensemble", description="加权融合：多策略预测加权平均；可设 weight_estimator=odds_correlation 由赔率相关度推导权重。")
class WeightedEnsemble(MetaStrategy):
    """Weighted average of sub-strategy predictions. sub_strategies can be strategy IDs (str) or Strategy instances."""

    def __init__(self, sub_strategies: Optional[List[Union[Strategy, str]]] = None, combiner_config: Optional[dict] = None):
        super().__init__(sub_strategies=[], combiner_config=combiner_config or {})
        self._sub_strategy_ids: Optional[List[str]] = None
        if sub_strategies:
            if sub_strategies and isinstance(sub_strategies[0], str):
                self._sub_strategy_ids = list(sub_strategies)
            else:
                self.sub_strategies = list(sub_strategies)

    def set_params(self, **params) -> None:
        if "sub_strategies" in params:
            val = params["sub_strategies"]
            if val and isinstance(val[0], str):
                self._sub_strategy_ids = list(val)
                self.sub_strategies = []
            else:
                self._sub_strategy_ids = None
                self.sub_strategies = list(val) if val else []
        if "combiner_config" in params:
            self.combiner_config = dict(params["combiner_config"])

    def fit(self, X, y, **kwargs) -> None:
        if self._sub_strategy_ids and not self.sub_strategies:
            from platform_core.strategy.registry import get_strategy
            self.sub_strategies = [get_strategy(sid) for sid in self._sub_strategy_ids]
            self.sub_strategies = [s for s in self.sub_strategies if s is not None]
        super().fit(X, y, **kwargs)
        cfg = self.combiner_config or {}
        if cfg.get("weight_estimator") == "odds_correlation":
            idx = cfg.get("odds_strategy_index")
            if idx is not None and 0 <= idx < len(self.sub_strategies):
                try:
                    from platform_core.fusion import compute_fusion_weights_with_odds_correlation, get_odds_correlation_theta
                    import numpy as np
                    sub_preds = [s.predict(np.asarray(X)) for s in self.sub_strategies]
                    weights = compute_fusion_weights_with_odds_correlation(sub_preds, np.asarray(y), idx)
                    self.combiner_config["weights"] = weights
                    theta = get_odds_correlation_theta(sub_preds, np.asarray(y), idx)
                    if theta is not None:
                        self.combiner_config["odds_correlation_theta"] = theta
                except Exception:
                    pass

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
