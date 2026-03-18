"""DataSrc CRUD API."""
import logging

from rest_framework.views import APIView
from rest_framework.request import Request

from common.utils.http_util import resp_ok, resp_err, resp_exception, safe_request_data
from common.consts.response_const import RET_INVALID_PARAM, RET_RESOURCE_NOT_FOUND

from platform_app.models import DataSrc

logger = logging.getLogger(__name__)


class DataSrcListCreateView(APIView):
    """GET /api/v1/data-srcs - list; POST - create."""

    def get(self, request: Request):
        try:
            items = list(
                DataSrc.objects.order_by("-ct").values("id", "name", "src_url", "dest_path", "ct", "ut")
            )
            return resp_ok({"data_srcs": items})
        except Exception as e:
            logger.exception("List data_srcs failed: %s", e)
            return resp_exception(e)

    def post(self, request: Request):
        try:
            data = safe_request_data(request)
            src_url = (data.get("src_url") or "").strip()
            if not src_url:
                return resp_err("src_url required", code=RET_INVALID_PARAM)
            dest_path = (data.get("dest_path") or "").strip()
            name = (data.get("name") or "").strip()
            obj = DataSrc.objects.create(name=name, src_url=src_url, dest_path=dest_path)
            return resp_ok({"id": obj.id, "name": obj.name, "src_url": obj.src_url, "dest_path": obj.dest_path, "ct": obj.ct, "ut": obj.ut})
        except Exception as e:
            logger.exception("Create data_src failed: %s", e)
            return resp_exception(e)


class DataSrcDetailView(APIView):
    """GET/PUT/DELETE /api/v1/data-srcs/<pk>"""

    def get(self, request: Request, pk: int):
        try:
            obj = DataSrc.objects.filter(pk=pk).first()
            if not obj:
                return resp_err("DataSrc not found", code=RET_RESOURCE_NOT_FOUND)
            return resp_ok({
                "id": obj.id, "name": obj.name, "src_url": obj.src_url, "dest_path": obj.dest_path, "ct": obj.ct, "ut": obj.ut
            })
        except Exception as e:
            logger.exception("Get data_src failed: %s", e)
            return resp_exception(e)

    def put(self, request: Request, pk: int):
        try:
            obj = DataSrc.objects.filter(pk=pk).first()
            if not obj:
                return resp_err("DataSrc not found", code=RET_RESOURCE_NOT_FOUND)
            data = safe_request_data(request)
            if "src_url" in data:
                obj.src_url = (data.get("src_url") or "").strip()
            if "dest_path" in data:
                obj.dest_path = (data.get("dest_path") or "").strip()
            if "name" in data:
                obj.name = (data.get("name") or "").strip()
            obj.save()
            return resp_ok({"id": obj.id, "name": obj.name, "src_url": obj.src_url, "dest_path": obj.dest_path, "ct": obj.ct, "ut": obj.ut})
        except Exception as e:
            logger.exception("Update data_src failed: %s", e)
            return resp_exception(e)

    def delete(self, request: Request, pk: int):
        try:
            obj = DataSrc.objects.filter(pk=pk).first()
            if not obj:
                return resp_err("DataSrc not found", code=RET_RESOURCE_NOT_FOUND)
            obj.delete()
            return resp_ok({"deleted": pk})
        except Exception as e:
            logger.exception("Delete data_src failed: %s", e)
            return resp_exception(e)
