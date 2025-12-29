"""
Simple URL configuration for initial setup
"""
from django.contrib import admin
from django.urls import path
from django.http import JsonResponse

def home_view(request):
    return JsonResponse({'message': 'AI Pricing Agent API', 'status': 'running'})

def health_check(request):
    return JsonResponse({'status': 'healthy'})

urlpatterns = [
    path('admin/', admin.site.urls),  # Admin re-enabled
    path('', home_view, name='home'),
    path('health/', health_check, name='health'),
]