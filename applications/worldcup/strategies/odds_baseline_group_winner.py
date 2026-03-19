"""赔率基线策略：不做训练，预测值 = 某档赔率的隐含概率（如最后一档）。用于 group_winner 融合时作为「赔率」中间结果。"""
import numpy as np
import pandas as pd
from platform_core.strategy.base import Strategy, PredictResult, StrategySchema
from platform_core.strategy.registry import register_strategy


@register_strategy(
    "odds_baseline_group_winner",
    description="赔率基线：不训练，用赔率隐含概率作为 P(小组第一)，供融合与相关度计算。",
)
class OddsBaselineGroupWinnerStrategy(Strategy):
    """Use a single odds column (e.g. latest) as P(winner). No fit."""

    def __init__(self, odds_column_index: int = -1, **kwargs):
        """
        Args:
            odds_column_index: 用作 P(winner) 的特征列索引，默认 -1（最后一列，通常为最新赔率）。
        """
        self.odds_column_index = odds_column_index
        self._model = None

    def fit(self, X, y, **kwargs) -> None:
        # No-op: 赔率即预测，无需训练
        pass

    def predict(self, X, **kwargs) -> PredictResult:
        X = np.asarray(X)
        if X.ndim == 1:
            X = X.reshape(1, -1)
        col = self.odds_column_index
        proba_positive = np.asarray(X[:, col], dtype=float).ravel()
        proba_positive = np.clip(proba_positive, 1e-6, 1 - 1e-6)
        proba = np.column_stack([1 - proba_positive, proba_positive])
        preds = (proba_positive >= 0.5).astype(int)
        # 兼容 DataFrame（与平台其他策略一致）
        if hasattr(X, "columns") and X.shape[1] == len(X.columns):
            X = pd.DataFrame(X, columns=X.columns)
        return PredictResult(predictions=preds, proba=proba, metadata={"odds_proba": proba_positive.tolist()})

    def get_params(self) -> dict:
        return {"odds_column_index": self.odds_column_index}

    def set_params(self, **params) -> None:
        if "odds_column_index" in params:
            self.odds_column_index = int(params["odds_column_index"])

    @classmethod
    def get_schema(cls) -> StrategySchema:
        return StrategySchema(
            name="OddsBaselineGroupWinner",
            version="0.1.0",
            params_schema={
                "odds_column_index": {"type": "integer", "default": -1, "description": "Feature column index for P(winner), -1 = last"},
            },
            supported_tasks=["group_winner"],
        )
