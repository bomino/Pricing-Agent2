"""
Pricing app admin interface
"""
from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Avg, Max, Min
from django.utils import timezone
from datetime import timedelta
from .models import (
    Material, Price, PricePrediction, PriceAlert, PriceBenchmark,
    Category, PriceHistory
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Category admin interface"""
    list_display = ['name', 'organization', 'material_count', 'created_at']
    list_filter = ['organization', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    def material_count(self, obj):
        """Display count of materials in this category"""
        count = obj.materials.count()
        return format_html('<span style="color: #006eb8;">{}</span>', count)
    material_count.short_description = 'Materials'


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    """Material admin interface"""
    list_display = [
        'name', 'category', 'organization', 'unit_of_measure',
        'price_count', 'latest_price', 'is_active', 'created_at'
    ]
    list_filter = [
        'organization', 'category', 'unit_of_measure',
        'is_active', 'created_at'
    ]
    search_fields = ['name', 'description', 'specification']
    readonly_fields = ['created_at', 'updated_at', 'price_count', 'latest_price']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'category', 'organization')
        }),
        ('Specifications', {
            'fields': ('specification', 'unit_of_measure', 'sku_code')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('price_count', 'latest_price'),
            'classes': ('collapse',)
        })
    )
    
    def price_count(self, obj):
        """Display count of prices for this material"""
        count = obj.prices.count()
        return format_html('<span style="color: #006eb8;">{}</span>', count)
    price_count.short_description = 'Price Records'
    
    def latest_price(self, obj):
        """Display latest price for this material"""
        latest = obj.prices.order_by('-time').first()
        if latest:
            return format_html(
                '<span style="color: #28a745;">{:.2f} {}</span>',
                latest.price, latest.currency
            )
        return '-'
    latest_price.short_description = 'Latest Price'
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related(
            'organization', 'category', 'created_by'
        ).prefetch_related('prices')


class PriceHistoryInline(admin.TabularInline):
    """Price history inline for Material admin"""
    model = PriceHistory
    extra = 0
    readonly_fields = ['created_at']
    fields = ['price', 'currency', 'source', 'created_at']
    ordering = ['-created_at']
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Price)
class PriceAdmin(admin.ModelAdmin):
    """Price admin interface"""
    list_display = [
        'material', 'price', 'currency', 'source',
        'confidence_score', 'time', 'organization'
    ]
    list_filter = [
        'organization', 'currency', 'source', 'material__category',
        'time', 'confidence_score'
    ]
    search_fields = [
        'material__name', 'source', 'notes'
    ]
    readonly_fields = ['created_at']
    date_hierarchy = 'time'
    
    fieldsets = (
        ('Price Information', {
            'fields': ('material', 'price', 'currency', 'source')
        }),
        ('Quality', {
            'fields': ('confidence_score', 'data_quality_score')
        }),
        ('Timing', {
            'fields': ('time', 'created_at')
        }),
        ('Additional Information', {
            'fields': ('notes', 'metadata'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related(
            'material', 'organization'
        )


@admin.register(PricePrediction)
class PricePredictionAdmin(admin.ModelAdmin):
    """Price prediction admin interface"""
    list_display = [
        'material', 'predicted_price', 'confidence_interval',
        'prediction_horizon_days', 'accuracy_score', 'status', 'created_at'
    ]
    list_filter = [
        'organization', 'status', 'material__category',
        'prediction_horizon_days', 'created_at'
    ]
    search_fields = ['material__name']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Prediction', {
            'fields': (
                'material', 'predicted_price', 'confidence_interval',
                'prediction_horizon_days'
            )
        }),
        ('Model Information', {
            'fields': ('model_version', 'accuracy_score', 'model_confidence')
        }),
        ('Status', {
            'fields': ('status',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related(
            'material', 'organization'
        )


@admin.register(PriceAlert)
class PriceAlertAdmin(admin.ModelAdmin):
    """Price alert admin interface"""
    list_display = [
        'material', 'alert_type', 'threshold_value',
        'is_active', 'triggered_count', 'created_by', 'created_at'
    ]
    list_filter = [
        'organization', 'alert_type', 'is_active',
        'material__category', 'created_at'
    ]
    search_fields = ['material__name', 'created_by__username']
    readonly_fields = ['triggered_count', 'last_triggered_at', 'created_at']
    
    fieldsets = (
        ('Alert Configuration', {
            'fields': (
                'material', 'alert_type', 'threshold_value',
                'threshold_percentage'
            )
        }),
        ('Notifications', {
            'fields': ('notification_emails', 'webhook_url')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Statistics', {
            'fields': ('triggered_count', 'last_triggered_at'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related(
            'material', 'organization', 'created_by'
        )


@admin.register(PriceBenchmark)
class PriceBenchmarkAdmin(admin.ModelAdmin):
    """Price benchmark admin interface"""
    list_display = [
        'material', 'benchmark_type', 'benchmark_value',
        'percentile', 'valid_from', 'valid_to'
    ]
    list_filter = [
        'organization', 'benchmark_type', 'material__category',
        'valid_from', 'valid_to'
    ]
    search_fields = ['material__name', 'source']
    
    fieldsets = (
        ('Benchmark Information', {
            'fields': (
                'material', 'benchmark_type', 'benchmark_value',
                'percentile', 'source'
            )
        }),
        ('Validity Period', {
            'fields': ('valid_from', 'valid_to')
        }),
        ('Statistics', {
            'fields': ('sample_size', 'standard_deviation'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related(
            'material', 'organization'
        )


@admin.register(PriceHistory)
class PriceHistoryAdmin(admin.ModelAdmin):
    """Price history admin interface"""
    list_display = [
        'material', 'price', 'currency', 'source',
        'change_type', 'created_at'
    ]
    list_filter = [
        'organization', 'currency', 'source',
        'change_type', 'created_at'
    ]
    search_fields = ['material__name']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related(
            'material', 'organization'
        )
    
    def has_add_permission(self, request):
        """Price history should be automatically created"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Price history should not be modified"""
        return False