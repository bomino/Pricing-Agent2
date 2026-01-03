"""
Core app URL patterns
"""
from django.urls import path
from django.views.generic import TemplateView
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.utils import timezone
from .auth_views import (
    LoginView, LogoutView, RegisterView, 
    PasswordResetView, ProfileView, UserManagementView
)
from .views import (
    DashboardView, recent_rfqs_api, price_alerts_api,
    notifications_list_api, notifications_unread_count_api, notifications_mark_all_read_api
)

app_name = 'core'

# Simple health check view
@api_view(['GET'])
def health_check(request):
    """Simple health check endpoint"""
    return Response({
        'status': 'healthy',
        'timestamp': timezone.now().isoformat(),
        'service': 'AI Pricing Agent Django API'
    })

# URL patterns
urlpatterns = [
    # Health check
    path('health/', health_check, name='health_check'),
    
    # Authentication
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('register/', RegisterView.as_view(), name='register'),
    path('password-reset/', PasswordResetView.as_view(), name='password_reset'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('users/', UserManagementView.as_view(), name='user_management'),
    
    # Home page
    path('', TemplateView.as_view(template_name='index.html'), name='home'),
    
    # Dashboard views
    path('dashboard/', DashboardView.as_view(), name='dashboard'),

    # Dashboard API endpoints (for HTMX)
    path('api/dashboard/recent-rfqs/', recent_rfqs_api, name='recent_rfqs_api'),
    path('api/dashboard/price-alerts/', price_alerts_api, name='price_alerts_api'),

    # Notification API endpoints (for header HTMX polling)
    path('api/notifications/', notifications_list_api, name='notifications_list_api'),
    path('api/notifications/unread-count/', notifications_unread_count_api, name='notifications_unread_count_api'),
    path('api/notifications/mark-all-read/', notifications_mark_all_read_api, name='notifications_mark_all_read_api'),
]