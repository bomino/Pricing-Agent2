"""
Admin configuration for Analytics app
"""
from django.contrib import admin
from .models import Report, DashboardMetric, Alert, AnalyticsDashboard, DataQualityCheck


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ['name', 'report_type', 'status', 'organization', 'created_by', 'created_at']
    list_filter = ['status', 'report_type', 'organization', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at', 'generated_at']
    date_hierarchy = 'created_at'


@admin.register(DashboardMetric)
class DashboardMetricAdmin(admin.ModelAdmin):
    list_display = ['name', 'metric_type', 'organization', 'current_value', 'updated_at']
    list_filter = ['metric_type', 'organization', 'updated_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ['alert_type', 'severity', 'status', 'organization', 'created_at']
    list_filter = ['status', 'severity', 'alert_type', 'organization']
    search_fields = ['title', 'message']
    readonly_fields = ['created_at', 'resolved_at']
    date_hierarchy = 'created_at'


@admin.register(AnalyticsDashboard)
class AnalyticsDashboardAdmin(admin.ModelAdmin):
    list_display = ['name', 'dashboard_type', 'is_public', 'organization', 'created_by']
    list_filter = ['dashboard_type', 'is_public', 'organization']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(DataQualityCheck)
class DataQualityCheckAdmin(admin.ModelAdmin):
    list_display = ['check_type', 'status', 'organization', 'created_at']
    list_filter = ['status', 'check_type', 'organization']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'