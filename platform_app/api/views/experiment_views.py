"""Experiment REST API per DESIGN_SPECIFICATIONS §6"""
import logging
import threading

from rest_framework.views import APIView

from rest_framework.request import Request

from common.utils.http_util import resp_ok, resp_err, resp_exception, safe_request_data, with_type
from common.consts.response_const import RET_INVALID_PARAM, RET_RESOURCE_NOT_FOUND

from platform_app.models import ExperimentRun
from platform_app.repos.experiment_repo import (
    create_run,
    update_run_status,
    get_run,
    list_runs,
)
from platform_app.services.prediction_round import (
    apply_improvements,
    fetch_and_save_improvement_suggestions,
    get_workflow_phase_label,
)
from platform_core.experiment.runner import ExperimentConfig
from platform_core.strategy.registry import get_strategy_schema
from platform_app.services.experiment_runner import get_runner

logger = logging.getLogger(__name__)


def _run_experiment_async(pk: int, config: ExperimentConfig):
    try:
        runner = get_runner(config.data_config)
        result = runner.run(config)
        update_run_status(
            pk,
            result.status,
            metrics=result.metrics,
            error_message=result.error_message,
        )
        if result.status == "SUCCESS":
            fetch_and_save_improvement_suggestions(pk)
    except Exception as e:
        logger.exception("Experiment %s failed: %s", pk, e)
        update_run_status(pk, "FAILED", error_message=str(e))


