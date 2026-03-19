"""World Cup app config. Single source for strategy list etc."""
from pathlib import Path
from typing import List, Optional, Tuple


def load() -> dict:
    """Load config.yaml from this directory."""
    path = Path(__file__).parent / "config.yaml"
    if not path.exists():
        return {}
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def load_groups_config(groups_config: Optional[str] = None) -> Tuple[List[str], List[str], List[float], Optional[str]]:
    """
    加载小组分组配置（含赔率），返回 (groups, teams, odds_proba, edition)。

    Args:
        groups_config: 配置文件名，如 groups_2026.yaml。若为 None 则从 config.yaml 的 prediction.groups_config 读取。

    Returns:
        (groups, teams, odds_proba, edition) 四个值；edition 来自 yaml 的 edition 字段
    """
    cfg = load()
    pred = cfg.get("prediction") or {}
    filename = groups_config or pred.get("groups_config") or "groups_2026.yaml"
    path = Path(__file__).parent / filename
    if not path.exists():
        return [], [], [], None
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception:
        return [], [], [], None
    edition = data.get("edition")
    grps = data.get("groups") or {}
    groups, teams, odds = [], [], []
    for g in sorted(grps.keys()):
        for item in grps[g]:
            if isinstance(item, dict):
                groups.append(g)
                teams.append(str(item.get("team", "")))
                odds.append(float(item.get("odds", 0.25)))
            else:
                groups.append(g)
                teams.append(str(item))
                odds.append(0.25)
    return groups, teams, odds, edition


def get_strategy_ids() -> List[str]:
    """Strategy IDs for this app (single source: config.yaml)."""
    return list(load().get("strategies") or [])
