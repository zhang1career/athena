"""DataLoader for World Cup match data. Supports CSV/JSON file loading."""
import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

from applications.worldcup.data.schema import MatchRecord, match_records_to_arrays

logger = logging.getLogger(__name__)


def load_from_csv(path: str, feature_cols: List[str] = None) -> List[MatchRecord]:
    """Load matches from CSV. Expected columns: match_id, home_team, away_team, date, league, result, + feature cols."""
    records = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            features = {}
            for k, v in row.items():
                if k not in ("match_id", "home_team", "away_team", "date", "league", "result", "home_goals", "away_goals"):
                    try:
                        features[k] = float(v) if v else 0
                    except ValueError:
                        features[k] = 0
            r = MatchRecord(
                match_id=row.get("match_id", ""),
                home_team=row.get("home_team", ""),
                away_team=row.get("away_team", ""),
                date=row.get("date", ""),
                league=row.get("league", ""),
                result=row.get("result") or None,
                home_goals=int(row["home_goals"]) if row.get("home_goals") and row["home_goals"].strip() else None,
                away_goals=int(row["away_goals"]) if row.get("away_goals") and row["away_goals"].strip() else None,
                features=features or None,
            )
            records.append(r)
    return records


def load_from_json(path: str) -> List[MatchRecord]:
    """Load matches from JSON array of objects."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    records = []
    for item in data if isinstance(data, list) else [data]:
        feats = item.get("features", {})
        for k, v in list(item.items()):
            if k not in ("match_id", "home_team", "away_team", "date", "league", "result", "home_goals", "away_goals", "features"):
                feats[k] = v
        records.append(MatchRecord(
            match_id=str(item.get("match_id", "")),
            home_team=str(item.get("home_team", "")),
            away_team=str(item.get("away_team", "")),
            date=str(item.get("date", "")),
            league=str(item.get("league", "")),
            result=item.get("result"),
            home_goals=item.get("home_goals"),
            away_goals=item.get("away_goals"),
            features=feats if feats else None,
        ))
    return records


def worldcup_data_loader(data_config: Dict[str, Any]) -> Tuple:
    """
    Platform DataLoader interface.
    Returns (X_train, y_train, X_val, y_val, X_test, y_test).
    """
    path = data_config.get("path") or data_config.get("data_path")
    if not path:
        raise ValueError("data_config must contain 'path' or 'data_path'")
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")

    fmt = data_config.get("format", "csv")
    if fmt == "csv":
        records = load_from_csv(str(path))
    elif fmt == "json":
        records = load_from_json(str(path))
    else:
        raise ValueError(f"Unsupported format: {fmt}")

    feature_cols = data_config.get("feature_cols")
    if not feature_cols and records:
        # Infer from first record's features
        r0 = records[0]
        feature_cols = list(r0.features.keys()) if r0.features else []
    if not feature_cols:
        feature_cols = ["f1", "f2", "f3", "f4", "f5"]  # Fallback for sample

    X, y = match_records_to_arrays(records, feature_cols)
    if len(X) == 0:
        raise ValueError("No valid records with features and result")

    train_ratio = float(data_config.get("train_ratio", 0.7))
    val_ratio = float(data_config.get("val_ratio", 0.15))
    n = len(X)
    t1 = int(n * train_ratio)
    t2 = int(n * (train_ratio + val_ratio))
    return (
        X[:t1], y[:t1],
        X[t1:t2], y[t1:t2],
        X[t2:], y[t2:],
    )
