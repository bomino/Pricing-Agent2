from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'integrations'

# API router for DRF viewsets
router = DefaultRouter()
router.register(r'connections', views.IntegrationConnectionViewSet, basename='connection')
router.register(r'sync-logs', views.SyncLogViewSet, basename='sync_log')

# URL patterns
urlpatterns = [
    # API endpoints
    path('api/', include(router.urls)),
    
    # Integration management
    path('', views.IntegrationsListView.as_view(), name='list'),
    path('connections/', views.ConnectionListView.as_view(), name='connection_list'),
    path('connections/<int:pk>/', views.ConnectionDetailView.as_view(), name='connection_detail'),
    path('connections/create/', views.ConnectionCreateView.as_view(), name='connection_create'),
    path('connections/<int:pk>/edit/', views.ConnectionUpdateView.as_view(), name='connection_update'),
    path('connections/<int:pk>/test/', views.ConnectionTestView.as_view(), name='connection_test'),
    
    # ERP integrations
    path('erp/sap/', views.SAPIntegrationView.as_view(), name='sap_integration'),
    path('erp/oracle/', views.OracleIntegrationView.as_view(), name='oracle_integration'),
    path('erp/sage/', views.SageIntegrationView.as_view(), name='sage_integration'),
    
    # Market data integrations
    path('market-data/bloomberg/', views.BloombergIntegrationView.as_view(), name='bloomberg_integration'),
    path('market-data/reuters/', views.ReutersIntegrationView.as_view(), name='reuters_integration'),
    
    # Supplier portals
    path('supplier-portals/', views.SupplierPortalIntegrationView.as_view(), name='supplier_portal_integration'),
    
    # Data synchronization
    path('sync/manual/', views.ManualSyncView.as_view(), name='manual_sync'),
    path('sync/schedule/', views.ScheduleSyncView.as_view(), name='schedule_sync'),
    path('sync/logs/', views.SyncLogListView.as_view(), name='sync_log_list'),
    path('sync/logs/<int:pk>/', views.SyncLogDetailView.as_view(), name='sync_log_detail'),
    
    # Webhooks
    path('webhooks/', views.WebhookListView.as_view(), name='webhook_list'),
    path('webhooks/create/', views.WebhookCreateView.as_view(), name='webhook_create'),
    path('webhooks/<int:pk>/edit/', views.WebhookUpdateView.as_view(), name='webhook_update'),
    path('webhooks/receive/', views.WebhookReceiveView.as_view(), name='webhook_receive'),
]