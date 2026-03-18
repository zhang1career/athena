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


class FormatType(models.IntegerChoices):
    """数据文件格式枚举；存于 data_src.format_type，用于「获取数据」时 html_tables 的输出格式等。"""
    JSON = 1, "JSON"
    CSV = 2, "CSV"
    EXCEL = 3, "Excel (.xlsx)"
    XLS = 4, "Excel (.xls)"


class FetchMode(models.IntegerChoices):
    """获取数据时的处理方式枚举；存于 data_src.fetch_mode。"""
    RAW = 0, "原始（保存完整响应）"
    HTML_TABLES = 1, "仅网页中的表格（提取 <table>）"


class DataSrc(models.Model):
    """数据源的元信息。
    src_url 可为字面 URL，或带占位符的模板（如 data/budget/{year}.json）。
    url_params 为占位符名称列表，JSON 数组，每项 {"name": "占位符名"}，如 [{"name": "year"}]。
    raw_name、raw_path 支持占位符，用于「获取数据」时生成 raw_data_file 的 name、file_path 并保存原始文件。
    clean_script：数据清洗脚本（Python），输入 raw_data_file，产出 data_file。
    fetch_mode：获取数据时的处理方式（FetchMode）。
    format_type：当 fetch_mode=HTML_TABLES 时，提取的表格保存为此格式（csv/xlsx/xls 等）；也作数据源默认格式。
    """
    name = models.CharField(max_length=255, default="")
    src_url = models.CharField(max_length=1024, default="")
    url_params = JSONTextField(default=list, json_type=list)  # 占位符列表 [{"name": "year"}, ...]
    raw_name = models.CharField(max_length=512, default="")  # 含占位符，替换后写入 raw_data_file.name
    raw_path = models.CharField(max_length=512, default="")  # 含占位符，替换后写入 raw_data_file.file_path 并保存原始文件
    cleaned_name = models.CharField(max_length=512, default="")  # 含占位符，替换后写入 data_file.name
    cleaned_path = models.CharField(max_length=512, default="")  # 含占位符，替换后得到 data_file.file_path 并保存清洗后文件
    clean_script = models.TextField(blank=True)  # 数据清洗脚本（Python），输入 raw_data_file 及 cleaned_name/path，产出 data_file
    fetch_mode = models.PositiveSmallIntegerField(
        choices=FetchMode.choices, default=FetchMode.RAW
    )
    format_type = models.SmallIntegerField(
        choices=FormatType.choices, default=FormatType.CSV
    )  # html_tables 时输出格式；csv/xlsx/xls
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


class RawDataFile(models.Model):
    """原始数据文件记录。由「获取数据」创建；name、file_path、args 由 params 替换 raw_name、raw_path 得到。"""

    data_src = models.ForeignKey(
        DataSrc,
        on_delete=models.PROTECT,
        related_name="raw_files",
    )
    name = models.CharField(max_length=255, default="")
    file_path = models.CharField(max_length=255, default="")
    args = models.CharField(max_length=1024, default="")  # JSON，url_params 替换参数如 {"year": "2022"}
    ct = models.PositiveBigIntegerField(default=0, db_column="ct")
    ut = models.PositiveBigIntegerField(default=0, db_column="ut")

    class Meta:
        db_table = "raw_data_file"
        ordering = ["-ct"]
        app_label = "platform_app"
        indexes = [
            models.Index(fields=["data_src_id"]),
        ]

    def save(self, *args, **kwargs):
        now = int(time.time())
        if not self.pk and self.ct == 0:
            self.ct = now
        self.ut = now
        super().save(*args, **kwargs)


class DataFile(models.Model):
    """清洗后的数据文件记录；由 clean_script 产出。name、file_path 由 save_cleaned_file 或 clean_script 创建。"""

    data_src = models.ForeignKey(
        DataSrc,
        on_delete=models.PROTECT,
        related_name="files",
    )
    raw = models.ForeignKey(
        RawDataFile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cleaned_files",
        db_column="raw_id",
    )  # 指向来源 raw_data_file
    name = models.CharField(max_length=512, default="")  # 由 clean_script 创建
    file_path = models.CharField(max_length=1024, default="")  # 清洗后文件路径
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
