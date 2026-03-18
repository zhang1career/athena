"""数据源 URL 解析：固定 schema + 可变参数。

src_url 可写为模板，占位符为 {param_name}。url_params 为占位符名称列表 [{"name": "year"}, ...]；
取值由 overrides 在获取数据时传入，如 overrides={"year": "2024"}。
"""
import re
from typing import Any, Dict, List, Optional

from platform_app.models import DataSrc


# 匹配 {name} 形式的占位符，name 为字母、数字、下划线
_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z0-9_]+)\}")


def normalize_url_params_list(url_params: list) -> List[Dict[str, str]]:
    """将 url_params 规范为 [{"name": "xxx"}, ...]，仅接受 list。"""
    if not isinstance(url_params, list):
        return []
    out = []
    for item in url_params:
        if isinstance(item, dict) and isinstance(item.get("name"), str):
            out.append({"name": item["name"]})
        elif isinstance(item, str):
            out.append({"name": item})
    return out


def _names_from_url_params_list(url_params: List[Dict[str, str]]) -> set:
    """从 [{"name": "xxx"}] 中取出 name 集合。"""
    return {item["name"] for item in url_params if isinstance(item.get("name"), str)}


def resolve_data_src_url(
    data_src: DataSrc,
    overrides: Optional[Dict[str, Any]] = None,
) -> str:
    """根据数据源的 src_url 模板与 overrides 解析出最终 URL。

    - 若 src_url 中无 {xxx}，直接返回 src_url。
    - 若有占位符，用 overrides 中的值填充；未提供值的占位符保留原样。

    Args:
        data_src: DataSrc 实例。
        overrides: 本次请求的参数值，如 {"year": "2024"}。

    Returns:
        可用来拉取数据的最终 URL 字符串。
    """
    template = (data_src.src_url or "").strip()
    if not template:
        return ""

    params = dict(overrides or {})

    if not _PLACEHOLDER_RE.search(template):
        return template

    def repl(m: re.Match) -> str:
        key = m.group(1)
        value = params.get(key)
        if value is None:
            return m.group(0)
        return str(value)

    return _PLACEHOLDER_RE.sub(repl, template)


def list_url_placeholders(src_url: str) -> list:
    """从 src_url 模板中解析出占位符名列表，便于前端展示或校验。"""
    if not src_url or not src_url.strip():
        return []
    return list(dict.fromkeys(_PLACEHOLDER_RE.findall(src_url or "")))


def ensure_url_params_has_placeholders(
    src_url: str,
    url_params: List[Dict[str, str]],
) -> List[Dict[str, str]]:
    """根据 src_url 中的占位符补全 url_params：占位符名若不在列表中则追加 {"name": "占位符名"}。"""
    current = list(url_params) if url_params else []
    existing = _names_from_url_params_list(current)
    result = list(current)
    for name in list_url_placeholders(src_url):
        if name not in existing:
            result.append({"name": name})
            existing.add(name)
    return result
