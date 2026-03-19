"""
由赔率相关度 θ 推导融合权重，供 WeightedEnsemble 使用。
见 docs/FUSION_ODDS_CORRELATION_WEIGHT.md。
"""
from typing import Any, List, Optional

import numpy as np

from platform_core.strategy.base import PredictResult

from .odds_correlation import compute_odds_correlation


def _proba_positive_from_result(result: PredictResult) -> Optional[np.ndarray]:
    """从 PredictResult 取出正类概率 (n,) 数组。"""
    if result.proba is None:
        return None
    proba = np.asarray(result.proba)
    if proba.ndim >= 2:
        return proba[:, 1]
    return proba.ravel()


def compute_fusion_weights_with_odds_correlation(
    sub_predictions: List[Any],
    y_true: np.ndarray,
    odds_strategy_index: int,
    other_weights: Optional[List[float]] = None,
) -> List[float]:
    """
    根据「赔率」分支的预测与真实标签计算 θ，并得到各分支的融合权重。

    Args:
        sub_predictions: 各子策略的 predict 结果（PredictResult 或可取 .proba 的对象）。
        y_true: 真实标签，形状 (n,)。
        odds_strategy_index: 哪个子策略是「赔率」分支（其预测将用于相关度计算）。
        other_weights: 非赔率分支的权重；若为 None 则均为 1.0。

    Returns:
        归一化后的权重列表，与 sub_predictions 一一对应。
    """
    n_strategies = len(sub_predictions)
    y_true = np.asarray(y_true).ravel()

    if odds_strategy_index < 0 or odds_strategy_index >= n_strategies:
        weights = list(other_weights) if other_weights and len(other_weights) == n_strategies else [1.0] * n_strategies
        total = sum(weights)
        return [w / total for w in weights]

    # 赔率分支：取正类概率并计算 θ
    res = sub_predictions[odds_strategy_index]
    if hasattr(res, "proba"):
        proba_positive = _proba_positive_from_result(res)
    else:
        proba_positive = None

    if proba_positive is None or len(proba_positive) != len(y_true):
        w_odds = 0.5
    else:
        theta = compute_odds_correlation(proba_positive, y_true)
        w_odds = theta["suggested_weight"]

    # 其余分支权重
    if other_weights is not None and len(other_weights) == n_strategies:
        weights = list(other_weights)
    else:
        weights = [1.0] * n_strategies
    weights[odds_strategy_index] = w_odds

    total = sum(weights)
    if total <= 0:
        return [1.0 / n_strategies] * n_strategies
    return [w / total for w in weights]


def get_odds_correlation_theta(
    sub_predictions: List[Any],
    y_true: np.ndarray,
    odds_strategy_index: int,
) -> Optional[dict]:
    """
    仅计算赔率分支的 θ，不推导权重。用于记录或展示。

    Returns:
        compute_odds_correlation 的返回值，若无法取到赔率概率则返回 None。
    """
    if odds_strategy_index < 0 or odds_strategy_index >= len(sub_predictions):
        return None
    res = sub_predictions[odds_strategy_index]
    proba_positive = _proba_positive_from_result(res) if hasattr(res, "proba") else None
    if proba_positive is None or len(proba_positive) != len(np.asarray(y_true).ravel()):
        return None
    return compute_odds_correlation(proba_positive, np.asarray(y_true).ravel())