class ExperimentListCreateView(APIView):
    """POST /api/v1/experiments - create and start; GET - list."""

    def post(self, request: Request):
        try:
            data = safe_request_data(request)
            name = data.get("name") or "Unnamed"
            strategy = data.get("strategy")
            if not strategy:
                return resp_err("strategy required", code=RET_INVALID_PARAM)
            params = data.get("params") or {}
            data_config = data.get("data_config") or {}
            task = data_config.get("task")
            if task:
                schema = get_strategy_schema(strategy)
                if schema and getattr(schema, "supported_tasks", None) and task not in schema.supported_tasks:
                    return resp_err(
                        f"策略 {strategy} 不支持任务 {task}（支持: {schema.supported_tasks}）",
                        code=RET_INVALID_PARAM,
                    )

            run = create_run(
                name=name,
                strategy=strategy,
                params=params,
                data_config=data_config,
            )
            config = ExperimentConfig(
                name=name,
                strategy_id=strategy,
                params=params,
                data_config=data_config,
            )
            t = threading.Thread(target=_run_experiment_async, args=(run.id, config))
            t.daemon = True
            t.start()
            return resp_ok({"id": run.id, "status": "PENDING"})
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
            strategy = request.GET.get("strategy")
            strategy_ids_raw = request.GET.get("strategy_ids")
            strategy_ids = [s.strip() for s in strategy_ids_raw.split(",") if s.strip()] if strategy_ids_raw else None

            items, total = list_runs(
                limit=limit, offset=offset, status=status,
                strategy=strategy, strategy_ids=strategy_ids,
            )
            data = []
            for r in items:
                params = r.params or {}
                workflow_phase = params.get("workflow_phase")
                data.append({
                    "id": r.id,
                    "name": r.name,
                    "strategy": r.strategy,
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
    """GET /api/v1/experiments/{pk} - detail; DELETE - delete record."""

    def get(self, request: Request, pk: int):
        run = get_run(pk)
        if not run:
            return resp_err("Experiment not found", code=RET_RESOURCE_NOT_FOUND)
        params = run.params or {}
        workflow_phase = params.get("workflow_phase")
        evaluation_raw = getattr(run, "evaluation", None) or ""
        evaluation_list = [
            line.strip() for line in (str(evaluation_raw or "").strip().split("\n"))
            if line.strip()
        ]
        # 供 odds_baseline 可视化：若无 artifacts 则根据 train_id 推断 artifact 路径
        artifact_path_hint = None
        if run.strategy == "odds_baseline_group_winner":
            arts = run.artifacts or []
            if arts and isinstance(arts[0], dict) and arts[0].get("path"):
                artifact_path_hint = arts[0]["path"]
            elif params.get("train_id"):
                try:
                    from platform_app.models import Train
                    t = Train.objects.filter(pk=params["train_id"]).first()
                    if t and (t.code or "").strip():
                        artifact_path_hint = (t.code or "").strip() + ".pkl"
                except Exception:
                    pass
            if not artifact_path_hint:
                artifact_path_hint = "worldcup_odds_group_winner.pkl"
        return resp_ok({
            "id": run.id,
            "name": run.name,
            "description": getattr(run, "description", "") or "",
            "strategy": run.strategy,
            "params": run.params,
            "artifact_path_hint": artifact_path_hint,
            "data_config": run.data_config,
            "data_q": run.data_q,
            "status": run.status_label,
            "metrics": run.metrics,
            "artifacts": run.artifacts,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "error_message": run.error_message,
            "workflow_phase": workflow_phase,
            "workflow_phase_label": get_workflow_phase_label(workflow_phase),
            "evaluation": evaluation_raw,
            "evaluation_list": evaluation_list,
            "confirmed_improvements_at": params.get("confirmed_improvements_at"),
            "improvement_follow_up_run_id": params.get("improvement_follow_up_run_id"),
            "cursor_cli_exit_code": params.get("cursor_cli_exit_code"),
            "cursor_cli_log_path": params.get("cursor_cli_log_path"),
            "cursor_cli_completed_at": params.get("cursor_cli_completed_at"),
            "cursor_cli_error": params.get("cursor_cli_error"),
            "v": run.v,
        })

    def delete(self, request: Request, pk: int):
        """DELETE /api/v1/experiments/{pk} - delete experiment record."""
        run = get_run(pk)
        if not run:
            return resp_err("Experiment not found", code=RET_RESOURCE_NOT_FOUND)
        run.delete()
        return resp_ok({"id": pk, "deleted": True})


class ExperimentRefreshSuggestionsView(APIView):
    """POST /api/v1/experiments/{pk}/refresh-suggestions — 重新调用 AI 获取实验结果评价并写回 run.evaluation。"""

    def post(self, request: Request, pk: int):
        run = get_run(pk)
        if not run:
            return resp_err("Experiment not found", code=RET_RESOURCE_NOT_FOUND)
        fetch_and_save_improvement_suggestions(pk)
        run = get_run(pk)
        params = run.params or {}
        evaluation_raw = getattr(run, "evaluation", None) or ""
        evaluation_list = [
            line.strip() for line in (str(evaluation_raw or "").strip().split("\n"))
            if line.strip()
        ]
        return resp_ok({
            "evaluation": evaluation_raw,
            "evaluation_list": evaluation_list,
            "workflow_phase": params.get("workflow_phase"),
            "workflow_phase_label": get_workflow_phase_label(params.get("workflow_phase")),
        })


class ExperimentCancelView(APIView):
    """POST /api/v1/experiments/{pk}/cancel"""

    def post(self, request: Request, pk: int):
        run = get_run(pk)
        if not run:
            return resp_err("Experiment not found", code=RET_RESOURCE_NOT_FOUND)
        if run.status == ExperimentRun.Status.RUNNING:
            update_run_status(pk, "CANCELLED")
        return resp_ok({"id": pk, "status": "CANCELLED"})


class ExperimentConfirmImprovementsView(APIView):
    """POST /api/v1/experiments/{pk}/confirm-improvements — 执行改进：勾选实验结果评价项+补充信息，调用 cursor-cli 在项目内执行改进"""

    def post(self, request: Request, pk: int):
        run = get_run(pk)
        if not run:
            return resp_err("Experiment not found", code=RET_RESOURCE_NOT_FOUND)
        try:
            data = safe_request_data(request) or {}
            selected_indices = data.get("selected_indices")
            if selected_indices is not None and not isinstance(selected_indices, list):
                selected_indices = [int(x) for x in str(selected_indices).split(",") if str(x).strip().isdigit()]
            elif isinstance(selected_indices, list):
                selected_indices = [int(x) for x in selected_indices if isinstance(x, (int, float)) or (isinstance(x, str) and x.strip().isdigit())]
            supplementary = data.get("supplementary")
            if supplementary is not None and not isinstance(supplementary, str):
                supplementary = str(supplementary)
            out = apply_improvements(pk, selected_indices=selected_indices, supplementary=supplementary)
            if out.get("error"):
                return resp_err(out["error"], code=RET_INVALID_PARAM)
            return resp_ok(out)
        except Exception as e:
            logger.exception("Apply improvements failed: %s", e)
            return resp_exception(e)
