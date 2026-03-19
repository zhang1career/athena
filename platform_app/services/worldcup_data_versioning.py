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

from platform_app.models import DataFile, DataPatch, DataPatchBatch, FormatType
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


def data_files_by_versions(
        data_src_id: int,
        data_file_versions: List[int],
) -> List[DataFile]:
    """按 data_src_id 与精确 ct 匹配，返回多个 data_file，按 ct 升序。"""
    if not data_file_versions:
        return []
    return list(
        DataFile.objects.filter(
            data_src_id=data_src_id,
            ct__in=data_file_versions,
        ).order_by("ct", "id")
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


def _parse_json_envelope(
        text: str,
) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    若 JSON 根为对象且含 'records'，则视为信封格式，返回 (records, envelope_meta)。
    否则返回 (原样解析的记录列表, None)。
    """
    if not text or not text.strip():
        return [], None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return [], None
    if isinstance(payload, dict) and "records" in payload:
        records = payload["records"]
        if not isinstance(records, list):
            records = []
        envelope_meta = {
            k: payload[k]
            for k in ("data_type", "task", "feature_cols")
            if k in payload
        }
        return records, envelope_meta if envelope_meta else None
    # 非信封：沿用原逻辑
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)], None
    if isinstance(payload, dict):
        return [payload], None
    return [], None


def _infer_format_type(src_url: str) -> int:
    """从 URL 或路径字符串推断格式（用于从 URL 拉取时的解析）。"""
    lower = (src_url or "").lower()
    if ".xlsx" in lower:
        return FormatType.EXCEL
    if ".xls" in lower and ".xlsx" not in lower:
        return FormatType.XLS
    if lower.endswith(".csv"):
        return FormatType.CSV
    return FormatType.JSON


def _infer_format_from_path(file_path: str) -> int:
    """从 file_path 扩展名推断格式（data_file 无 format_type 时用）。"""
    return _infer_format_type(file_path or "")


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
    if format_type in (FormatType.EXCEL, FormatType.XLS):
        return []  # 二进制格式，本模块不解析
    return _load_records_from_json_text(body)


def fetch_full_records(src_url: str) -> Tuple[int, List[Dict[str, Any]]]:
    """Load records from http(s) URL or local file path. Returns (format_type_enum_id, records)."""
    format_type = _infer_format_type(src_url)
    body = _fetch_body(src_url)
    records = _load_records_by_format_type(body, format_type)
    return format_type, records


def save_full_snapshot(version_v: int, data_src_id: int):
    """仅保存元数据；数据仍在 data_src.src_url 所指位置。"""
    DataFile.objects.create(
        data_src_id=data_src_id,
        name="",
        file_path="",
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
    for k in ("record_id", "match_id", "id", "data_name", "name"):
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


def _load_records_from_data_file(file_rec: DataFile) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """从单个 DataFile 加载 records，返回 (records, envelope_meta)。"""
    envelope_meta: Optional[Dict[str, Any]] = None
    if file_rec.file_path and file_rec.file_path.strip():
        full_path = _project_root() / file_rec.file_path.strip()
        format_type = _infer_format_from_path(file_rec.file_path)
        if format_type in (FormatType.EXCEL, FormatType.XLS):
            return [], None
        body = full_path.read_text(encoding="utf-8")
        if format_type == FormatType.JSON:
            records, envelope_meta = _parse_json_envelope(body)
            return records, envelope_meta
        return _load_records_by_format_type(body, format_type), None
    resolved_url = resolve_data_src_url(file_rec.data_src)
    body = _fetch_body(resolved_url)
    format_type = _infer_format_type(resolved_url)
    if format_type == FormatType.JSON:
        records, envelope_meta = _parse_json_envelope(body)
        return records, envelope_meta
    return _load_records_by_format_type(body, format_type), None


def load_composed_records(
        data_src_id: int,
        data_file_version: Optional[int] = None,
        patch_batch_versions: Optional[List[int]] = None,
        data_file_versions: Optional[List[int]] = None,
) -> Tuple[List[Dict[str, Any]], int, int, Optional[Dict[str, Any]]]:
    """
    按版本号查询并合成数据：

    - 若 data_file_versions 非空（多版本合并）：依次加载各 ct 对应的 data_file，合并 records。
    - 否则用 data_file_version：data_src_id 匹配，ct <= data_file_version，按 ct 倒序取第 1 条。

    2) data_patch_batch：ct 精确匹配 patch_batch_versions，按 ct 升序
    3) 若为信封 JSON，用 records 做 base，并保留 envelope_meta
    4) 返回 (records, snapshot_ct, patch_count, envelope_meta)
    """
    patch_batch_versions = patch_batch_versions or []
    batches = batches_by_versions(patch_batch_versions)
    envelope_meta: Optional[Dict[str, Any]] = None
    base: List[Dict[str, Any]] = []
    snapshot_ct = 0

    if data_file_versions and len(data_file_versions) > 0:
        # 多版本合并：按 ct 升序加载并拼接 records
        file_recs = data_files_by_versions(data_src_id, data_file_versions)
        for file_rec in file_recs:
            records, meta = _load_records_from_data_file(file_rec)
            if records:
                base.extend(records)
            if meta and envelope_meta is None:
                envelope_meta = meta
            if file_rec.ct > snapshot_ct:
                snapshot_ct = file_rec.ct
    else:
        # 单版本：沿用原逻辑
        file_rec = latest_data_file_by_version(data_src_id, data_file_version or 0)
        if file_rec:
            base, envelope_meta = _load_records_from_data_file(file_rec)
            snapshot_ct = file_rec.ct

    patch_count = 0
    for batch in batches:
        patch_rows = list(DataPatch.objects.filter(batch=batch).order_by("id"))
        patch_count += len(patch_rows)
        _apply_patches(base, patch_rows)

    return base, snapshot_ct, patch_count, envelope_meta


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
        envelope_meta: Optional[Dict[str, Any]] = None,
) -> str:
    """
    写入合成数据文件。完整路径为 <dest_path>-<version>.json
    若 dest_path 为空，则使用默认路径 data/worldcup/generated/composed_{version}.json
    若 envelope_meta 非空，则写出带信封的 JSON（data_type, task, feature_cols, records）。
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
    if envelope_meta:
        payload = {**envelope_meta, "records": records}
        p.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    else:
        p.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
    return str(p)
