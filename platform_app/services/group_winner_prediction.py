"""
小组赛第一名预测服务：采用 统一度量 + 简单归一化，在服务端融合多个中间结果，预测各队获得小组第一的概率。

数据来源：
  1. 配置文件：applications/worldcup/config/groups_*.yaml（小组分组与赔率）
  2. 赔率盘口：见 groups_*.yaml 中的 odds 字段（当前为配置内示例值，可改为外部数据源）
  3. 相关度 θ：resources/artifacts/ 下的 pkl 文件
"""
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


def _default_artifact_dir() -> Path:
    """artifact 目录，与 settings.RESOURCE_ROOT 一致"""
    from django.conf import settings
    root = getattr(settings, "RESOURCE_ROOT", None) or str(Path(settings.BASE_DIR) / "resources")
    return Path(root) / "artifacts"


def _get_artifact_filename() -> str:
    """从 worldcup config 读取 artifact 文件名"""
    from applications.worldcup.config import load
    pred = (load() or {}).get("prediction") or {}
    return pred.get("artifact_filename") or "worldcup_odds_group_winner.pkl"


def _load_artifact(filename: str) -> Optional[Dict[str, Any]]:
    """加载 artifact pkl，返回 { strategy_id, theta } 或原始 dict"""
    p = _default_artifact_dir() / filename
    if not p.exists():
        logger.warning("Artifact not found: %s", p)
        return None
    try:
        import joblib
        data = joblib.load(p)
        return data if isinstance(data, dict) else None
    except Exception as e:
        logger.exception("Failed to load artifact %s: %s", p, e)
        return None


def compute_group_winner_prediction(artifact_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    服务端计算：采用 统一度量 + 简单归一化 融合多个中间结果，预测各队获得小组第一的概率。
    所有计算在服务端完成，前端仅展示结果。

    Returns:
        {
            "fusion_method": "unified_metric_normalization",
            "intermediates": [ { "strategy_id", "weights", "theta" }, ... ],
            "theta": 主 θ（兼容前端，单策略时为该策略的 θ）,
            "records": [ { "group", "team", "odds_proba", "fused_proba", "is_predicted_winner" }, ... ],
            "groups_summary": [ { "group", "winner", "winner_proba" }, ... ]
        }
    """
    from applications.worldcup.config import load_groups_config
    from applications.worldcup.strategies.odds_baseline_group_winner import (
        _normalize_implied_proba_by_group,
        PROBA_MIN,
        PROBA_MAX,
    )
    from platform_core.fusion import fuse_with_unified_metric_normalization

    # 1. 从配置文件加载分组与赔率（applications/worldcup/config/groups_*.yaml）
    groups, teams, odds_list, edition = load_groups_config()
    if not groups:
        logger.warning("No groups config loaded, returning empty result")
        return {"records": [], "groups_summary": [], "theta": None, "intermediates": [], "fusion_method": "unified_metric_normalization", "edition": None}
    odds_proba_raw = np.array(odds_list, dtype=float)

    # 2. 构建中间结果列表（可扩展：添加 LightGBM、ELO 等）
    # 赔率：按组归一化
    proba_odds = _normalize_implied_proba_by_group(odds_proba_raw, groups)
    proba_odds = np.clip(proba_odds, PROBA_MIN, PROBA_MAX)

    # 3. 从 resources/artifacts/ 加载相关度 θ
    artifact = _load_artifact(_get_artifact_filename())
    theta_odds = None
    if artifact:
        theta_odds = artifact.get("theta") if isinstance(artifact.get("theta"), dict) else artifact

    intermediates: List[Dict[str, Any]] = [
        {
            "strategy_id": "odds_baseline_group_winner",
            "proba": proba_odds,
            "theta": theta_odds,
        }
    ]
    # 后续可追加: intermediates.append({ "strategy_id": "lightgbm_group_winner", "proba": ..., "theta": ... })

    # 2. 统一度量 + 简单归一化 融合（服务端）
    fused_proba, weights, theta_list = fuse_with_unified_metric_normalization(intermediates)
    fused_proba = np.clip(fused_proba, PROBA_MIN, PROBA_MAX)
    fused_proba = fused_proba.tolist()

    # 3. 每组预测第一名为组内概率最高者
    unique_groups = sorted(set(groups))
    predicted_winners = {}
    for g in unique_groups:
        idx = [i for i, x in enumerate(groups) if x == g]
        best_i = max(idx, key=lambda i: fused_proba[i])
        predicted_winners[g] = best_i

    records = []
    for i, (g, t) in enumerate(zip(groups, teams)):
        records.append({
            "group": g,
            "team": t,
            "odds_proba": round(odds_proba_raw[i], 4),
            "fused_proba": round(fused_proba[i], 4),
            "is_predicted_winner": i in predicted_winners.values(),
        })

    groups_summary = []
    for g in unique_groups:
        wi = predicted_winners[g]
        groups_summary.append({
            "group": g,
            "winner": teams[wi],
            "winner_proba": round(fused_proba[wi], 4),
        })

    # 5. 组装返回（兼容前端，theta 为主策略的 θ）
    result: Dict[str, Any] = {
        "fusion_method": "unified_metric_normalization",
        "edition": edition,
        "records": records,
        "groups_summary": groups_summary,
    }
    if theta_list:
        for i, ti in enumerate(theta_list):
            ti["weight"] = round(weights[i], 4) if i < len(weights) else None
        result["intermediates"] = theta_list
        t = theta_odds or {}
        result["theta"] = {
            "auc": round(t.get("auc", 0), 4),
            "brier": round(t.get("brier", 0), 4),
            "spearman": round(t.get("spearman", 0), 4),
            "suggested_weight": round(t.get("suggested_weight", 0.5), 4),
        }
    else:
        result["theta"] = None
        result["intermediates"] = []

    return result
