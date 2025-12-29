from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'procurement'

# API router for DRF viewsets
router = DefaultRouter()
router.register(r'suppliers', views.SupplierViewSet, basename='supplier')
router.register(r'rfqs', views.RFQViewSet, basename='rfq')
router.register(r'quotes', views.QuoteViewSet, basename='quote')

# URL patterns
urlpatterns = [
    # API endpoints
    path('api/', include(router.urls)),
    
    # Supplier views
    path('suppliers/', views.SupplierListView.as_view(), name='supplier_list'),
    path('suppliers/create/', views.SupplierCreateView.as_view(), name='supplier_create'),
    path('suppliers/<uuid:pk>/', views.SupplierDetailView.as_view(), name='supplier_detail'),
    path('suppliers/<uuid:pk>/edit/', views.SupplierUpdateView.as_view(), name='supplier_update'),
    
    # RFQ views
    path('rfqs/', views.RFQListView.as_view(), name='rfq_list'),
    path('rfqs/search/', views.RFQListView.as_view(), name='rfq_search'),
    path('rfqs/create/', views.RFQCreateView.as_view(), name='rfq_create'),
    path('rfqs/<uuid:pk>/', views.RFQDetailView.as_view(), name='rfq_detail'),
    path('rfqs/<uuid:pk>/edit/', views.RFQUpdateView.as_view(), name='rfq_edit'),
    path('rfqs/<uuid:pk>/delete/', views.RFQDeleteView.as_view(), name='rfq_delete'),
    path('rfqs/<uuid:pk>/send/', views.RFQSendView.as_view(), name='rfq_send'),
    
    # Quote views
    path('quotes/', views.QuoteListView.as_view(), name='quote_list'),
    path('quotes/<uuid:pk>/', views.QuoteDetailView.as_view(), name='quote_detail'),
    path('quotes/<uuid:pk>/approve/', views.QuoteApproveView.as_view(), name='quote_approve'),
    path('quotes/<uuid:pk>/reject/', views.QuoteRejectView.as_view(), name='quote_reject'),
    
    # Analytics
    path('analytics/supplier-performance/', views.SupplierPerformanceView.as_view(), name='supplier_performance'),
    path('analytics/quote-comparison/', views.QuoteComparisonView.as_view(), name='quote_comparison'),
    
    # Contract views
    path('contracts/', views.ContractListView.as_view(), name='contract_list'),
    path('contracts/create/', views.ContractCreateView.as_view(), name='contract_create'),
    path('contracts/<uuid:pk>/', views.ContractDetailView.as_view(), name='contract_detail'),
    path('contracts/<uuid:pk>/edit/', views.ContractUpdateView.as_view(), name='contract_update'),
    
    # Dashboard
    path('dashboard/', views.ProcurementDashboardView.as_view(), name='dashboard'),
    path('', views.ProcurementDashboardView.as_view(), name='index'),
]