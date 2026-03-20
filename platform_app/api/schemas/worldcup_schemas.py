"""
OpenAPI schemas for World Cup prediction API.
Used by drf-spectacular for Swagger documentation.
"""
from rest_framework import serializers


class ThetaInfoSchema(serializers.Serializer):
    """θ (theta) correlation metrics from artifact."""

    auc = serializers.FloatField(help_text="AUC")
    brier = serializers.FloatField(help_text="Brier score")
    spearman = serializers.FloatField(help_text="Spearman correlation")
    suggested_weight = serializers.FloatField(help_text="建议权重")


class GroupSummarySchema(serializers.Serializer):
    """Single group predicted winner summary."""

    group = serializers.CharField(help_text="组别，如 A、B")
    winner = serializers.CharField(help_text="预测第一名球队")
    winner_proba = serializers.FloatField(help_text="该队融合概率")


class GroupWinnerRecordSchema(serializers.Serializer):
    """Single team record in detailed table."""

    group = serializers.CharField(help_text="组别")
    team = serializers.CharField(help_text="球队")
    odds_proba = serializers.FloatField(help_text="赔率隐含概率")
    fused_proba = serializers.FloatField(help_text="融合后概率")
    is_predicted_winner = serializers.BooleanField(help_text="是否为预测第一名")


class GroupWinnerPredictionDataSchema(serializers.Serializer):
    """Response data for group-winner-prediction."""

    edition = serializers.CharField(allow_null=True, help_text="届别，如 2022")
    theta = ThetaInfoSchema(allow_null=True, help_text="相关度 θ，未加载 artifact 时为 null")
    groups_summary = GroupSummarySchema(many=True, help_text="各组预测第一摘要")
    records = GroupWinnerRecordSchema(many=True, help_text="详细预测表格")


class GroupWinnerPredictionResponseSchema(serializers.Serializer):
    """Full API response wrapper for group-winner-prediction."""

    errorCode = serializers.IntegerField(help_text="0 表示成功")
    message = serializers.CharField(help_text="错误信息，成功时为空")
    data = GroupWinnerPredictionDataSchema(allow_null=True, help_text="预测数据")
