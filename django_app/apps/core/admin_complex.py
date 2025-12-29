"""
Core app admin interface
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import Organization, AuditLog


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    """Organization admin interface"""
    list_display = [
        'name', 'subdomain', 'is_active', 'created_at', 'user_count'
    ]
    list_filter = ['is_active', 'created_at', 'plan_type']
    search_fields = ['name', 'subdomain', 'contact_email']
    readonly_fields = ['created_at', 'updated_at', 'user_count']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'subdomain', 'description')
        }),
        ('Contact Information', {
            'fields': ('contact_email', 'contact_phone', 'address')
        }),
        ('Subscription', {
            'fields': ('plan_type', 'max_users', 'subscription_expires_at')
        }),
        ('Settings', {
            'fields': ('is_active', 'settings')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def user_count(self, obj):
        """Display user count for organization"""
        from django.contrib.auth.models import User
        count = User.objects.filter(userprofile__organization=obj).count()
        return format_html('<span style="color: #006eb8;">{}</span>', count)
    user_count.short_description = 'Users'
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).prefetch_related('users')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Audit log admin interface"""
    list_display = [
        'timestamp', 'user', 'organization', 'action', 'model_name',
        'object_id', 'ip_address'
    ]
    list_filter = [
        'timestamp', 'action', 'model_name', 'organization'
    ]
    search_fields = [
        'user__username', 'user__email', 'action', 'model_name',
        'object_id', 'ip_address'
    ]
    readonly_fields = [
        'timestamp', 'user', 'organization', 'action', 'model_name',
        'object_id', 'object_repr', 'changes', 'ip_address', 'user_agent'
    ]
    
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']
    
    def has_add_permission(self, request):
        """Audit logs should not be manually added"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Audit logs should not be modified"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Allow deletion for cleanup purposes"""
        return request.user.is_superuser


# Custom admin site configuration
admin.site.site_header = 'AI Pricing Agent Administration'
admin.site.site_title = 'AI Pricing Agent Admin'
admin.site.index_title = 'Welcome to AI Pricing Agent Administration'