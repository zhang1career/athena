from django.contrib import admin
from .models import ExperimentRun, ExperimentMetric


@admin.register(ExperimentRun)
class ExperimentRunAdmin(admin.ModelAdmin):
    list_display = ("run_id", "name", "strategy_id", "get_status_display", "created_at")
    list_filter = ("status",)
    search_fields = ("run_id", "name")


@admin.register(ExperimentMetric)
class ExperimentMetricAdmin(admin.ModelAdmin):
    list_display = ("run", "name", "value", "step")
