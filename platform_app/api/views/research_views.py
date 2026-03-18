"""AI Research Loop: propose experiment; GET recommendations (data requirements)."""
import logging
import threading

from rest_framework.views import APIView

from rest_framework.request import Request

from common.utils.http_util import resp_ok, resp_err, resp_exception, safe_request_data
from common.consts.response_const import RET_INVALID_PARAM

from platform_app.repos.experiment_repo import create_run, update_run_status
from platform_core.experiment.runner import ExperimentConfig
from platform_app.services.experiment_runner import get_runner
from platform_app.services.ai_recommendations import get_recommendations
from platform_app.services.prediction_round import start_prediction_round
from platform_app.services.worldcup_data_versioning import list_patch_batches
from platform_app.services.data_file_service import list_data_file_versions

logger = logging.getLogger(__name__)


class ResearchProposeView(APIView):
    """
    Accept AI proposal: strategy_id, params override, combiner_config.
    Creates and runs experiment, returns run_id.
    """

    def post(self, request: Request):
        try:
            data = safe_request_data(request)
            strategy_id = data.get("strategy_id")
            if not strategy_id:
                return resp_err("strategy_id required", code=RET_INVALID_PARAM)
            params = data.get("params") or {}
            data_config = data.get("data_config") or {}
            name = data.get("name") or f"AI propose: {strategy_id}"

            run = create_run(
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
            runner = get_runner(data_config)

            def run_async():
                try:
                    result = runner.run(config)
                    update_run_status(
                        run.id,
                        result.status,
                        metrics=result.metrics,
                        error_message=result.error_message,
                    )
                except Exception as e:
                    logger.exception("Research propose run %s failed: %s", run.id, e)
                    update_run_status(run.id, "FAILED", error_message=str(e))

            t = threading.Thread(target=run_async)
            t.daemon = True
            t.start()
            return resp_ok({"id": run.id, "status": "PENDING"})
        except Exception as e:
            logger.exception("Research propose failed: %s", e)
            return resp_exception(e)


class ResearchRecommendationsView(APIView):
    """
    GET /api/v1/research/recommendations?application=worldcup

    AI 根据应用与策略上下文生成数据需求与运行建议（如「需要最近20年的足球数据」）。
    返回自然语言 message 与可选的 requirements 结构。
    """

    def get(self, request: Request):
        application = request.GET.get("application", "worldcup").strip() or "worldcup"
        try:
            out = get_recommendations(application=application)
            return resp_ok(out)
        except Exception as e:
            logger.exception("Research recommendations failed: %s", e)
            return resp_exception(e)


class DataPatchBatchListView(APIView):
    """
    GET /api/v1/research/data-patch-batches

    列出所有 data_patch_batch，用于前端复选框。
    """

    def get(self, request: Request):
        try:
            batches = list_patch_batches()
            return resp_ok({"batches": batches})
        except Exception as e:
            logger.exception("List patch batches failed: %s", e)
            return resp_exception(e)


class DataFileVersionsView(APIView):
    """
    GET /api/v1/research/data-file-versions?data_src_id=1

    按 data_src_id 查询 data_file 的 ct 列表（倒序），供「原始数据版本」多选下拉使用。
    """

    def get(self, request: Request):
        try:
            data_src_id = request.GET.get("data_src_id")
            if not data_src_id:
                return resp_ok({"versions": []})
            try:
                data_src_id = int(data_src_id)
            except (ValueError, TypeError):
                return resp_ok({"versions": []})
            versions = list_data_file_versions(data_src_id)
            return resp_ok({"versions": versions})
        except Exception as e:
            logger.exception("List data file versions failed: %s", e)
            return resp_exception(e)


class StartPredictionRoundView(APIView):
    """
    POST /api/v1/research/start-prediction-round

    启动一轮预测：
    - data_src_id: 必填，原始数据（data_src 的 id）
    - data_file_version: 可选，单个原始数据版本（与 data_file_versions 二选一）
    - data_file_versions: 可选，原始数据版本 ct 列表（多选）；若传则取 max 作为 data_file_version
    - patch_batch_cts: 选中的 data_patch_batch 的 ct 列表
    - incremental_update_data: 可选，name-value 字典，保存为新 batch 后加入
    """

    def post(self, request: Request):
        try:
            data = safe_request_data(request)
            application = data.get("application", "worldcup")
            data_src_id = data.get("data_src_id")
            if data_src_id is not None:
                try:
                    data_src_id = int(data_src_id)
                except (ValueError, TypeError):
                    data_src_id = None
            data_file_version = data.get("data_file_version")
            data_file_versions = data.get("data_file_versions") or []
            if isinstance(data_file_versions, list) and data_file_versions:
                try:
                    ct_list = [int(x) for x in data_file_versions if x is not None]
                    if ct_list:
                        data_file_version = max(ct_list)
                except (ValueError, TypeError):
                    pass
            if data_file_version is not None:
                try:
                    data_file_version = int(data_file_version)
                except (ValueError, TypeError):
                    data_file_version = None
            patch_batch_cts = data.get("patch_batch_cts") or []
            if not isinstance(patch_batch_cts, list):
                patch_batch_cts = []
            patch_batch_cts = [int(x) for x in patch_batch_cts if x is not None]
            incremental_update_data = data.get("incremental_update_data") or {}
            out = start_prediction_round(
                application=application,
                data_src_id=data_src_id,
                data_file_version=data_file_version,
                patch_batch_cts=patch_batch_cts,
                incremental_update_data=incremental_update_data,
            )
            return resp_ok(out)
        except Exception as e:
            logger.exception("Start prediction round failed: %s", e)
            return resp_exception(e)
