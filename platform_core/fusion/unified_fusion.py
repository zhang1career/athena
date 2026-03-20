"""
统一度量 + 简单归一化 融合：各中间结果依其 θ 的 suggested_weight 归一化后加权平均。
"""
from typing import Any, Dict, List, Optional

import numpy as np


def fuse_with_unified_metric_normalization(
    intermediates: List[Dict[str, Any]],
) -> tuple[np.ndarray, List[float], List[Dict[str, Any]]]:
    """
    统一度量 + 简单归一化：各中间结果按 suggested_weight 归一化后加权求和。

    Args:
        intermediates: 每项为 {
            "strategy_id": str,
            "proba": np.ndarray 形状 (n,) 正类概率,
            "theta": dict 含 auc, brier, spearman, suggested_weight，或 None 时用 0.5
        }

    Returns:
        (fused_proba, weights, theta_list)
        - fused_proba: 融合后的正类概率 (n,)
        - weights: 归一化后的权重列表，与 intermediates 一一对应
        - theta_list: 各策略的 θ 摘要（用于返回给前端）
    """
    if not intermediates:
        return np.array([]), [], []

    n = len(intermediates[0].get("proba", []))
    if n == 0:
        return np.array([]), [], []

    # 1. 取各 suggested_weight，缺失则 0.5
    suggested = []
    theta_list = []
    for item in intermediates:
        theta = item.get("theta") or {}
        if isinstance(theta, dict) and "suggested_weight" in theta:
            sw = float(theta["suggested_weight"])
        else:
            sw = 0.5
        suggested.append(max(0.0, min(1.0, sw)))
        theta_list.append({
            "strategy_id": item.get("strategy_id", ""),
            "auc": theta.get("auc"),
            "brier": theta.get("brier"),
            "spearman": theta.get("spearman"),
            "suggested_weight": theta.get("suggested_weight"),
        })

    # 2. 简单归一化
    total = sum(suggested)
    if total <= 0:
        weights = [1.0 / len(intermediates)] * len(intermediates)
    else:
        weights = [s / total for s in suggested]

    # 3. 加权平均
    fused = np.zeros(n, dtype=float)
    for i, item in enumerate(intermediates):
        proba = np.asarray(item.get("proba"), dtype=float).ravel()
        if len(proba) == n:
            fused += weights[i] * proba

    return fused, weights, theta_list
