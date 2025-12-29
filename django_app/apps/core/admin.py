"""
Simple admin configuration for core app
"""
from django.contrib import admin
from .models import Organization, AuditLog, Category, SystemConfiguration, Notification

# Register with basic ModelAdmin
admin.site.register(Organization)
admin.site.register(AuditLog)
admin.site.register(Category)
admin.site.register(SystemConfiguration)
admin.site.register(Notification)