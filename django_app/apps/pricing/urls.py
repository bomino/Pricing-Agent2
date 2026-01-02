from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'pricing'

# API router for DRF viewsets
router = DefaultRouter()
router.register(r'materials', views.MaterialViewSet, basename='material')
router.register(r'prices', views.PriceViewSet, basename='price')
router.register(r'price-predictions', views.PricePredictionViewSet, basename='price_prediction')

# URL patterns
urlpatterns = [
    # API endpoints
    path('api/', include(router.urls)),
    
    # Material views (UUID primary keys)
    path('materials/', views.MaterialListView.as_view(), name='material_list'),
    path('materials/<uuid:pk>/', views.MaterialDetailView.as_view(), name='material_detail'),
    path('materials/<uuid:pk>/price-history/', views.MaterialPriceHistoryView.as_view(), name='material_price_history'),
    path('materials/create/', views.MaterialCreateView.as_view(), name='material_create'),
    path('materials/<uuid:pk>/edit/', views.MaterialUpdateView.as_view(), name='material_update'),

    # Price views (UUID primary keys)
    path('prices/', views.PriceListView.as_view(), name='price_list'),
    path('prices/<uuid:pk>/', views.PriceDetailView.as_view(), name='price_detail'),
    path('prices/bulk-upload/', views.BulkPriceUploadView.as_view(), name='bulk_price_upload'),

    # Predictions and Alerts (UUID primary keys)
    path('predictions/', views.PricePredictionView.as_view(), name='predictions'),
    path('alerts/', views.AlertListView.as_view(), name='alerts'),
    path('alerts/create/', views.AlertCreateView.as_view(), name='alert_create'),
    path('alerts/<uuid:pk>/edit/', views.AlertUpdateView.as_view(), name='alert_update'),
    
    # Analytics views
    path('analytics/trends/', views.PriceTrendView.as_view(), name='price_trends'),
    path('analytics/predictions/', views.PricePredictionView.as_view(), name='price_predictions'),
    path('analytics/volatility/', views.PriceVolatilityView.as_view(), name='price_volatility'),
    
    # Dashboard
    path('dashboard/', views.PricingDashboardView.as_view(), name='dashboard'),
]