"""Experiment repository for CRUD operations."""
from typing import List, Optional, Union

from platform_app.models import ExperimentRun, ExperimentMetric


def _ensure_list(v) -> list:
    if v is None:
        return []
    return list(v) if isinstance(v, (list, tuple)) else [v]


def _status_to_int(status: Union[str, int]) -> int:
    """Convert status str (PENDING/RUNNING/...) or int to enum value."""
    if isinstance(status, int):
        return status
    try:
        return getattr(ExperimentRun.Status, str(status).upper()).value
    except (AttributeError, ValueError):
        return ExperimentRun.Status.PENDING


def _pk_int(v) -> int:
    """Normalize pk (id) to int."""
    if v is None:
        raise ValueError("id required")
    return int(v)


def create_run(
    name: str,
    strategy: str,
    params: dict,
    data_config: dict,
    parent_id: Optional[int] = None,
    v: int = 0,
    data_q: Optional[dict] = None,
    description: Optional[str] = None,
) -> ExperimentRun:
    parent = None
    if parent_id is not None and parent_id != 0:
        parent = ExperimentRun.objects.filter(pk=_pk_int(parent_id)).first()
    run = ExperimentRun.objects.create(
        name=name,
        description=(description or "").strip(),
        strategy=strategy,
        params=params,
        data_config=data_config,
        parent_id=parent.id if parent else 0,
        v=v,
        status=ExperimentRun.Status.RUNNING,
        data_q=data_q or {},
    )
    return run


def update_run_status(
    run_id: Union[str, int],
    status: Union[str, int],
    metrics: dict = None,
    error_message: str = "",
    artifacts: Optional[List] = None,
):
    run = ExperimentRun.objects.filter(pk=_pk_int(run_id)).first()
    if not run:
        return None
    run.status = _status_to_int(status)
    if metrics is not None:
        run.metrics = metrics
    if error_message:
        run.error_message = error_message
    if artifacts is not None:
        run.artifacts = _ensure_list(artifacts)
    run.save()
    return run


def update_run_params(run_id: Union[str, int], **kwargs) -> Optional[ExperimentRun]:
    """Merge key-value pairs into run.params (e.g. workflow_phase)."""
    run = ExperimentRun.objects.filter(pk=_pk_int(run_id)).first()
    if not run:
        return None
    params = dict(run.params or {})
    for k, v in kwargs.items():
        if v is not None:
            params[k] = v
    run.params = params
    run.save()
    return run


def update_run_evaluation(run_id: Union[str, int], evaluation: str) -> Optional[ExperimentRun]:
    """Set run.evaluation (实验结果评价，由 AI 生成)."""
    run = ExperimentRun.objects.filter(pk=_pk_int(run_id)).first()
    if not run:
        return None
    run.evaluation = (evaluation or "").strip()
    run.save()
    return run


def get_run(run_id: Union[str, int]) -> Optional[ExperimentRun]:
    return ExperimentRun.objects.filter(pk=_pk_int(run_id)).first()


def list_runs(
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None,
    strategy: Optional[str] = None,
    strategy_ids: Optional[List[str]] = None,
) -> tuple[List[ExperimentRun], int]:
    qs = ExperimentRun.objects.all()
    if status:
        qs = qs.filter(status=_status_to_int(status))
    if strategy_ids:
        qs = qs.filter(strategy__in=strategy_ids)
    elif strategy:
        qs = qs.filter(strategy=strategy)
    total = qs.count()
    items = list(qs.order_by("-ct")[offset : offset + limit])
    return items, total
