"""
Accounts app admin interface
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from .models import UserProfile


class UserProfileInline(admin.StackedInline):
    """User profile inline for User admin"""
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'
    
    fieldsets = (
        ('Organization', {
            'fields': ('organization', 'role', 'department')
        }),
        ('Preferences', {
            'fields': ('timezone', 'language', 'email_notifications')
        }),
        ('Profile', {
            'fields': ('phone_number', 'avatar', 'bio')
        }),
        ('Security', {
            'fields': ('two_factor_enabled', 'failed_login_attempts', 'last_login_ip')
        })
    )
    
    readonly_fields = ['failed_login_attempts', 'last_login_ip']


class UserAdmin(BaseUserAdmin):
    """Extended User admin with profile"""
    inlines = (UserProfileInline,)
    
    list_display = [
        'username', 'email', 'first_name', 'last_name',
        'organization_name', 'role', 'is_active', 'last_login'
    ]
    
    list_filter = [
        'is_active', 'is_staff', 'is_superuser',
        'userprofile__organization', 'userprofile__role',
        'date_joined', 'last_login'
    ]
    
    search_fields = [
        'username', 'email', 'first_name', 'last_name',
        'userprofile__phone_number'
    ]
    
    def organization_name(self, obj):
        """Display organization name"""
        if hasattr(obj, 'userprofile') and obj.profile.organization:
            return obj.profile.organization.name
        return '-'
    organization_name.short_description = 'Organization'
    
    def role(self, obj):
        """Display user role"""
        if hasattr(obj, 'userprofile'):
            role = obj.profile.role
            color = {
                'admin': '#dc3545',
                'manager': '#fd7e14',
                'user': '#28a745',
                'viewer': '#6c757d'
            }.get(role, '#6c757d')
            return format_html(
                '<span style="color: {};">{}</span>',
                color, role.title() if role else 'User'
            )
        return '-'
    role.short_description = 'Role'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related(
            'userprofile', 'userprofile__organization'
        )


# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """User profile admin interface"""
    list_display = [
        'user', 'organization', 'role', 'department',
        'timezone', 'two_factor_enabled', 'last_login_ip'
    ]
    
    list_filter = [
        'organization', 'role', 'department', 'timezone',
        'two_factor_enabled', 'email_notifications'
    ]
    
    search_fields = [
        'user__username', 'user__email', 'user__first_name',
        'user__last_name', 'phone_number', 'department'
    ]
    
    readonly_fields = [
        'failed_login_attempts', 'last_login_ip', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Organization', {
            'fields': ('organization', 'role', 'department')
        }),
        ('Contact Information', {
            'fields': ('phone_number', 'bio')
        }),
        ('Preferences', {
            'fields': ('timezone', 'language', 'email_notifications')
        }),
        ('Security', {
            'fields': ('two_factor_enabled', 'failed_login_attempts', 'last_login_ip')
        }),
        ('Media', {
            'fields': ('avatar',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related(
            'user', 'organization'
        )