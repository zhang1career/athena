"""世界杯相关 API"""
from rest_framework.views import APIView

from common.utils.http_util import resp_ok, resp_exception
from platform_app.services.group_winner_prediction import compute_group_winner_prediction


class GroupWinnerPredictionView(APIView):
    """GET /api/v1/worldcup/group-winner-prediction - 小组赛第一名预测"""

    def get(self, request):
        try:
            data = compute_group_winner_prediction()
            return resp_ok(data)
        except Exception as e:
            return resp_exception(e)
