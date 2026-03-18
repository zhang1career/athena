"""Experiment models per DESIGN_SPECIFICATIONS §5"""
import time

from django.db import models

from .fields import JSONTextField


class ExperimentRun(models.Model):
    """Experiment run record. 使用 id 作为主键，parent_id 指向父记录的 id。"""

    class Status(models.IntegerChoices):
        PENDING = 0, "Pending"
        RUNNING = 1, "Running"
        SUCCESS = 2, "Success"
        FAILED = 3, "Failed"
        CANCELLED = 4, "Cancelled"

    name = models.CharField(max_length=255)
    strategy_id = models.CharField(max_length=128)
    params = JSONTextField(default=dict, json_type=dict)
    data_config = JSONTextField(default=dict, json_type=dict)
    status = models.SmallIntegerField(
        choices=Status.choices, default=Status.PENDING, db_index=True
    )
    parent_id = models.PositiveBigIntegerField(default=0, db_column="parent_id", help_text="父记录的 id，0 表示无父记录")
    v = models.PositiveBigIntegerField(default=0, db_column="v", help_text="数据版本号，用于复现")
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
        return f"{self.id} ({self.status_label})"


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


class FormatType:
    """数据文件格式枚举，format_type 字段存枚举 id。"""
    JSON = 1
    CSV = 2


class DataSrc(models.Model):
    """数据源的元信息。
    src_url 可为字面 URL，或带占位符的模板（如 data/budget/{year}.json）。
    url_params 为占位符名称列表，JSON 数组，每项 {"name": "占位符名"}，如 [{"name": "year"}]。
    """

    name = models.CharField(max_length=255, default="")
    src_url = models.CharField(max_length=1024, default="")
    url_params = JSONTextField(default=list, json_type=list)  # 占位符列表 [{"name": "year"}, ...]
    dest_path = models.CharField(max_length=512, default="")
    ct = models.PositiveBigIntegerField(default=0, db_column="ct")
    ut = models.PositiveBigIntegerField(default=0, db_column="ut")

    class Meta:
        db_table = "data_src"
        ordering = ["-ct"]
        app_label = "platform_app"

    def save(self, *args, **kwargs):
        now = int(time.time())
        if not self.pk and self.ct == 0:
            self.ct = now
        self.ut = now
        super().save(*args, **kwargs)


class DataFile(models.Model):
    """全量数据元信息，数据存于 data_src 所指文件。版本由 ct 提供。"""

    data_src = models.ForeignKey(
        DataSrc,
        on_delete=models.PROTECT,
        related_name="files",
    )
    format_type = models.SmallIntegerField(default=FormatType.JSON)
    ct = models.PositiveBigIntegerField(default=0, db_column="ct", help_text="创建时间(unix)，作为版本号")

    class Meta:
        db_table = "data_file"
        ordering = ["-ct"]
        app_label = "platform_app"
        indexes = [
            models.Index(fields=["ct"]),
        ]

    def save(self, *args, **kwargs):
        now = int(time.time())
        if not self.pk and self.ct == 0:
            self.ct = now
        super().save(*args, **kwargs)


class DataPatchBatch(models.Model):
    """增量补丁批次，ct 作为版本信息。"""

    ct = models.PositiveBigIntegerField(default=0, db_column="ct", help_text="创建时间(unix)，作为版本号")

    class Meta:
        db_table = "data_patch_batch"
        ordering = ["-ct"]
        app_label = "platform_app"
        indexes = [
            models.Index(fields=["ct"]),
        ]

    def save(self, *args, **kwargs):
        now = int(time.time())
        if not self.pk and self.ct == 0:
            self.ct = now
        super().save(*args, **kwargs)


class DataPatch(models.Model):
    """增量补丁 key-value 记录，通过 batch_id 关联批次。"""

    batch = models.ForeignKey(
        DataPatchBatch,
        on_delete=models.CASCADE,
        related_name="patches",
    )
    name = models.CharField(max_length=255, db_index=True)
    value = JSONTextField(default=dict, json_type=dict)

    class Meta:
        db_table = "data_patch"
        ordering = ["id"]
        app_label = "platform_app"
        indexes = [
            models.Index(fields=["batch", "name"]),
        ]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
