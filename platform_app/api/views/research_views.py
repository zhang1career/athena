"""AI Research Loop: POST /api/v1/research/propose"""
import logging
import threading

from rest_framework.views import APIView

from common.snowflake import get_snowflake_id
from rest_framework.request import Request

from common.utils.http_util import resp_ok, resp_err, resp_exception
from common.consts.response_const import RET_INVALID_PARAM

from platform_app.repos.experiment_repo import create_run, update_run_status
from platform_core.experiment.runner import LocalRunner, ExperimentConfig

from platform_app.api.views.experiment_views import _get_runner

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
            runner = _get_runner(data_config)

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
