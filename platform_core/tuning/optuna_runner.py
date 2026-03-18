"""Optuna-based parameter search per DESIGN_SPECIFICATIONS §4."""
import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


def run_optuna_study(
    objective_fn: Callable[[dict], float],
    param_space: Dict[str, Any],
    n_trials: int = 50,
    study_name: Optional[str] = None,
) -> tuple[dict, float]:
    """
    Run Optuna study. objective_fn receives trial params, returns metric to minimize.
    param_space: e.g. {
        "learning_rate": {"type": "float", "low": 0.01, "high": 0.3},
        "n_estimators": {"type": "int", "low": 50, "high": 500},
        "max_depth": [3, 5, 7, 9],
    }
    Returns (best_params, best_value).
    """
    try:
        import optuna
    except ImportError:
        raise ImportError("optuna is required. pip install optuna")

    def objective(trial):
        params = {}
        for name, spec in param_space.items():
            if isinstance(spec, dict):
                t = spec.get("type", "float")
                if t == "float":
                    params[name] = trial.suggest_float(
                        name, spec["low"], spec["high"], log=spec.get("log", False)
                    )
                elif t == "int":
                    params[name] = trial.suggest_int(name, spec["low"], spec["high"])
                elif t == "categorical":
                    params[name] = trial.suggest_categorical(name, spec["choices"])
            elif isinstance(spec, (list, tuple)):
                params[name] = trial.suggest_categorical(name, list(spec))
            else:
                params[name] = spec
        return objective_fn(params)

    study = optuna.create_study(study_name=study_name or "athena")
    study.optimize(objective, n_trials=n_trials, show_progress_bar=True)
    return study.best_params, study.best_value
