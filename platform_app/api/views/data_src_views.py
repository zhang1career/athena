"""DataSrc CRUD API."""
import logging

from rest_framework.views import APIView
from rest_framework.request import Request

from common.utils.http_util import resp_ok, resp_err, resp_exception, safe_request_data
from common.consts.response_const import RET_INVALID_PARAM, RET_RESOURCE_NOT_FOUND

from platform_app.models import DataSrc, FetchMode, FormatType
from platform_app.services.data_src_url import (
    ensure_url_params_has_placeholders,
    normalize_url_params_list,
)
from platform_app.services.data_src_fetch import fetch_data_and_save

logger = logging.getLogger(__name__)


def _coerce_fetch_mode(v):
    """将前端传来的 fetch_mode 转为 int（FetchMode）。"""
    if v is None:
        return FetchMode.RAW
    try:
        i = int(v)
        if i in (FetchMode.RAW, FetchMode.HTML_TABLES):
            return i
    except (TypeError, ValueError):
        pass
    return FetchMode.RAW


def _coerce_format_type(v):
    """将前端传来的 format_type 转为 int（FormatType）。"""
    if v is None:
        return FormatType.CSV
    try:
        i = int(v)
        if i in (FormatType.JSON, FormatType.CSV, FormatType.EXCEL, FormatType.XLS):
            return i
    except (TypeError, ValueError):
        pass
    return FormatType.CSV


def _data_src_to_dict(obj):
    return {
        "id": obj.id,
        "name": obj.name,
        "src_url": obj.src_url,
        "url_params": normalize_url_params_list(obj.url_params or []),
        "raw_name": obj.raw_name or "",
        "raw_path": obj.raw_path or "",
        "cleaned_name": obj.cleaned_name or "",
        "cleaned_path": obj.cleaned_path or "",
        "clean_script": obj.clean_script or "",
        "fetch_mode": obj.fetch_mode,
        "format_type": obj.format_type,
        "ct": obj.ct,
        "ut": obj.ut,
    }


class DataSrcListCreateView(APIView):
    """GET /api/v1/data-srcs - list; POST - create."""

    def get(self, request: Request):
        try:
            rows = list(
                DataSrc.objects.order_by("-ct").values(
                    "id", "name", "src_url", "url_params", "raw_name", "raw_path", "cleaned_name", "cleaned_path",
                    "clean_script", "fetch_mode", "format_type", "ct", "ut"
                )
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
            name = (data.get("name") or "").strip()
            url_params = data.get("url_params")
            if url_params is not None and not isinstance(url_params, list):
                url_params = []
            raw_name = (data.get("raw_name") or "").strip()
            raw_path = (data.get("raw_path") or "").strip()
            cleaned_name = (data.get("cleaned_name") or "").strip()
            cleaned_path = (data.get("cleaned_path") or "").strip()
            fetch_mode = _coerce_fetch_mode(data.get("fetch_mode"))
            format_type = _coerce_format_type(data.get("format_type"))
            url_params = ensure_url_params_has_placeholders(src_url, normalize_url_params_list(url_params or []))
            obj = DataSrc.objects.create(
                name=name, src_url=src_url, url_params=url_params,
                raw_name=raw_name, raw_path=raw_path, cleaned_name=cleaned_name, cleaned_path=cleaned_path,
                fetch_mode=fetch_mode, format_type=format_type,
            )
            return resp_ok(_data_src_to_dict(obj))
        except Exception as e:
            logger.exception("Create data_src failed: %s", e)
            return resp_exception(e)


class DataSrcFetchView(APIView):
    """POST /api/v1/data-srcs/<pk>/fetch - 获取数据：用 params 解析 URL 与路径，拉取并保存，创建 data_file。"""

    def post(self, request: Request, pk: int):
        try:
            data = safe_request_data(request)
            params = data.get("params")
            if not isinstance(params, dict):
                params = {}
            # 前端可能传字符串，统一转成字符串
            params = {k: str(v).strip() if v is not None else "" for k, v in params.items()}
            result = fetch_data_and_save(pk, params)
            if result.get("ok"):
                return resp_ok(result)
            return resp_err(result.get("error", "获取数据失败"), code=RET_INVALID_PARAM)
        except Exception as e:
            logger.exception("Fetch data failed: %s", e)
            return resp_exception(e)


class DataSrcDetailView(APIView):
    """GET/PUT/DELETE /api/v1/data-srcs/<pk>"""

    def get(self, request: Request, pk: int):
        try:
            obj = DataSrc.objects.filter(pk=pk).first()
            if not obj:
                return resp_err("DataSrc not found", code=RET_RESOURCE_NOT_FOUND)
            return resp_ok(_data_src_to_dict(obj))
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
            if "raw_path" in data:
                obj.raw_path = (data.get("raw_path") or "").strip()
            if "raw_name" in data:
                obj.raw_name = (data.get("raw_name") or "").strip()
            if "cleaned_name" in data:
                obj.cleaned_name = (data.get("cleaned_name") or "").strip()
            if "cleaned_path" in data:
                obj.cleaned_path = (data.get("cleaned_path") or "").strip()
            if "clean_script" in data:
                obj.clean_script = (data.get("clean_script") or "").strip()
            if "fetch_mode" in data:
                obj.fetch_mode = _coerce_fetch_mode(data.get("fetch_mode"))
            if "format_type" in data:
                obj.format_type = _coerce_format_type(data.get("format_type"))
            if "name" in data:
                obj.name = (data.get("name") or "").strip()
            obj.url_params = ensure_url_params_has_placeholders(obj.src_url, obj.url_params)
            obj.save()
            return resp_ok(_data_src_to_dict(obj))
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
