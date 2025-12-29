"""
Serializers for the Analytics application.
"""

from rest_framework import serializers
from .models import (
    AnalyticsDashboard, Report, DashboardMetric,
    Alert, DataQualityCheck
)


class AnalyticsDashboardSerializer(serializers.ModelSerializer):
    """Serializer for analytics dashboards."""

    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)

    class Meta:
        model = AnalyticsDashboard
        fields = [
            'id', 'name', 'description', 'created_by', 'created_by_name',
            'organization', 'dashboard_type', 'config', 'is_public',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_by', 'created_by_name', 'created_at', 'updated_at']

    def create(self, validated_data):
        """Create dashboard with current user as creator."""
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class ReportSerializer(serializers.ModelSerializer):
    """Serializer for reports."""

    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Report
        fields = [
            'id', 'name', 'description', 'report_type', 'created_by',
            'created_by_name', 'organization', 'report_format', 'parameters',
            'filters', 'date_range_start', 'date_range_end', 'status',
            'status_display', 'file_path', 'error_message', 'generated_at',
            'is_scheduled', 'schedule_config', 'recipients', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'created_by', 'created_by_name', 'status',
            'status_display', 'file_path', 'error_message',
            'generated_at', 'created_at', 'updated_at'
        ]

    def create(self, validated_data):
        """Create report with current user as creator."""
        validated_data['created_by'] = self.context['request'].user
        validated_data['status'] = 'draft'
        return super().create(validated_data)


class DashboardMetricSerializer(serializers.ModelSerializer):
    """Serializer for dashboard metrics."""

    trend = serializers.SerializerMethodField()

    class Meta:
        model = DashboardMetric
        fields = [
            'id', 'name', 'metric_type', 'value', 'previous_value',
            'unit', 'format_type', 'icon', 'color', 'trend', 'trend_direction',
            'calculation_method', 'data_source', 'query', 'filters',
            'aggregation_period', 'refresh_interval', 'threshold_warning',
            'threshold_critical', 'is_active', 'display_order',
            'dashboard', 'organization', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_trend(self, obj):
        """Calculate trend based on current and previous values."""
        if obj.value and obj.previous_value:
            try:
                current = float(obj.value)
                previous = float(obj.previous_value)
                if previous != 0:
                    percentage = ((current - previous) / previous) * 100
                    return {
                        'direction': obj.trend_direction or ('up' if percentage > 0 else 'down'),
                        'percentage': round(percentage, 2),
                        'period': obj.aggregation_period or 'period'
                    }
            except (ValueError, TypeError):
                pass
        return {
            'direction': obj.trend_direction or 'neutral',
            'percentage': 0,
            'period': obj.aggregation_period or 'period'
        }


class AlertSerializer(serializers.ModelSerializer):
    """Serializer for alerts."""

    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Alert
        fields = [
            'id', 'name', 'description', 'alert_type', 'severity',
            'severity_display', 'status', 'status_display', 'condition',
            'threshold_value', 'current_value', 'metric', 'query',
            'triggered_at', 'resolved_at', 'acknowledged_at',
            'acknowledged_by', 'resolution_notes', 'notification_sent',
            'recipients', 'organization', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'severity_display', 'status_display',
            'triggered_at', 'resolved_at', 'acknowledged_at',
            'created_at', 'updated_at'
        ]


class DataQualityCheckSerializer(serializers.ModelSerializer):
    """Serializer for data quality checks."""

    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = DataQualityCheck
        fields = [
            'id', 'name', 'check_type', 'status', 'status_display',
            'table_name', 'column_name', 'rule', 'threshold',
            'current_score', 'passed', 'failed', 'total_records',
            'error_message', 'last_run', 'next_run', 'is_active',
            'organization', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'status_display', 'current_score', 'passed',
            'failed', 'total_records', 'error_message', 'last_run',
            'created_at', 'updated_at'
        ]


# Summary serializers for list views
class AnalyticsDashboardSummarySerializer(serializers.ModelSerializer):
    """Lightweight serializer for dashboard lists."""

    class Meta:
        model = AnalyticsDashboard
        fields = ['id', 'name', 'description', 'dashboard_type', 'is_public', 'updated_at']


class ReportSummarySerializer(serializers.ModelSerializer):
    """Lightweight serializer for report lists."""

    class Meta:
        model = Report
        fields = ['id', 'name', 'report_type', 'status', 'created_at', 'generated_at']


class DashboardMetricSummarySerializer(serializers.ModelSerializer):
    """Lightweight serializer for metric cards."""

    class Meta:
        model = DashboardMetric
        fields = ['id', 'name', 'value', 'unit', 'metric_type', 'trend_direction']


class AlertSummarySerializer(serializers.ModelSerializer):
    """Lightweight serializer for alert lists."""

    class Meta:
        model = Alert
        fields = ['id', 'name', 'alert_type', 'severity', 'status', 'triggered_at']