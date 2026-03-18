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


class ExperimentCompareView(TemplateView):
    template_name = "console/experiment_compare.html"


class WorldCupAppView(TemplateView):
    template_name = "console/worldcup_app.html"
