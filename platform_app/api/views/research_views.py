"""AI Research Loop: propose experiment; GET recommendations (data requirements)."""
import logging
import threading

from rest_framework.views import APIView

from common.snowflake import get_snowflake_id
from rest_framework.request import Request

from common.utils.http_util import resp_ok, resp_err, resp_exception
from common.consts.response_const import RET_INVALID_PARAM

from platform_app.repos.experiment_repo import create_run, update_run_status
from platform_core.experiment.runner import ExperimentConfig
from platform_app.services.experiment_runner import get_runner
from platform_app.services.ai_recommendations import get_recommendations
from platform_app.services.prediction_round import start_prediction_round

logger = logging.getLogger(__name__)


class ResearchProposeView(APIView):
    """
    Accept AI proposal: strategy_id, params override, combiner_config.
    Creates and runs experiment, returns run_id.
    """

    def post(self, request: Request):
        try:
            data = request.data if hasattr(request, "data") and request.data else {}
            if not isinstance(data, dict):
                data = {}
            strategy_id = data.get("strategy_id")
            if not strategy_id:
                return resp_err("strategy_id required", code=RET_INVALID_PARAM)
            params = data.get("params") or {}
            data_config = data.get("data_config") or {}
            name = data.get("name") or f"AI propose: {strategy_id}"

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
            runner = get_runner(data_config)

            def run_async():
                try:
                    result = runner.run(config)
                    update_run_status(
                        run_id,
                        result.status,
                        metrics=result.metrics,
                        error_message=result.error_message,
                    )
                except Exception as e:
                    logger.exception("Research propose run %s failed: %s", run_id, e)
                    update_run_status(run_id, "FAILED", error_message=str(e))

            t = threading.Thread(target=run_async)
            t.daemon = True
            t.start()
            return resp_ok({"run_id": run_id, "status": "PENDING"})
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


class StartPredictionRoundView(APIView):
    """
    POST /api/v1/research/start-prediction-round

    启动一轮预测流程：先由 AI 判断是否缺少数据/配置等；通过则执行预测流程，否则返回 error + suggestion。
    请求体可选: {"application": "worldcup"}。
    成功返回 data: {run_id, status}；失败返回 data: {error, suggestion}，前端展示报错与建议。
    """

    def post(self, request: Request):
        try:
            data = getattr(request, "data", None) or {}
            application = (data if isinstance(data, dict) else {}).get("application", "worldcup")
            out = start_prediction_round(application=application)
            return resp_ok(out)
        except Exception as e:
            logger.exception("Start prediction round failed: %s", e)
            return resp_exception(e)
