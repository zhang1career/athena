from django.urls import path

from platform_app.api.views.experiment_views import (
    ExperimentListCreateView,
    ExperimentDetailView,
    ExperimentCancelView,
    ExperimentConfirmImprovementsView,
)
from platform_app.api.views.strategy_views import StrategyListView, StrategySchemaView
from platform_app.api.views.research_views import (
    ResearchProposeView,
    ResearchRecommendationsView,
    DataPatchBatchListView,
    DataFileVersionsView,
    StartPredictionRoundView,
)
from platform_app.api.views.data_src_views import DataSrcListCreateView, DataSrcDetailView

urlpatterns = [
    path("experiments", ExperimentListCreateView.as_view()),
    path("experiments/<int:pk>", ExperimentDetailView.as_view()),
    path("experiments/<int:pk>/cancel", ExperimentCancelView.as_view()),
    path("experiments/<int:pk>/confirm-improvements", ExperimentConfirmImprovementsView.as_view()),
    path("strategies", StrategyListView.as_view()),
    path("strategies/<str:strategy_id>/schema", StrategySchemaView.as_view()),
    path("research/propose", ResearchProposeView.as_view()),
    path("research/recommendations", ResearchRecommendationsView.as_view()),
    path("research/data-patch-batches", DataPatchBatchListView.as_view()),
    path("research/data-file-versions", DataFileVersionsView.as_view()),
    path("research/start-prediction-round", StartPredictionRoundView.as_view()),
    path("data-srcs", DataSrcListCreateView.as_view()),
    path("data-srcs/<int:pk>", DataSrcDetailView.as_view()),
]
