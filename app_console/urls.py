from django.urls import path
from app_console.views import (
    DashboardView,
    ExperimentListView,
    ExperimentDetailView,
    StrategyListView,
    ExperimentCompareView,
    WorldCupAppView,
)

app_name = "console"

urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("apps/worldcup/", WorldCupAppView.as_view(), name="worldcup-app"),
    path("experiments/", ExperimentListView.as_view(), name="experiment-list"),
    path("experiments/compare/", ExperimentCompareView.as_view(), name="experiment-compare"),
    path("experiments/<int:run_id>/", ExperimentDetailView.as_view(), name="experiment-detail"),
    path("strategies/", StrategyListView.as_view(), name="strategy-list"),
]
