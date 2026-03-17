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
    StartPredictionRoundView,
)

urlpatterns = [
    path("experiments", ExperimentListCreateView.as_view()),
    path("experiments/<int:run_id>", ExperimentDetailView.as_view()),
    path("experiments/<int:run_id>/cancel", ExperimentCancelView.as_view()),
    path("experiments/<int:run_id>/confirm-improvements", ExperimentConfirmImprovementsView.as_view()),
    path("strategies", StrategyListView.as_view()),
    path("strategies/<str:strategy_id>/schema", StrategySchemaView.as_view()),
    path("research/propose", ResearchProposeView.as_view()),
    path("research/recommendations", ResearchRecommendationsView.as_view()),
    path("research/start-prediction-round", StartPredictionRoundView.as_view()),
]
