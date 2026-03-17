"""Experiment repository for CRUD operations."""
from typing import List, Optional, Union

from platform_app.models import ExperimentRun, ExperimentMetric


def _status_to_int(status: Union[str, int]) -> int:
    """Convert status str (PENDING/RUNNING/...) or int to enum value."""
    if isinstance(status, int):
        return status
    try:
        return getattr(ExperimentRun.Status, str(status).upper()).value
    except (AttributeError, ValueError):
        return ExperimentRun.Status.PENDING


def _run_id_int(v) -> int:
    """Normalize run_id to int."""
    if v is None:
        raise ValueError("run_id required")
    return int(v)


def create_run(
    run_id: int,
    name: str,
    strategy_id: str,
    params: dict,
    data_config: dict,
    parent_run_id: Optional[int] = None,
) -> ExperimentRun:
    parent = None
    if parent_run_id is not None and parent_run_id != 0:
        parent = ExperimentRun.objects.filter(run_id=int(parent_run_id)).first()
    run = ExperimentRun.objects.create(
        run_id=run_id,
        name=name,
        strategy_id=strategy_id,
        params=params,
        data_config=data_config,
        parent_id=parent.id if parent else 0,
        status=ExperimentRun.Status.RUNNING,
    )
    return run


def update_run_status(
    run_id: Union[str, int],
    status: Union[str, int],
    metrics: dict = None,
    error_message: str = "",
):
    run = ExperimentRun.objects.filter(run_id=_run_id_int(run_id)).first()
    if not run:
        return None
    run.status = _status_to_int(status)
    if metrics is not None:
        run.metrics = metrics
    if error_message:
        run.error_message = error_message
    run.save()
    return run


def update_run_params(run_id: Union[str, int], **kwargs) -> Optional[ExperimentRun]:
    """Merge key-value pairs into run.params (e.g. workflow_phase, ai_suggestions)."""
    run = ExperimentRun.objects.filter(run_id=_run_id_int(run_id)).first()
    if not run:
        return None
    params = dict(run.params or {})
    for k, v in kwargs.items():
        if v is not None:
            params[k] = v
    run.params = params
    run.save()
    return run


def get_run(run_id: Union[str, int]) -> Optional[ExperimentRun]:
    return ExperimentRun.objects.filter(run_id=_run_id_int(run_id)).first()


def list_runs(
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None,
    strategy_id: Optional[str] = None,
    strategy_ids: Optional[List[str]] = None,
) -> tuple[List[ExperimentRun], int]:
    qs = ExperimentRun.objects.all()
    if status:
        qs = qs.filter(status=_status_to_int(status))
    if strategy_ids:
        qs = qs.filter(strategy_id__in=strategy_ids)
    elif strategy_id:
        qs = qs.filter(strategy_id=strategy_id)
    total = qs.count()
    items = list(qs.order_by("-ct")[offset : offset + limit])
    return items, total
