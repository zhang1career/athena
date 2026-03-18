"""RawDataFile API: list by data_src_id, clean (execute clean_script)."""
import json
import logging
from pathlib import Path
from typing import Any, Dict

from django.conf import settings
from rest_framework.views import APIView
from rest_framework.request import Request

from common.utils.http_util import resp_ok, resp_err, resp_exception
from common.consts.response_const import RET_INVALID_PARAM, RET_RESOURCE_NOT_FOUND

from platform_app.models import DataFile, DataSrc, RawDataFile
from platform_app.services.clean_script_helper import save_cleaned_file

logger = logging.getLogger(__name__)


def _project_root() -> Path:
    """与 Django BASE_DIR 一致的项目根路径。"""
    return Path(settings.BASE_DIR)


def _raw_data_file_to_dict(obj: RawDataFile) -> Dict[str, Any]:
    return {
        "id": obj.id,
        "data_src_id": obj.data_src_id,
        "name": obj.name or "",
        "file_path": obj.file_path or "",
        "args": obj.args or "{}",
        "ct": obj.ct,
        "ut": obj.ut,
    }


class RawDataFileListView(APIView):
    """GET /api/v1/raw-data-files?data_src_id=123 - 按数据源列出 raw_data_file。"""

    def get(self, request: Request):
        try:
            data_src_id = request.GET.get("data_src_id", "").strip()
            if not data_src_id:
                return resp_err("data_src_id required", code=RET_INVALID_PARAM)
            try:
                sid = int(data_src_id)
            except ValueError:
                return resp_err("data_src_id must be integer", code=RET_INVALID_PARAM)

            qs = RawDataFile.objects.filter(data_src_id=sid).order_by("-ct", "-id")
            items = [_raw_data_file_to_dict(r) for r in qs]
            return resp_ok({"items": items})
        except Exception as e:
            logger.exception("List raw_data_files failed: %s", e)
            return resp_exception(e)


class RawDataFileCleanView(APIView):
    """POST /api/v1/raw-data-files/<pk>/clean - 执行 data_src.clean_script，输入当前 raw_data_file。"""

    def post(self, request: Request, pk: int):
        try:
            raw_file = RawDataFile.objects.filter(pk=pk).select_related("data_src").first()
            if not raw_file:
                return resp_err("RawDataFile not found", code=RET_RESOURCE_NOT_FOUND)

            data_src = raw_file.data_src
            clean_script = (data_src.clean_script or "").strip()
            if not clean_script:
                return resp_err("该数据源未配置 clean_script，无法执行清洗", code=RET_INVALID_PARAM)

            # 脚本入参：raw_data_file.file_path、args，以及 data_src.cleaned_name、cleaned_path
            try:
                args_parsed = json.loads(raw_file.args) if raw_file.args else {}
            except json.JSONDecodeError:
                args_parsed = {}

            # 执行 clean_script（Python 代码）
            # 脚本可调用 save_cleaned_file(params, content, raw_file, data_src) 保存并创建 data_file
            # 提供 resolve_raw_path：将 file_path 解析为绝对路径，供脚本使用
            _root = _project_root()

            def _resolve_raw_path(fp: str) -> Path:
                fp = (fp or "").strip()
                if not fp:
                    return _root / "resources/data/football/odds-worldcup-group-2022.csv"
                p = Path(fp)
                if p.is_absolute():
                    return p.resolve()
                return (_root / fp).resolve()

            _globals = {
                "file_path": raw_file.file_path or "",
                "args": args_parsed,
                "cleaned_name": data_src.cleaned_name or "",
                "cleaned_path": data_src.cleaned_path or "",
                "save_cleaned_file": lambda params, content, text=True: save_cleaned_file(
                    params, content, raw_file, data_src, content_is_text=text
                ),
                "DataFile": DataFile,
                "DataSrc": DataSrc,
                "RawDataFile": RawDataFile,
                "raw_file": raw_file,
                "data_src": data_src,
                "data_src_id": data_src.id,
                "project_root": _root,
                "resolve_raw_path": _resolve_raw_path,
                "json": json,
            }

            try:
                exec(compile(clean_script, "<clean_script>", "exec"), _globals)
            except Exception as e:
                logger.exception("clean_script execution failed: %s", e)
                return resp_err(f"清洗脚本执行失败: {e}", code=RET_INVALID_PARAM)

            return resp_ok({"ok": True, "message": "清洗完成"})
        except Exception as e:
            logger.exception("Clean raw_data_file failed: %s", e)
            return resp_exception(e)
