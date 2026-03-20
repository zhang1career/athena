"""
聚合 /api/v1 路由：按 settings 中与 service_foundation 同风格的 APP_*_ENABLED 开关挂载子模块。
仅开启 APP_WORLD_CUP_ENABLED 时不会 import urls_lab，避免拉起 pandas / LightGBM 等。
"""
from django.conf import settings
from django.urls import path

urlpatterns = []

if getattr(settings, "APP_WORLD_CUP_ENABLED", True):
    from platform_app.api.views.worldcup_views import GroupWinnerPredictionView

    urlpatterns.append(
        path("worldcup/group-winner-prediction", GroupWinnerPredictionView.as_view()),
    )

if getattr(settings, "APP_PLATFORM_LAB_ENABLED", True):
    from platform_app.urls_lab import urlpatterns as _lab_patterns

    urlpatterns.extend(_lab_patterns)
