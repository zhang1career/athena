"""
赔率与结果的相关度计算：由 (y_proba, y_true) 得到具有相关度含义的参数 θ。
用于融合时推导博彩赔率的加权值（见 docs/FUSION_ODDS_CORRELATION_WEIGHT.md）。
"""
from typing import Dict, Optional

import numpy as np


def compute_odds_correlation(
    y_proba_positive: np.ndarray,
    y_true: np.ndarray,
    *,
    groups: Optional[np.ndarray] = None,
) -> Dict[str, float]:
    """
    用赔率隐含概率（正类概率）与真实 0/1 标签，计算相关度参数 θ。

    Args:
        y_proba_positive: 正类概率，形状 (n,)；即「该队小组第一」的隐含概率。
        y_true: 真实标签 0/1，形状 (n,)。
        groups: 可选，形状 (n,) 的分组标签（如组别），用于组内 Spearman。

    Returns:
        含以下键的字典（相关度含义的参数）：
        - auc: 赔率作为二分类得分时的 AUC
        - brier: Brier score（越小越好）
        - spearman: 全局「概率 vs 0/1」的 Spearman 相关系数
        - suggested_weight: 建议的融合权重（0~1），由 AUC 映射得到，未归一化
    """
    y_proba_positive = np.asarray(y_proba_positive, dtype=float).ravel()
    y_true = np.asarray(y_true).ravel()
    n = len(y_true)
    if n == 0:
        return {"auc": 0.5, "brier": 0.25, "spearman": 0.0, "suggested_weight": 0.0}

    theta: Dict[str, float] = {}

    # AUC（仅当存在正负类时）
    if len(np.unique(y_true)) == 2:
        try:
            from sklearn.metrics import roc_auc_score
            theta["auc"] = float(roc_auc_score(y_true, y_proba_positive))
        except Exception:
            theta["auc"] = 0.5
    else:
        theta["auc"] = 0.5

    # Brier score
    try:
        from sklearn.metrics import brier_score_loss
        theta["brier"] = float(brier_score_loss(y_true, y_proba_positive))
    except Exception:
        theta["brier"] = 0.25

    # Spearman：概率与 0/1 的秩相关（scipy 可选）
    try:
        from scipy.stats import spearmanr
        r, _ = spearmanr(y_proba_positive, y_true)
        theta["spearman"] = float(r) if not np.isnan(r) else 0.0
    except Exception:
        # 无 scipy 时用简单相关系数
        theta["spearman"] = float(np.corrcoef(y_proba_positive, y_true)[0, 1]) if n > 1 else 0.0
        if np.isnan(theta["spearman"]):
            theta["spearman"] = 0.0

    # 建议权重：由 AUC 映射，AUC=0.5 -> 0，AUC=1 -> 1，线性
    auc = theta["auc"]
    suggested = max(0.0, min(1.0, (auc - 0.5) / 0.5))
    theta["suggested_weight"] = suggested

    return theta
