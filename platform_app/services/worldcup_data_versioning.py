"""Worldcup data versioning: full snapshot + incremental patches."""
import csv
import io
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from platform_app.models import DataFile, DataPatch, DataPatchBatch, DataSrc, FormatType
from platform_app.services.data_src_url import resolve_data_src_url

logger = logging.getLogger(__name__)


def now_version_v() -> int:
    return int(time.time())


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def latest_data_file_by_version(
    data_src_id: int,
    data_file_version: int,
) -> Optional[DataFile]:
    """data_file 最近记录：data_src_id 匹配，ct <= data_file_version，按 ct 倒序取第 1 条。"""
    return (
        DataFile.objects.filter(data_src_id=data_src_id, ct__lte=data_file_version)
        .order_by("-ct", "-id")
        .first()
    )


def batches_by_versions(patch_batch_versions: List[int]) -> List[DataPatchBatch]:
    """data_patch_batch 精确匹配多个版本号，按 ct 升序排列。"""
    if not patch_batch_versions:
        return []
    return list(
        DataPatchBatch.objects.filter(ct__in=patch_batch_versions).order_by("ct", "id")
    )


def _looks_like_http(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https")


def _load_records_from_csv_text(text: str) -> List[Dict[str, Any]]:
    f = io.StringIO(text)
    reader = csv.DictReader(f)
    return [dict(r) for r in reader]


def _load_records_from_json_text(text: str) -> List[Dict[str, Any]]:
    if not text or not text.strip():
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        return [payload]
    raise ValueError("JSON payload must be object or array")


def _infer_format_type(src_url: str) -> int:
    lower = src_url.lower()
    if lower.endswith(".csv"):
        return FormatType.CSV
    return FormatType.JSON


def _fetch_body(src_url: str) -> str:
    """Fetch file content from http(s) URL or local path."""
    if _looks_like_http(src_url):
        req = Request(src_url, headers={"User-Agent": "athena-worldcup/1.0"})
        with urlopen(req, timeout=20) as resp:
            return resp.read().decode("utf-8")
    p = Path(src_url)
    if not p.is_absolute():
        p = _project_root() / p
    if not p.exists():
        raise FileNotFoundError(f"Data source not found: {p}")
    return p.read_text(encoding="utf-8")


def _load_records_by_format_type(body: str, format_type: int) -> List[Dict[str, Any]]:
    if format_type == FormatType.CSV:
        return _load_records_from_csv_text(body)
    return _load_records_from_json_text(body)


def fetch_full_records(src_url: str) -> Tuple[int, List[Dict[str, Any]]]:
    """Load records from http(s) URL or local file path. Returns (format_type_enum_id, records)."""
    format_type = _infer_format_type(src_url)
    body = _fetch_body(src_url)
    records = _load_records_by_format_type(body, format_type)
    return format_type, records


def save_full_snapshot(version_v: int, data_src_id: int, format_type: int):
    """Save metadata only. Data stays in file at data_src.src_url."""
    DataFile.objects.create(
        data_src_id=data_src_id,
        format_type=format_type,
        ct=version_v,
    )


def save_incremental_patches(version_v: int, patch_dict: Dict[str, Any]) -> int:
    """Create batch and patches. Returns patch count."""
    batch = DataPatchBatch.objects.create(ct=version_v)
    count = 0
    for k, v in (patch_dict or {}).items():
        if not isinstance(k, str) or not k.strip():
            continue
        payload = v if isinstance(v, dict) else {"value": v}
        DataPatch.objects.create(
            batch=batch,
            name=k.strip(),
            value=payload,
        )
        count += 1
    return count


def _record_key(rec: Dict[str, Any]) -> str:
    if not isinstance(rec, dict):
        return ""
    for k in ("match_id", "id", "data_name", "name"):
        v = rec.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    return ""


def _apply_patches(base: List[Dict[str, Any]], patch_rows: List[DataPatch]) -> None:
    """In-place: 用 patch 覆盖 base 中同名记录，或追加新记录。"""
    idx = {}
    for i, rec in enumerate(base):
        key = _record_key(rec)
        if key:
            idx[key] = i
    for p in patch_rows:
        key = p.name
        val = p.value or {}
        if key in idx:
            merged = dict(base[idx[key]])
            if isinstance(val, dict):
                merged.update(val)
            base[idx[key]] = merged
        else:
            new_rec = {"match_id": key}
            if isinstance(val, dict):
                new_rec.update(val)
            base.append(new_rec)
            idx[key] = len(base) - 1


def load_composed_records(
    data_src_id: int,
    data_file_version: int,
    patch_batch_versions: List[int],
) -> Tuple[List[Dict[str, Any]], int, int]:
    """
    按版本号查询并合成数据：
    1) data_file：data_src_id 匹配，ct <= data_file_version，按 ct 倒序取第 1 条
    2) data_patch_batch：ct 精确匹配 patch_batch_versions，按 ct 升序
    3) 按 batch 的 ct 分组找到 data_patch，按 ct 顺序依次覆盖 base
    4) 返回合成结果
    """
    file_rec = latest_data_file_by_version(data_src_id, data_file_version)
    batches = batches_by_versions(patch_batch_versions)

    if file_rec:
        resolved_url = resolve_data_src_url(file_rec.data_src)
        body = _fetch_body(resolved_url)
        base = _load_records_by_format_type(body, file_rec.format_type)
        snapshot_ct = file_rec.ct
    else:
        base = []
        snapshot_ct = 0

    patch_count = 0
    for batch in batches:
        patch_rows = list(DataPatch.objects.filter(batch=batch).order_by("id"))
        patch_count += len(patch_rows)
        _apply_patches(base, patch_rows)

    return base, snapshot_ct, patch_count


def list_patch_batches() -> List[Dict[str, Any]]:
    """列出所有 data_patch_batch，用于前端复选框。"""
    from django.db.models import Count
    return list(
        DataPatchBatch.objects.annotate(patch_count=Count("patches"))
        .order_by("-ct")
        .values("ct", "patch_count")
    )


def write_composed_records_file(
    version_v: int,
    records: List[Dict[str, Any]],
    dest_path: str = "",
) -> str:
    """
    写入合成数据文件。完整路径为 <dest_path>-<version>.json
    若 dest_path 为空，则使用默认路径 data/worldcup/generated/composed_{version}.json
    """
    if dest_path and dest_path.strip():
        base = Path(dest_path.strip())
        if not base.is_absolute():
            base = _project_root() / base
        p = Path(str(base) + f"-{version_v}.json")
    else:
        out_dir = _project_root() / "data" / "worldcup" / "generated"
        out_dir.mkdir(parents=True, exist_ok=True)
        p = out_dir / f"composed_{version_v}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
    return str(p)
