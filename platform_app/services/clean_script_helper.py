"""clean_script 可调用的通用方法：保存清洗后文件并创建 data_file 记录。"""
import logging
import time
from pathlib import Path
from typing import Any, Dict, Union

from platform_app.models import DataFile, DataSrc, RawDataFile
from platform_app.services.data_src_url import resolve_template

logger = logging.getLogger(__name__)


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def save_cleaned_file(
    params: Dict[str, Any],
    content: Union[str, bytes],
    raw_file: RawDataFile,
    data_src: DataSrc,
    content_is_text: bool = True,
) -> DataFile:
    """
    clean_script 调用的通用方法：用 params 替换 cleaned_path、cleaned_name 占位符，
    保存 content 到路径，并创建 data_file 记录。

    Args:
        params: 占位符替换参数，如 {"year": "2022", "suffix": "matches"}
        content: 清洗后的文件内容，str 或 bytes
        raw_file: 当前 raw_data_file 记录（用于 raw_id、data_src_id）
        data_src: 数据源记录（提供 cleaned_name、cleaned_path 模板）
        content_is_text: True 时 content 按 utf-8 写入，False 时按 bytes 写入

    Returns:
        创建的 DataFile 记录
    """
    cleaned_path_tpl = (data_src.cleaned_path or "").strip()
    cleaned_name_tpl = (data_src.cleaned_name or "").strip()
    if not cleaned_path_tpl:
        raise ValueError("data_src.cleaned_path 未配置，无法保存清洗后文件")

    file_path = resolve_template(cleaned_path_tpl, params)
    if not file_path:
        raise ValueError("cleaned_path 替换后为空")

    name = resolve_template(cleaned_name_tpl, params) if cleaned_name_tpl else file_path

    full_path = Path(file_path)
    if not full_path.is_absolute():
        full_path = _project_root() / full_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    if content_is_text:
        full_path.write_text(content if isinstance(content, str) else content.decode("utf-8"), encoding="utf-8")
    else:
        path_content = content if isinstance(content, bytes) else content.encode("utf-8")
        full_path.write_bytes(path_content)

    ct = int(time.time())
    data_file = DataFile.objects.create(
        data_src_id=data_src.id,
        raw=raw_file,
        name=name,
        file_path=file_path,
        ct=ct,
    )
    logger.info("Created data_file id=%s name=%s file_path=%s from raw_id=%s", data_file.id, name, file_path, raw_file.id)
    return data_file
