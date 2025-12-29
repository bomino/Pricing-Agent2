"""
Admin configuration for Data Ingestion Module
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import (
    DataUpload,
    DataMappingTemplate,
    ProcurementDataStaging,
    DataIngestionLog
)


@admin.register(DataUpload)
class DataUploadAdmin(admin.ModelAdmin):
    """Admin for Data Upload management"""
    list_display = [
        'original_filename',
        'data_type',
        'uploaded_by',
        'organization',
        'status_badge',
        'total_rows',
        'processed_rows',
        'created_at',
        'file_size_display'
    ]
    list_filter = [
        'status',
        'data_type',
        'file_format',
        'created_at',
        'organization'
    ]
    search_fields = [
        'original_filename',
        'uploaded_by__username',
        'uploaded_by__email',
        'organization__name'
    ]
    readonly_fields = [
        'id',
        'created_at',
        'updated_at',
        'processing_started_at',
        'processing_completed_at',
        'detected_schema',
        'validation_report',
        'file_size_display',
        'duration_display'
    ]
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    fieldsets = (
        ('Upload Information', {
            'fields': (
                'id',
                'organization',
                'uploaded_by',
                'original_filename',
                'file',
                'file_format',
                'file_size_display',
                'data_type'
            )
        }),
        ('Processing Status', {
            'fields': (
                'status',
                'total_rows',
                'processed_rows',
                'error_message'
            )
        }),
        ('Schema & Mapping', {
            'fields': (
                'detected_schema',
                'column_mapping'
            ),
            'classes': ('collapse',)
        }),
        ('Validation', {
            'fields': (
                'validation_report',
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
                'processing_started_at',
                'processing_completed_at',
                'duration_display'
            )
        })
    )
    
    def status_badge(self, obj):
        """Display status as colored badge"""
        colors = {
            'pending': '#FFC107',
            'processing': '#2196F3',
            'validating': '#9C27B0',
            'mapping': '#FF9800',
            'completed': '#4CAF50',
            'failed': '#F44336'
        }
        color = colors.get(obj.status, '#9E9E9E')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 15px; font-size: 11px; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display() if hasattr(obj, 'get_status_display') else obj.status.upper()
        )
    status_badge.short_description = 'Status'
    
    def file_size_display(self, obj):
        """Display file size in human-readable format"""
        if obj.file_size:
            size = obj.file_size
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size < 1024.0:
                    return f"{size:.1f} {unit}"
                size /= 1024.0
            return f"{size:.1f} TB"
        return '-'
    file_size_display.short_description = 'File Size'
    
    def duration_display(self, obj):
        """Display processing duration"""
        if obj.processing_started_at and obj.processing_completed_at:
            duration = obj.processing_completed_at - obj.processing_started_at
            minutes = int(duration.total_seconds() / 60)
            seconds = int(duration.total_seconds() % 60)
            return f"{minutes}m {seconds}s"
        return '-'
    duration_display.short_description = 'Processing Time'
    
    actions = ['restart_processing', 'mark_as_failed', 'export_data']
    
    def restart_processing(self, request, queryset):
        """Restart processing for selected uploads"""
        count = 0
        for upload in queryset:
            if upload.status in ['failed', 'completed']:
                upload.status = 'pending'
                upload.error_message = None
                upload.save()
                count += 1
        self.message_user(request, f'Restarted processing for {count} upload(s)')
    restart_processing.short_description = 'Restart processing'
    
    def mark_as_failed(self, request, queryset):
        """Mark selected uploads as failed"""
        count = queryset.update(status='failed')
        self.message_user(request, f'Marked {count} upload(s) as failed')
    mark_as_failed.short_description = 'Mark as failed'
    
    def export_data(self, request, queryset):
        """Export processed data"""
        # This would implement actual export functionality
        self.message_user(request, 'Export functionality not yet implemented')
    export_data.short_description = 'Export processed data'


@admin.register(DataMappingTemplate)
class DataMappingTemplateAdmin(admin.ModelAdmin):
    """Admin for Data Mapping Templates"""
    list_display = [
        'name',
        'data_type',
        'source_system',
        'organization',
        'created_by',
        'created_at',
        'usage_count'
    ]
    list_filter = [
        'data_type',
        'source_system',
        'created_at',
        'organization'
    ]
    search_fields = [
        'name',
        'description',
        'source_system',
        'created_by__username',
        'organization__name'
    ]
    readonly_fields = [
        'id',
        'created_at',
        'updated_at',
        'usage_count'
    ]
    ordering = ['-created_at']
    
    fieldsets = (
        ('Template Information', {
            'fields': (
                'id',
                'name',
                'description',
                'data_type',
                'source_system',
                'organization'
            )
        }),
        ('Mapping Configuration', {
            'fields': (
                'column_mappings',
                'transformation_rules'
            )
        }),
        ('Metadata', {
            'fields': (
                'created_by',
                'created_at',
                'updated_at',
                'usage_count'
            )
        })
    )
    
    def usage_count(self, obj):
        """Count how many times this template has been used"""
        # This would count actual usage
        return 0
    usage_count.short_description = 'Times Used'
    
    actions = ['duplicate_template']
    
    def duplicate_template(self, request, queryset):
        """Duplicate selected templates"""
        count = 0
        for template in queryset:
            template.pk = None
            template.name = f"{template.name} (Copy)"
            template.save()
            count += 1
        self.message_user(request, f'Duplicated {count} template(s)')
    duplicate_template.short_description = 'Duplicate selected templates'


@admin.register(ProcurementDataStaging)
class ProcurementDataStagingAdmin(admin.ModelAdmin):
    """Admin for Staging Data"""
    list_display = [
        'upload',
        'row_number',
        'po_number',
        'supplier_name',
        'validation_status_badge',
        'is_processed',
        'created_at'
    ]
    list_filter = [
        'validation_status',
        'is_processed',
        'created_at',
        'upload'
    ]
    search_fields = [
        'po_number',
        'supplier_name',
        'material_description',
        'upload__original_filename'
    ]
    readonly_fields = [
        'id',
        'created_at',
        'updated_at',
        'processed_at'
    ]
    date_hierarchy = 'created_at'
    ordering = ['-created_at', 'row_number']
    list_per_page = 20  # Reduced to prevent field limit issues
    list_select_related = ['upload']  # Optimize queries
    show_full_result_count = False  # Don't count all records for performance
    
    fieldsets = (
        ('Record Information', {
            'fields': (
                'id',
                'upload',
                'row_number'
            )
        }),
        ('Data', {
            'fields': (
                'raw_data',
                'processed_data'
            )
        }),
        ('Validation', {
            'fields': (
                'validation_status',
                'validation_errors'
            )
        }),
        ('Processing', {
            'fields': (
                'is_processed',
                'processed_at',
                'created_at',
                'updated_at'
            )
        })
    )
    
    def validation_status_badge(self, obj):
        """Display validation status as colored badge"""
        colors = {
            'pending': '#FFC107',
            'valid': '#4CAF50',
            'invalid': '#F44336',
            'warning': '#FF9800'
        }
        color = colors.get(obj.validation_status, '#9E9E9E')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 15px; font-size: 11px; font-weight: bold;">{}</span>',
            color,
            obj.validation_status.upper()
        )
    validation_status_badge.short_description = 'Validation'
    
    actions = ['mark_as_valid', 'mark_as_invalid', 'reprocess_records']
    
    def mark_as_valid(self, request, queryset):
        """Mark selected records as valid"""
        count = queryset.update(validation_status='valid')
        self.message_user(request, f'Marked {count} record(s) as valid')
    mark_as_valid.short_description = 'Mark as valid'
    
    def mark_as_invalid(self, request, queryset):
        """Mark selected records as invalid"""
        count = queryset.update(validation_status='invalid')
        self.message_user(request, f'Marked {count} record(s) as invalid')
    mark_as_invalid.short_description = 'Mark as invalid'
    
    def reprocess_records(self, request, queryset):
        """Reprocess selected records"""
        count = queryset.update(is_processed=False, processed_at=None)
        self.message_user(request, f'Marked {count} record(s) for reprocessing')
    reprocess_records.short_description = 'Reprocess selected records'


@admin.register(DataIngestionLog)
class DataIngestionLogAdmin(admin.ModelAdmin):
    """Admin for Ingestion Logs"""
    list_display = [
        'upload',
        'action',
        'user',
        'timestamp',
        'message_preview'
    ]
    list_filter = [
        'action',
        'timestamp'
    ]
    search_fields = [
        'upload__original_filename',
        'user__username',
        'message',
        'action'
    ]
    readonly_fields = [
        'id',
        'upload',
        'action',
        'user',
        'timestamp',
        'message',
        'details'
    ]
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']
    list_per_page = 100
    
    fieldsets = (
        ('Log Entry', {
            'fields': (
                'id',
                'upload',
                'action',
                'timestamp'
            )
        }),
        ('User Information', {
            'fields': (
                'user',
            )
        }),
        ('Message Details', {
            'fields': (
                'message',
                'details'
            )
        })
    )
    
    def message_preview(self, obj):
        """Show truncated message preview"""
        if obj.message:
            return obj.message[:100] + '...' if len(obj.message) > 100 else obj.message
        return '-'
    message_preview.short_description = 'Message'
    
    def has_add_permission(self, request):
        """Logs should not be manually added"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Logs should not be edited"""
        return False
    
    actions = ['export_logs']
    
    def export_logs(self, request, queryset):
        """Export selected logs"""
        # This would implement actual export functionality
        self.message_user(request, f'Export functionality for {queryset.count()} log(s) not yet implemented')
    export_logs.short_description = 'Export selected logs'


# Customize admin site header
admin.site.site_header = "AI Pricing Agent Administration"
admin.site.site_title = "AI Pricing Agent Admin"
admin.site.index_title = "Welcome to AI Pricing Agent Administration"