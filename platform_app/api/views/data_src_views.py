"""DataSrc CRUD API."""
import logging

from rest_framework.views import APIView
from rest_framework.request import Request

from common.utils.http_util import resp_ok, resp_err, resp_exception, safe_request_data
from common.consts.response_const import RET_INVALID_PARAM, RET_RESOURCE_NOT_FOUND

from platform_app.models import DataSrc
from platform_app.services.data_src_url import (
    ensure_url_params_has_placeholders,
    normalize_url_params_list,
)

logger = logging.getLogger(__name__)


class DataSrcListCreateView(APIView):
    """GET /api/v1/data-srcs - list; POST - create."""

    def get(self, request: Request):
        try:
            rows = list(
                DataSrc.objects.order_by("-ct").values("id", "name", "src_url", "url_params", "dest_path", "ct", "ut")
            )
            for r in rows:
                r["url_params"] = normalize_url_params_list(r.get("url_params") or [])
            return resp_ok({"data_srcs": rows})
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
            url_params = data.get("url_params")
            if url_params is not None and not isinstance(url_params, list):
                url_params = []
            url_params = ensure_url_params_has_placeholders(src_url, normalize_url_params_list(url_params or []))
            obj = DataSrc.objects.create(name=name, src_url=src_url, url_params=url_params, dest_path=dest_path)
            return resp_ok({
                "id": obj.id, "name": obj.name, "src_url": obj.src_url,
                "url_params": normalize_url_params_list(obj.url_params or []),
                "dest_path": obj.dest_path, "ct": obj.ct, "ut": obj.ut
            })
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
                "id": obj.id, "name": obj.name, "src_url": obj.src_url,
                "url_params": normalize_url_params_list(obj.url_params or []),
                "dest_path": obj.dest_path, "ct": obj.ct, "ut": obj.ut
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
            if "url_params" in data:
                v = data.get("url_params")
                obj.url_params = normalize_url_params_list(v) if isinstance(v, list) else []
            if "dest_path" in data:
                obj.dest_path = (data.get("dest_path") or "").strip()
            if "name" in data:
                obj.name = (data.get("name") or "").strip()
            obj.url_params = ensure_url_params_has_placeholders(obj.src_url, obj.url_params)
            obj.save()
            return resp_ok({
                "id": obj.id, "name": obj.name, "src_url": obj.src_url,
                "url_params": normalize_url_params_list(obj.url_params or []),
                "dest_path": obj.dest_path, "ct": obj.ct, "ut": obj.ut
            })
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
