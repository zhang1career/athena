"""Backtest engine per DESIGN_SPECIFICATIONS §3"""
import numpy as np
from typing import Any, Dict, List, Optional, Tuple

from platform_core.strategy.base import Strategy, PredictResult


def compute_metrics(
    y_true: Any,
    y_pred: Any,
    task: str = "auto",
    y_proba: Any = None,
) -> Dict[str, float]:
    """
    Unified evaluation: compute metrics by task.
    task: 'classification' | 'regression' | 'match_1x2' | 'group_winner' | 'auto'
    y_proba: optional probability array for binary (e.g. group_winner) to compute AUC.
    """
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)

    if task == "auto":
        n_unique = len(np.unique(y_true))
        task = "classification" if n_unique <= 20 else "regression"
    # Normalize task to classification for match_1x2 / group_winner
    if task in ("match_1x2", "group_winner"):
        task = "classification"

    metrics = {}
    if task == "classification":
        from sklearn.metrics import accuracy_score, log_loss
        metrics["accuracy"] = float(accuracy_score(y_true, y_pred))
        try:
            if hasattr(y_pred, "shape") and len(y_pred.shape) > 1:
                metrics["log_loss"] = float(log_loss(y_true, y_pred))
            else:
                metrics["log_loss"] = float(log_loss(y_true, y_pred, labels=np.unique(y_true)))
        except Exception:
            pass
        # Binary: add AUC when proba provided
        if y_proba is not None and len(np.unique(y_true)) == 2:
            try:
                from sklearn.metrics import roc_auc_score
                proba = np.asarray(y_proba)
                if proba.ndim >= 2:
                    proba = proba[:, 1]
                metrics["auc"] = float(roc_auc_score(y_true, proba))
            except Exception:
                pass
    else:
        from sklearn.metrics import mean_absolute_error, mean_squared_error
        metrics["mae"] = float(mean_absolute_error(y_true, y_pred))
        metrics["rmse"] = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    return metrics


def walk_forward_split(
    X: np.ndarray,
    y: np.ndarray,
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
) -> Tuple[Tuple[np.ndarray, np.ndarray], Tuple[np.ndarray, np.ndarray], Tuple[np.ndarray, np.ndarray]]:
    """Time-series aware split. Assumes rows are ordered by time."""
    n = len(X)
    t1 = int(n * train_ratio)
    t2 = int(n * (train_ratio + val_ratio))
    train = (X[:t1], y[:t1])
    val = (X[t1:t2], y[t1:t2])
    test = (X[t2:], y[t2:])
    return train, val, test


def run_backtest(
    strategy: Strategy,
    X: np.ndarray,
    y: np.ndarray,
    split_method: str = "time",
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
) -> Dict[str, Any]:
    """
    Run backtest: train on train set, predict on val, compute metrics.
    """
    if split_method == "time":
        (X_train, y_train), (X_val, y_val), _ = walk_forward_split(
            X, y, train_ratio, val_ratio
        )
    else:
        from sklearn.model_selection import train_test_split
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, train_size=train_ratio, random_state=42
        )

    strategy.fit(X_train, y_train)
    result = strategy.predict(X_val)
    metrics = compute_metrics(y_val, result.predictions)
    return {"metrics": metrics, "n_train": len(X_train), "n_val": len(X_val)}
