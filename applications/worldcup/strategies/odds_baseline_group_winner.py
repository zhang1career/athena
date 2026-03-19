"""赔率基线策略：预测值 = 某档赔率的隐含概率。相关度 θ（与真实结果的 AUC/Brier 等）视为训练结果，保存到 artifact，参与融合权重与预测计算。"""
import numpy as np
import pandas as pd
from platform_core.strategy.base import Strategy, PredictResult, StrategySchema
from platform_core.strategy.registry import register_strategy

# 概率裁剪边界，避免 log_loss 因 0/1 极值爆炸
PROBA_EPS = 1e-6
PROBA_MIN = PROBA_EPS
PROBA_MAX = 1.0 - PROBA_EPS


def _normalize_implied_proba_by_group(
    proba_positive: np.ndarray,
    group_ids: list,
) -> np.ndarray:
    """按组去水并归一化：同组内隐含概率之和通常>1，归一化使组内和为1。"""
    out = np.asarray(proba_positive, dtype=float).copy()
    if not group_ids or len(group_ids) != len(out):
        return out
    uniq = sorted(set(g for g in group_ids if g != ""))
    for g in uniq:
        idx = [i for i, x in enumerate(group_ids) if x == g]
        if not idx:
            continue
        s = out[idx].sum()
        if s > 0:
            out[idx] = out[idx] / s
        # 若 s<=0 则保持原值，后续会 clip
    return out


@register_strategy(
    "odds_baseline_group_winner",
    description="赔率基线：用赔率隐含概率作为 P(小组第一)。相关度 θ 视为训练结果，保存到 artifact，参与预测与融合权重。",
)
class OddsBaselineGroupWinnerStrategy(Strategy):
    """Use odds implied proba as P(winner). fit() computes correlation θ; artifact saved; predict uses θ for calibration."""

    def __init__(self, odds_column_index: int = -1, **kwargs):
        """
        Args:
            odds_column_index: 用作 P(winner) 的特征列索引，默认 -1（最后一列，通常为最新赔率）。
        """
        self.odds_column_index = odds_column_index
        self._model = None
        self._artifact = None  # 相关度 θ：{auc, brier, spearman, suggested_weight}

    def fit(self, X, y, **kwargs) -> None:
        """计算赔率与真实结果的相关度 θ，作为训练结果保存到 artifact。"""
        X = np.asarray(X)
        y = np.asarray(y).ravel()
        if len(X) == 0 or len(y) == 0:
            self._artifact = {"auc": 0.5, "brier": 0.25, "spearman": 0.0, "suggested_weight": 0.0}
            return
        col = self.odds_column_index
        proba_positive = np.asarray(X[:, col], dtype=float).ravel()
        group_ids = kwargs.get("group_ids")
        if group_ids is not None:
            proba_positive = _normalize_implied_proba_by_group(proba_positive, list(group_ids))
        proba_positive = np.clip(proba_positive, PROBA_MIN, PROBA_MAX)
        from platform_core.fusion import compute_odds_correlation
        self._artifact = compute_odds_correlation(
            proba_positive,
            y,
            groups=np.asarray(group_ids) if group_ids and len(group_ids) == len(y) else None,
        )

    def get_artifact(self):
        """返回相关度 θ，保存到 artifacts/<model_name>.pkl；融合加载时可识别 strategy_id。"""
        if self._artifact is None:
            return None
        return {
            "strategy_id": "odds_baseline_group_winner",
            "theta": self._artifact,
        }

    def predict(self, X, **kwargs) -> PredictResult:
        # 若未 fit 但有 artifact 路径，则加载以参与预测（prediction-only 场景）
        if self._artifact is None:
            load_path = kwargs.get("artifact_load_path")
            if load_path:
                try:
                    import joblib
                    loaded = joblib.load(load_path)
                    # 兼容 {strategy_id, theta} 与 原始 θ dict
                    theta = loaded.get("theta", loaded) if isinstance(loaded, dict) else None
                    if isinstance(theta, dict) and "suggested_weight" in theta:
                        self._artifact = theta
                except Exception:
                    pass
        X = np.asarray(X)
        if X.ndim == 1:
            X = X.reshape(1, -1)
        col = self.odds_column_index
        proba_positive = np.asarray(X[:, col], dtype=float).ravel()
        group_ids = kwargs.get("group_ids")
        if group_ids is not None:
            proba_positive = _normalize_implied_proba_by_group(proba_positive, list(group_ids))
        proba_positive = np.clip(proba_positive, PROBA_MIN, PROBA_MAX)
        # 使用 artifact 中的 suggested_weight 参与预测：当赔率不可靠时向 0.5 收缩
        if self._artifact is not None:
            w = self._artifact.get("suggested_weight", 1.0)
            proba_positive = w * proba_positive + (1.0 - w) * 0.5
            proba_positive = np.clip(proba_positive, PROBA_MIN, PROBA_MAX)
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
