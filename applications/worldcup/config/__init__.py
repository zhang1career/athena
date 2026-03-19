"""World Cup app config. Single source for strategy list etc."""
from pathlib import Path
from typing import Any, List


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


def get_strategy_ids() -> List[str]:
    """Strategy IDs for this app (single source: config.yaml)."""
    return list(load().get("strategies") or [])
