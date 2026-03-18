"""DataFile 业务：按数据源列出可用版本（供前端原始数据版本下拉）。"""
from typing import List

from platform_app.repos.data_file_repo import list_ct_by_data_src_id


def list_data_file_versions(data_src_id: int) -> List[dict]:
    """
    按 data_src_id 列出 data_file 的版本（ct），倒序。
    返回 [ {"ct": 123}, ... ]，供前端多选下拉使用。
    """
    if not data_src_id:
        return []
    ct_list = list_ct_by_data_src_id(data_src_id)
    return [{"ct": ct} for ct in ct_list]
