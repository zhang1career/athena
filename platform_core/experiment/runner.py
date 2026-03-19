"""Experiment runner per DESIGN_SPECIFICATIONS §2"""
import logging
import os
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ExperimentConfig:
    """Experiment configuration."""

    name: str
    strategy_id: str
    params: Dict[str, Any] = field(default_factory=dict)
    data_config: Dict[str, Any] = field(default_factory=dict)
    parent_run_id: Optional[str] = None


@dataclass
class ExperimentResult:
    """Result of an experiment run."""

    run_id: str
    status: str  # SUCCESS, FAILED
    metrics: Dict[str, float] = field(default_factory=dict)
    error_message: str = ""
    artifacts: List[Dict[str, Any]] = field(default_factory=list)


class ExperimentRunner:
    """Base interface for experiment execution."""

    def run(self, config: ExperimentConfig) -> ExperimentResult:
        raise NotImplementedError


class LocalRunner(ExperimentRunner):
    """Local synchronous experiment runner. Phases: INIT, TRAIN, VALIDATE, BACKTEST, FINALIZE."""

    def __init__(self, data_loader_factory=None):
        """
        Args:
            data_loader_factory: Callable(data_config) -> (X_train, y_train, X_val, y_val, X_test, y_test)
        """
        self.data_loader_factory = data_loader_factory

    def run(self, config: ExperimentConfig) -> ExperimentResult:
        run_id = str(uuid.uuid4())[:12]
        logger.info("[LocalRunner] Starting run %s: %s", run_id, config.name)

        try:
            # INIT
            from platform_core.strategy import get_strategy

            strategy = get_strategy(config.strategy_id, config.params)
            if strategy is None:
                return ExperimentResult(
                    run_id=run_id,
                    status="FAILED",
                    error_message=f"Strategy not found: {config.strategy_id}",
                )

            X_train, y_train = None, None
            X_val, y_val = None, None
            X_test, y_test = None, None
            group_ids_train, group_ids_val = None, None
            if self.data_loader_factory:
                data = self.data_loader_factory(config.data_config)
                if len(data) >= 2:
                    X_train, y_train = data[0], data[1]
                if len(data) >= 4:
                    X_val, y_val = data[2], data[3]
                if len(data) >= 6:
                    X_test, y_test = data[4], data[5]
                if len(data) >= 9:
                    group_ids_train, group_ids_val = data[6], data[7]

            if X_train is None or y_train is None:
                return ExperimentResult(
                    run_id=run_id,
                    status="FAILED",
                    error_message="No training data available",
                )

            # TRAIN (fit kwargs: group_ids for group_winner task)
            fit_kwargs = {}
            if group_ids_train is not None:
                fit_kwargs["group_ids"] = group_ids_train
            strategy.fit(X_train, y_train, **fit_kwargs)

            # Save training artifact when artifact_dir is provided (e.g. by prediction round).
            # Artifact = model (LightGBM etc.) or correlation params (odds_baseline θ).
            artifacts: List[Dict[str, Any]] = []
            artifact_dir = (config.data_config or {}).get("artifact_dir")
            artifact_filename = (config.data_config or {}).get("artifact_filename") or "model.pkl"
            if artifact_dir and os.path.isdir(artifact_dir):
                try:
                    artifact_obj = (
                        strategy.get_artifact()
                        if hasattr(strategy, "get_artifact")
                        else getattr(strategy, "_model", None)
                    )
                    if artifact_obj is not None:
                        import joblib
                        path = os.path.join(artifact_dir, artifact_filename)
                        joblib.dump(artifact_obj, path)
                        artifacts.append({"type": "artifact", "path": artifact_filename})
                        logger.info("[LocalRunner] Saved artifact to %s", path)
                except Exception as e:
                    logger.warning("[LocalRunner] Failed to save artifact: %s", e)

            # VALIDATE (unified evaluation by task)
            metrics = {}
            if X_val is not None and y_val is not None:
                from platform_core.backtest.engine import compute_metrics
                predict_kwargs = {"group_ids": group_ids_val} if group_ids_val is not None else {}
                result = strategy.predict(X_val, **predict_kwargs)
                task = (config.data_config or {}).get("task", "auto")
                metrics = compute_metrics(
                    y_val,
                    result.predictions,
                    task=task,
                    y_proba=getattr(result, "proba", None),
                )

            # BACKTEST (same as validate for now; full backtest in backtest engine)
            # FINALIZE: metrics already computed
            return ExperimentResult(run_id=run_id, status="SUCCESS", metrics=metrics, artifacts=artifacts)

        except Exception as e:
            logger.exception("[LocalRunner] Run %s failed: %s", run_id, e)
            return ExperimentResult(
                run_id=run_id,
                status="FAILED",
                error_message=str(e),
            )
