"""Train (训练科目) CRUD API."""
import logging

from rest_framework.views import APIView
from rest_framework.request import Request

from common.utils.http_util import resp_ok, resp_err, resp_exception, safe_request_data
from common.consts.response_const import RET_INVALID_PARAM, RET_RESOURCE_NOT_FOUND

from platform_app.models import Train

logger = logging.getLogger(__name__)


def _train_to_dict(obj: Train) -> dict:
    return {
        "id": obj.id,
        "name": obj.name,
        "code": obj.code or "",
        "description": obj.description or "",
        "strategy": obj.strategy or "",
        "ct": obj.ct,
        "ut": obj.ut,
    }


class TrainListCreateView(APIView):
    """GET /api/v1/trains - list; POST - create."""

    def get(self, request: Request):
        try:
            rows = list(Train.objects.order_by("-ct").all())
            return resp_ok({"trains": [_train_to_dict(r) for r in rows]})
        except Exception as e:
            logger.exception("List trains failed: %s", e)
            return resp_exception(e)

    def post(self, request: Request):
        try:
            data = safe_request_data(request)
            name = (data.get("name") or "").strip()
            if not name:
                return resp_err("name required", code=RET_INVALID_PARAM)
            code = (data.get("code") or "").strip()
            description = (data.get("description") or "").strip()
            strategy = (data.get("strategy") or "").strip()
            obj = Train.objects.create(name=name, code=code, description=description, strategy=strategy)
            return resp_ok(_train_to_dict(obj))
        except Exception as e:
            logger.exception("Create train failed: %s", e)
            return resp_exception(e)


class TrainDetailView(APIView):
    """GET/PUT/DELETE /api/v1/trains/<pk>"""

    def get(self, request: Request, pk: int):
        try:
            obj = Train.objects.filter(pk=pk).first()
            if not obj:
                return resp_err("Train not found", code=RET_RESOURCE_NOT_FOUND)
            return resp_ok(_train_to_dict(obj))
        except Exception as e:
            logger.exception("Get train failed: %s", e)
            return resp_exception(e)

    def put(self, request: Request, pk: int):
        try:
            obj = Train.objects.filter(pk=pk).first()
            if not obj:
                return resp_err("Train not found", code=RET_RESOURCE_NOT_FOUND)
            data = safe_request_data(request)
            if "name" in data:
                name = (data.get("name") or "").strip()
                if not name:
                    return resp_err("name cannot be empty", code=RET_INVALID_PARAM)
                obj.name = name
            if "description" in data:
                obj.description = (data.get("description") or "").strip()
            if "strategy" in data:
                obj.strategy = (data.get("strategy") or "").strip()
            if "code" in data:
                obj.code = (data.get("code") or "").strip()
            obj.save()
            return resp_ok(_train_to_dict(obj))
        except Exception as e:
            logger.exception("Update train failed: %s", e)
            return resp_exception(e)

    def delete(self, request: Request, pk: int):
        try:
            obj = Train.objects.filter(pk=pk).first()
            if not obj:
                return resp_err("Train not found", code=RET_RESOURCE_NOT_FOUND)
            obj.delete()
            return resp_ok({"deleted": pk})
        except Exception as e:
            logger.exception("Delete train failed: %s", e)
            return resp_exception(e)
