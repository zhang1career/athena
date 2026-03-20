"""组内赔率隐含概率归一化（仅 numpy）。供推理 API 与 odds_baseline 策略共用，避免推理路径依赖 pandas。"""
import numpy as np

# 概率裁剪边界，与 odds_baseline_group_winner 一致
PROBA_EPS = 1e-6
PROBA_MIN = PROBA_EPS
PROBA_MAX = 1.0 - PROBA_EPS


def normalize_implied_proba_by_group(
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
    return out
