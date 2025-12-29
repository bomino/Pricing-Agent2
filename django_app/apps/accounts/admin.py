"""
Simple admin configuration for accounts app
"""
from django.contrib import admin
from .models import UserProfile

# Register UserProfile with basic admin
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'organization', 'role', 'department']
    search_fields = ['user__username', 'user__email']