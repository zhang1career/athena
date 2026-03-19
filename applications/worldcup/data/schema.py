"""Football match data schema for World Cup prediction."""
from dataclasses import dataclass
from typing import Any, List, Optional
import numpy as np


@dataclass
class MatchRecord:
    """Single match record for prediction."""
    match_id: str
    home_team: str
    away_team: str
    date: str
    league: str
    # Target: 1=home win, X=draw, 2=away win
    result: Optional[str] = None  # "1", "X", "2"
    home_goals: Optional[int] = None
    away_goals: Optional[int] = None
    # Feature columns (extensible)
    features: Optional[dict] = None

    def to_target_class(self) -> Optional[int]:
        """Map result to 0/1/2 for classification."""
        if self.result == "1":
            return 0
        if self.result == "X":
            return 1
        if self.result == "2":
            return 2
        return None


def match_records_to_arrays(
    records: List[MatchRecord],
    feature_cols: List[str],
) -> tuple[np.ndarray, np.ndarray]:
    """Convert match records to X, y arrays."""
    X_rows = []
    y_list = []
    for r in records:
        if r.features and r.to_target_class() is not None:
            row = [r.features.get(c, 0) for c in feature_cols]
            X_rows.append(row)
            y_list.append(r.to_target_class())
    return np.array(X_rows, dtype=float), np.array(y_list)


def group_records_to_arrays(
    records: List[dict],
    feature_cols: List[str],
) -> tuple[np.ndarray, np.ndarray, List[str]]:
    """Convert group_winner records (dicts with features, is_winner) to X, y arrays and group_ids (for per-group de-water/normalize)."""
    X_rows = []
    y_list = []
    group_list = []
    for r in records:
        if not isinstance(r, dict):
            continue
        feats = r.get("features") or {}
        y_val = r.get("is_winner")
        if y_val is None:
            continue
        try:
            y_list.append(int(y_val))
        except (TypeError, ValueError):
            continue
        row = [feats.get(c, 0) for c in feature_cols]
        X_rows.append(row)
        group_list.append(str(r.get("group") or ""))
    return np.array(X_rows, dtype=float), np.array(y_list), group_list
