from django.views.generic import TemplateView


class DashboardView(TemplateView):
    template_name = "console/dashboard.html"


class ExperimentListView(TemplateView):
    template_name = "console/experiment_list.html"


class ExperimentDetailView(TemplateView):
    template_name = "console/experiment_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["pk"] = kwargs.get("pk")
        return context


class StrategyListView(TemplateView):
    template_name = "console/strategy_list.html"


class DataSrcListView(TemplateView):
    template_name = "console/data_src_list.html"


class DataSrcDetailView(TemplateView):
    template_name = "console/data_src_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["pk"] = kwargs.get("pk")
        return context


class RawDataManagementView(TemplateView):
    template_name = "console/raw_data_management.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["data_src_id"] = self.request.GET.get("data_src_id", "")
        return context


class TrainListView(TemplateView):
    template_name = "console/train_list.html"


class TrainDetailView(TemplateView):
    template_name = "console/train_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["pk"] = kwargs.get("pk")
        return context


class ExperimentCompareView(TemplateView):
    template_name = "console/experiment_compare.html"


class ArtifactView(TemplateView):
    template_name = "console/artifact_view.html"


class WorldCupAppView(TemplateView):
    template_name = "console/worldcup_app.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            from applications.worldcup.config import get_strategy_ids
            context["wc_strategy_ids"] = ",".join(get_strategy_ids())
        except Exception:
            context["wc_strategy_ids"] = "lightgbm_match,elo_baseline,odds_baseline_group_winner"
        return context
