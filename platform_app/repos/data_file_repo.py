"""DataFile repository: query by data_src_id."""
from typing import List

from platform_app.models import DataFile


def list_ct_by_data_src_id(data_src_id: int) -> List[int]:
    """
    按 data_src_id 查询 data_file 的 ct 列表，倒序（最新在前）。
    """
    if not data_src_id:
        return []
    return list(
        DataFile.objects.filter(data_src_id=data_src_id)
        .order_by("-ct")
        .values_list("ct", flat=True)
    )
