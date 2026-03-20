"""世界杯相关 API"""
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from common.utils.http_util import resp_ok, resp_exception
from platform_app.services.group_winner_prediction import compute_group_winner_prediction
from platform_app.api.schemas.worldcup_schemas import GroupWinnerPredictionResponseSchema


class GroupWinnerPredictionView(APIView):
    """GET /api/v1/worldcup/group-winner-prediction - 小组赛第一名预测"""

    @extend_schema(
        summary="小组赛第一名预测",
        description="采用统一度量 + 简单归一化融合多个中间结果，预测各队获得小组第一的概率。数据来源：分组配置与赔率、artifacts 中的相关度 θ。",
        responses={200: GroupWinnerPredictionResponseSchema},
        tags=["世界杯预测"],
    )
    def get(self, request):
        try:
            data = compute_group_winner_prediction()
            return resp_ok(data)
        except Exception as e:
            return resp_exception(e)
