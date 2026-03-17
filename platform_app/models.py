"""Experiment models per DESIGN_SPECIFICATIONS §5"""
import time

from django.db import models

from .fields import JSONTextField


class ExperimentRun(models.Model):
    """Experiment run record."""

    class Status(models.IntegerChoices):
        PENDING = 0, "Pending"
        RUNNING = 1, "Running"
        SUCCESS = 2, "Success"
        FAILED = 3, "Failed"
        CANCELLED = 4, "Cancelled"

    run_id = models.BigIntegerField(unique=True, db_index=True)
    name = models.CharField(max_length=255)
    strategy_id = models.CharField(max_length=128)
    params = JSONTextField(default=dict, json_type=dict)
    data_config = JSONTextField(default=dict, json_type=dict)
    status = models.SmallIntegerField(
        choices=Status.choices, default=Status.PENDING, db_index=True
    )
    parent_id = models.PositiveBigIntegerField(default=0, db_column="parent_id")
    metrics = JSONTextField(default=dict, json_type=dict)
    artifacts = JSONTextField(default=list, json_type=list)
    ct = models.PositiveBigIntegerField(default=0, db_column="ct")
    ut = models.PositiveBigIntegerField(default=0, db_column="ut")
    error_message = models.TextField(blank=True)

    class Meta:
        db_table = "plat_exp_run"
        ordering = ["-ct"]
        app_label = "platform_app"

    def save(self, *args, **kwargs):
        now = int(time.time())
        if not self.pk and self.ct == 0:
            self.ct = now
        self.ut = now
        super().save(*args, **kwargs)

    @property
    def created_at(self):
        """Datetime from ct (unix timestamp) for API compatibility."""
        if self.ct and self.ct > 0:
            from datetime import datetime
            return datetime.fromtimestamp(self.ct)
        return None

    @property
    def updated_at(self):
        """Datetime from ut (unix timestamp) for API compatibility."""
        if self.ut and self.ut > 0:
            from datetime import datetime
            return datetime.fromtimestamp(self.ut)
        return None

    @property
    def parent(self):
        """Parent run when parent_id > 0, else None."""
        if not self.parent_id:
            return None
        try:
            return ExperimentRun.objects.get(pk=self.parent_id)
        except ExperimentRun.DoesNotExist:
            return None

    @property
    def status_label(self):
        """API/display: PENDING, RUNNING, etc."""
        try:
            return self.Status(self.status).name
        except ValueError:
            return "UNKNOWN"

    def __str__(self):
        return f"{self.run_id} ({self.status_label})"


class ExperimentMetric(models.Model):
    """Per-run metric for curves and scalar values."""

    run = models.ForeignKey(
        ExperimentRun, on_delete=models.CASCADE, related_name="metric_records"
    )
    name = models.CharField(max_length=128)
    value = models.FloatField()
    step = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "plat_exp_metric"
        app_label = "platform_app"
        indexes = [
            models.Index(fields=["run", "name"]),
        ]
