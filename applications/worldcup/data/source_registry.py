"""
数据源注册表：人设计配置 → AI 辅助设计 → AI 实现 Loader

- 人设计：data_sources.yaml 定义数据源列表、类型、路径
- AI 辅助：field_mapping、ETL 流程建议
- AI 实现：各 type 对应 Loader（file 已实现，api 等可扩展）
"""
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "data_sources.yaml"
_SOURCES: Optional[List[Dict[str, Any]]] = None


def _load_config() -> List[Dict[str, Any]]:
    """加载 data_sources.yaml 配置"""
    global _SOURCES
    if _SOURCES is not None:
        return _SOURCES
    if not _CONFIG_PATH.exists():
        logger.warning("Data sources config not found: %s", _CONFIG_PATH)
        _SOURCES = []
        return _SOURCES
    try:
        import yaml
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        _SOURCES = data.get("sources") or []
        return _SOURCES
    except Exception as e:
        logger.exception("Failed to load data_sources.yaml: %s", e)
        _SOURCES = []
        return _SOURCES


def list_sources() -> List[Dict[str, Any]]:
    """列出所有配置的数据源"""
    return _load_config()


def get_source(source_id: str) -> Optional[Dict[str, Any]]:
    """根据 source_id 获取数据源配置"""
    for s in _load_config():
        if s.get("id") == source_id:
            return s
    return None


def source_to_data_config(source_id: str, overrides: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    将 source_id 转换为 data_config，供 worldcup_data_loader 使用。
    便于实验创建时指定 source_id 而非手写 path/format。
    """
    src = get_source(source_id)
    if not src:
        raise ValueError(f"Unknown source_id: {source_id}")

    cfg: Dict[str, Any] = {}
    if src.get("type") == "file":
        path = src.get("path")
        if path and not Path(path).is_absolute():
            base = Path(__file__).resolve().parent.parent.parent.parent
            path = str(base / path)
        cfg["path"] = path
        cfg["format"] = src.get("format", "csv")
    else:
        raise ValueError(f"Unsupported source type: {src.get('type')}")

    cfg.update(overrides or {})
    return cfg
