"""实验 / 策略 / 研究 / 数据 / 训练等平台 API（重依赖：pandas、LightGBM 等）。由 APP_PLATFORM_LAB_ENABLED 控制是否挂载。"""
from django.urls import path

from platform_app.api.views.experiment_views import (
    ExperimentListCreateView,
    ExperimentDetailView,
    ExperimentCancelView,
    ExperimentConfirmImprovementsView,
    ExperimentRefreshSuggestionsView,
)
from platform_app.api.views.strategy_views import StrategyListView, StrategySchemaView
from platform_app.api.views.research_views import (
    ResearchProposeView,
    ResearchRecommendationsView,
    DataPatchBatchListView,
    DataFileVersionsView,
    StartPredictionRoundView,
)
from platform_app.api.views.data_src_views import (
    DataSrcListCreateView,
    DataSrcDetailView,
    DataSrcFetchView,
)
from platform_app.api.views.raw_data_file_views import (
    RawDataFileListView,
    RawDataFileCleanView,
)
from platform_app.api.views.train_views import TrainListCreateView, TrainDetailView
from platform_app.api.views.artifact_views import ArtifactDetailView

urlpatterns = [
    path("experiments", ExperimentListCreateView.as_view()),
    path("experiments/<int:pk>/refresh-suggestions", ExperimentRefreshSuggestionsView.as_view()),
    path("experiments/<int:pk>/confirm-improvements", ExperimentConfirmImprovementsView.as_view()),
    path("experiments/<int:pk>/cancel", ExperimentCancelView.as_view()),
    path("experiments/<int:pk>", ExperimentDetailView.as_view()),
    path("strategies", StrategyListView.as_view()),
    path("strategies/<str:strategy_id>/schema", StrategySchemaView.as_view()),
    path("research/propose", ResearchProposeView.as_view()),
    path("research/recommendations", ResearchRecommendationsView.as_view()),
    path("research/data-patch-batches", DataPatchBatchListView.as_view()),
    path("research/data-file-versions", DataFileVersionsView.as_view()),
    path("research/start-prediction-round", StartPredictionRoundView.as_view()),
    path("data-srcs", DataSrcListCreateView.as_view()),
    path("data-srcs/<int:pk>/fetch", DataSrcFetchView.as_view()),
    path("data-srcs/<int:pk>", DataSrcDetailView.as_view()),
    path("raw-data-files", RawDataFileListView.as_view()),
    path("raw-data-files/<int:pk>/clean", RawDataFileCleanView.as_view()),
    path("trains", TrainListCreateView.as_view()),
    path("trains/<int:pk>", TrainDetailView.as_view()),
    path("artifacts", ArtifactDetailView.as_view()),
]
