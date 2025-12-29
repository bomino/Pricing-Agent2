"""
URL configuration for pricing_agent project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from apps.core.views import HealthCheckView

urlpatterns = [
    # Health check endpoint (accessible at root level)
    path('health/', HealthCheckView.as_view(), name='health_check'),
    
    # Admin
    path('admin/', admin.site.urls),
    
    # Main application URLs
    path('', include('apps.core.urls')),
    
    # Accounts URLs
    path('accounts/', include('apps.accounts.urls')),
    
    # Procurement URLs
    path('procurement/', include('apps.procurement.urls')),
    
    # Pricing URLs
    path('pricing/', include('apps.pricing.urls')),
    
    # Analytics URLs
    path('analytics/', include('apps.analytics.urls')),
    
    # Data Ingestion URLs
    path('data-ingestion/', include('apps.data_ingestion.urls')),
    
    # API URLs (will add later after migrations)
    # path('api/v1/', include(api_v1_router.urls)),
    # path('api/v1/auth/', include('apps.accounts.api.urls')),
]

# Add static/media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)