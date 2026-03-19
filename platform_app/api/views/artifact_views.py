"""Artifact API: load artifact content for visualization."""
import os
import re
from pathlib import Path

from django.conf import settings
from rest_framework.views import APIView
from rest_framework.request import Request

from common.utils.http_util import resp_ok, resp_err, resp_exception
from common.consts.response_const import RET_INVALID_PARAM, RET_RESOURCE_NOT_FOUND


# 安全文件名：仅允许字母数字、下划线、连字符、点
_SAFE_FILENAME_RE = re.compile(r"^[a-zA-Z0-9_\-\.]+$")


def _get_artifact_path(filename: str) -> str | None:
    """返回 artifact 文件绝对路径，校验安全；非法则返回 None。"""
    if not filename or not _SAFE_FILENAME_RE.match(filename):
        return None
    if ".." in filename or "/" in filename or "\\" in filename:
        return None
    root = getattr(settings, "RESOURCE_ROOT", None)
    if not root:
        base = getattr(settings, "BASE_DIR", Path(__file__).resolve().parent.parent.parent.parent)
        root = str(Path(base) / "resources")
    root = str(root)
    artifacts_dir = os.path.realpath(os.path.join(root, "artifacts"))
    path = os.path.realpath(os.path.join(artifacts_dir, filename))
    if not path.startswith(artifacts_dir):
        return None
    return path


class ArtifactDetailView(APIView):
    """GET /api/v1/artifacts?filename=xxx.pkl - 读取 artifact 内容，用于可视化。"""

    def get(self, request: Request):
        filename = (request.GET.get("filename") or "").strip()
        if not filename:
            return resp_err("filename required", code=RET_INVALID_PARAM)
        if not filename.endswith(".pkl"):
            filename = filename + ".pkl"
        path = _get_artifact_path(filename)
        if not path or not os.path.isfile(path):
            return resp_err("Artifact not found", code=RET_RESOURCE_NOT_FOUND)
        try:
            import joblib
            obj = joblib.load(path)
        except Exception as e:
            return resp_err(f"Failed to load artifact: {e}", code=RET_RESOURCE_NOT_FOUND)
        # 转为可 JSON 序列化的结构
        if isinstance(obj, dict):
            out = dict(obj)
            # 浮点数保留可读格式
            for k, v in out.items():
                if isinstance(v, float):
                    out[k] = round(v, 6)
            if "theta" in out and isinstance(out["theta"], dict):
                for k, v in list(out["theta"].items()):
                    if isinstance(v, float):
                        out["theta"][k] = round(v, 6)
        else:
            out = {"raw_type": type(obj).__name__, "message": "Non-dict artifact, visualization not available"}
        return resp_ok({"artifact": out, "filename": filename})
