"""数据源「获取数据」：按 params 解析 URL 与路径，拉取数据并写入 raw_data_file 与本地文件。"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from platform_app.models import DataSrc, FormatType, RawDataFile
from platform_app.services.data_src_content_handlers import process_fetched_content
from platform_app.services.data_src_url import resolve_data_src_url, resolve_template

logger = logging.getLogger(__name__)


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _looks_like_http(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https")


def params_to_unix_timestamp(params: Dict[str, Any]) -> int:
    """
    从 params 中取 year, month, day, hour, minute, second（缺省：month=1, day=1, hour=0, minute=0, second=0），
    拼成 UTC 时间并返回 unix 时间戳。
    """
    year = params.get("year")
    if year is None or str(year).strip() == "":
        return int(datetime.now(timezone.utc).timestamp())
    try:
        y = int(year)
    except (TypeError, ValueError):
        return int(datetime.now(timezone.utc).timestamp())
    m = int(params.get("month") or 1)
    d = int(params.get("day") or 1)
    h = int(params.get("hour") or 0)
    mi = int(params.get("minute") or 0)
    s = int(params.get("second") or 0)
    dt = datetime(y, m, d, h, mi, s, tzinfo=timezone.utc)
    return int(dt.timestamp())


def _infer_format_type(url_or_path: str) -> int:
    lower = (url_or_path or "").lower()
    if ".xlsx" in lower or ".xls" in lower:
        return FormatType.EXCEL
    if lower.endswith(".csv"):
        return FormatType.CSV
    return FormatType.JSON


def _fetch_bytes(url_or_path: str) -> bytes:
    """从 http(s) URL 或本地路径拉取原始字节。"""
    if _looks_like_http(url_or_path):
        req = Request(url_or_path, headers={"User-Agent": "athena/1.0"})
        with urlopen(req, timeout=60) as resp:
            return resp.read()
    p = Path(url_or_path)
    if not p.is_absolute():
        p = _project_root() / p
    if not p.exists():
        raise FileNotFoundError(f"Data source not found: {p}")
    return p.read_bytes()


def fetch_data_and_save(data_src_id: int, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    根据 data_src 与 params：
    1) 解析 src_url 得到实际 URL，拉取数据（字节）
    2) 用 params 计算 unix 时间戳 ct
    3) 解析 raw_name、raw_path 得到 raw_data_file.name、file_path 及保存路径
    4) 将数据写入该路径，并创建 RawDataFile 记录。
    返回 {"ok": True, "raw_data_file_id": id, "file_path": "...", "ct": ct} 或 {"ok": False, "error": "..."}。
    """
    try:
        data_src = DataSrc.objects.get(pk=data_src_id)
    except DataSrc.DoesNotExist:
        return {"ok": False, "error": "数据源不存在"}

    resolved_url = resolve_data_src_url(data_src, overrides=params)
    if not resolved_url or not resolved_url.strip():
        return {"ok": False, "error": "src_url 解析后为空"}

    raw_path_template = (data_src.raw_path or "").strip()
    raw_name_template = (data_src.raw_name or "").strip()
    if not raw_path_template:
        return {"ok": False, "error": "请配置 raw_path"}

    try:
        raw = _fetch_bytes(resolved_url)
    except FileNotFoundError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:
        logger.exception("Fetch failed: %s", e)
        return {"ok": False, "error": f"拉取失败: {e}"}

    fetch_mode = data_src.fetch_mode
    output_format_type = data_src.format_type
    try:
        out_bytes, suggested_ext, _ = process_fetched_content(
            fetch_mode, raw, resolved_url, output_format_type
        )
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:
        logger.exception("Content process failed: %s", e)
        return {"ok": False, "error": f"内容处理失败: {e}"}

    ct = params_to_unix_timestamp(params)
    resolved_raw_path = resolve_template(raw_path_template, params)
    resolved_raw_name = resolve_template(raw_name_template, params) if raw_name_template else resolved_raw_path

    # 若处理后的文件需要扩展名（如 html_tables 得到 .xlsx），且当前路径未带该扩展名，则追加
    if suggested_ext and not (resolved_raw_path.lower().endswith(suggested_ext.lower())):
        resolved_raw_path = resolved_raw_path.rstrip("/") + suggested_ext

    full_path = Path(resolved_raw_path)
    if not full_path.is_absolute():
        full_path = _project_root() / full_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(out_bytes)

    args_json = json.dumps(params, ensure_ascii=False) if params else "{}"
    raw_file = RawDataFile.objects.create(
        data_src_id=data_src_id,
        name=resolved_raw_name,
        file_path=resolved_raw_path,
        args=args_json,
        ct=ct,
    )
    return {
        "ok": True,
        "raw_data_file_id": raw_file.id,
        "file_path": resolved_raw_path,
        "name": resolved_raw_name,
        "ct": ct,
    }
