from django.urls import path
from app_console.views import (
    DashboardView,
    ExperimentListView,
    ExperimentDetailView,
    StrategyListView,
    DataSrcListView,
    DataSrcDetailView,
    RawDataManagementView,
    TrainListView,
    TrainDetailView,
    ExperimentCompareView,
    WorldCupAppView,
)

app_name = "console"

urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("apps/worldcup/", WorldCupAppView.as_view(), name="worldcup-app"),
    path("experiments/", ExperimentListView.as_view(), name="experiment-list"),
    path("experiments/compare/", ExperimentCompareView.as_view(), name="experiment-compare"),
    path("experiments/<int:pk>/", ExperimentDetailView.as_view(), name="experiment-detail"),
    path("strategies/", StrategyListView.as_view(), name="strategy-list"),
    path("data-srcs/", DataSrcListView.as_view(), name="data-src-list"),
    path("data-srcs/<int:pk>/", DataSrcDetailView.as_view(), name="data-src-detail"),
    path("raw-data/", RawDataManagementView.as_view(), name="raw-data"),
    path("trains/", TrainListView.as_view(), name="train-list"),
    path("trains/<int:pk>/", TrainDetailView.as_view(), name="train-detail"),
]
