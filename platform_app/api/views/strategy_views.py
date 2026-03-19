"""Strategy REST API per DESIGN_SPECIFICATIONS §6"""
import logging

# Load worldcup strategies (auto-imports all modules in applications.worldcup.strategies)
try:
    import applications.worldcup.strategies  # noqa: F401
except ImportError:
    pass

from rest_framework.views import APIView

from common.utils.http_util import resp_ok, resp_err, resp_exception
from common.consts.response_const import RET_RESOURCE_NOT_FOUND

from platform_core.strategy import list_strategies, get_strategy_schema, get_strategy_description

logger = logging.getLogger(__name__)


class StrategyListView(APIView):
    """GET /api/v1/strategies - list registered strategies."""

    def get(self, request):
        try:
            strategies = list_strategies()
            return resp_ok({"data": strategies})
        except Exception as e:
            logger.exception("List strategies failed: %s", e)
            return resp_exception(e)


class StrategySchemaView(APIView):
    """GET /api/v1/strategies/{id}/schema - get parameter schema."""

    def get(self, request, strategy_id: str):
        schema = get_strategy_schema(strategy_id)
        if not schema:
            return resp_err("Strategy not found", code=RET_RESOURCE_NOT_FOUND)
        payload = {
            "id": strategy_id,
            "name": schema.name,
            "version": schema.version,
            "params_schema": schema.params_schema,
            "description": get_strategy_description(strategy_id),
        }
        if hasattr(schema, "supported_tasks") and schema.supported_tasks:
            payload["supported_tasks"] = schema.supported_tasks
        return resp_ok(payload)
