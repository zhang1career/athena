"""Experiment REST API per DESIGN_SPECIFICATIONS §6"""
import logging
import threading

from rest_framework.views import APIView

from common.snowflake import get_snowflake_id
from rest_framework.request import Request

from common.utils.http_util import resp_ok, resp_err, resp_exception, with_type
from common.consts.response_const import RET_INVALID_PARAM, RET_RESOURCE_NOT_FOUND

from platform_app.models import ExperimentRun
from platform_app.repos.experiment_repo import (
    create_run,
    update_run_status,
    get_run,
    list_runs,
)
from platform_app.services.prediction_round import (
    confirm_and_apply_improvements,
    get_workflow_phase_label,
)
from platform_core.experiment.runner import ExperimentConfig
from platform_app.services.experiment_runner import get_runner

logger = logging.getLogger(__name__)


def _run_experiment_async(run_id: int, config: ExperimentConfig):
    try:
        runner = get_runner(config.data_config)
        result = runner.run(config)
        update_run_status(
            run_id,
            result.status,
            metrics=result.metrics,
            error_message=result.error_message,
        )
    except Exception as e:
        logger.exception("Experiment %s failed: %s", run_id, e)
        update_run_status(run_id, "FAILED", error_message=str(e))


class ExperimentListCreateView(APIView):
    """POST /api/v1/experiments - create and start; GET - list."""

    def post(self, request: Request):
        try:
            data = request.data if hasattr(request, "data") and request.data else {}
            if not isinstance(data, dict):
                data = {}
            name = data.get("name") or "Unnamed"
            strategy_id = data.get("strategy_id")
            if not strategy_id:
                return resp_err("strategy_id required", code=RET_INVALID_PARAM)
            params = data.get("params") or {}
            data_config = data.get("data_config") or {}

            run_id = get_snowflake_id()
            create_run(
                run_id=run_id,
                name=name,
                strategy_id=strategy_id,
                params=params,
                data_config=data_config,
            )
            config = ExperimentConfig(
                name=name,
                strategy_id=strategy_id,
                params=params,
                data_config=data_config,
            )
            t = threading.Thread(target=_run_experiment_async, args=(run_id, config))
            t.daemon = True
            t.start()
            return resp_ok({"run_id": run_id, "status": "PENDING"})
        except Exception as e:
            logger.exception("Create experiment failed: %s", e)
            return resp_exception(e)

    def get(self, request: Request):
        try:
            limit = int(with_type(request.GET.get("limit") or 50))
            offset = int(with_type(request.GET.get("offset") or 0))
            limit = min(max(1, limit), 200)
            offset = max(0, offset)
            status = request.GET.get("status")
            strategy_id = request.GET.get("strategy_id")
            strategy_ids_raw = request.GET.get("strategy_ids")
            strategy_ids = [s.strip() for s in strategy_ids_raw.split(",") if s.strip()] if strategy_ids_raw else None

            items, total = list_runs(
                limit=limit, offset=offset, status=status,
                strategy_id=strategy_id, strategy_ids=strategy_ids,
            )
            data = []
            for r in items:
                params = r.params or {}
                workflow_phase = params.get("workflow_phase")
                data.append({
                    "run_id": r.run_id,
                    "name": r.name,
                    "strategy_id": r.strategy_id,
                    "status": r.status_label,
                    "metrics": r.metrics,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "workflow_phase": workflow_phase,
                    "workflow_phase_label": get_workflow_phase_label(workflow_phase),
                })
            return resp_ok({"data": data, "total": total})
        except Exception as e:
            logger.exception("List experiments failed: %s", e)
            return resp_exception(e)


class ExperimentDetailView(APIView):
    """GET /api/v1/experiments/{run_id} - detail; DELETE - delete record."""

    def get(self, request: Request, run_id: int):
        run = get_run(run_id)
        if not run:
            return resp_err("Experiment not found", code=RET_RESOURCE_NOT_FOUND)
        params = run.params or {}
        workflow_phase = params.get("workflow_phase")
        return resp_ok({
            "run_id": run.run_id,
            "name": run.name,
            "strategy_id": run.strategy_id,
            "params": run.params,
            "data_config": run.data_config,
            "status": run.status_label,
            "metrics": run.metrics,
            "artifacts": run.artifacts,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "error_message": run.error_message,
            "workflow_phase": workflow_phase,
            "workflow_phase_label": get_workflow_phase_label(workflow_phase),
            "ai_suggestions": params.get("ai_suggestions"),
        })

    def delete(self, request: Request, run_id: int):
        """DELETE /api/v1/experiments/{run_id} - delete experiment record."""
        run = get_run(run_id)
        if not run:
            return resp_err("Experiment not found", code=RET_RESOURCE_NOT_FOUND)
        run.delete()
        return resp_ok({"run_id": run_id, "deleted": True})


class ExperimentCancelView(APIView):
    """POST /api/v1/experiments/{run_id}/cancel"""

    def post(self, request: Request, run_id: int):
        run = get_run(run_id)
        if not run:
            return resp_err("Experiment not found", code=RET_RESOURCE_NOT_FOUND)
        if run.status == ExperimentRun.Status.RUNNING:
            update_run_status(run_id, "CANCELLED")
        return resp_ok({"run_id": run_id, "status": "CANCELLED"})


class ExperimentConfirmImprovementsView(APIView):
    """POST /api/v1/experiments/{run_id}/confirm-improvements — 人工确认后执行改进"""

    def post(self, request: Request, run_id: int):
        run = get_run(run_id)
        if not run:
            return resp_err("Experiment not found", code=RET_RESOURCE_NOT_FOUND)
        try:
            out = confirm_and_apply_improvements(run_id)
            if out.get("error"):
                return resp_err(out["error"], code=RET_INVALID_PARAM)
            return resp_ok(out)
        except Exception as e:
            logger.exception("Confirm improvements failed: %s", e)
            return resp_exception(e)
