from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from . import api_views

app_name = 'analytics'

# API router for DRF viewsets
router = DefaultRouter()
router.register(r'reports', views.ReportViewSet, basename='report')
router.register(r'dashboards', views.DashboardViewSet, basename='dashboard')

# URL patterns
urlpatterns = [
    # API endpoints
    path('api/', include(router.urls)),
    
    # Dashboard views
    path('', views.AnalyticsDashboardView.as_view(), name='dashboard'),
    path('dashboards/', views.DashboardListView.as_view(), name='dashboard_list'),
    path('dashboards/<int:pk>/', views.DashboardDetailView.as_view(), name='dashboard_detail'),
    
    # Report views
    path('reports/', views.ReportListView.as_view(), name='report_list'),
    path('reports/<uuid:pk>/', views.ReportDetailView.as_view(), name='report_detail'),
    path('reports/<uuid:pk>/download/', views.ReportDownloadView.as_view(), name='report_download'),
    path('reports/generate/', views.ReportGenerateView.as_view(), name='report_generate'),
    
    # Data export
    path('export/pricing/', views.PricingDataExportView.as_view(), name='pricing_export'),
    path('export/procurement/', views.ProcurementDataExportView.as_view(), name='procurement_export'),
    path('export/suppliers/', views.SupplierDataExportView.as_view(), name='supplier_export'),
    
    # Metrics and KPIs
    path('metrics/pricing/', views.PricingMetricsView.as_view(), name='pricing_metrics'),
    path('metrics/procurement/', views.ProcurementMetricsView.as_view(), name='procurement_metrics'),
    path('metrics/suppliers/', views.SupplierMetricsView.as_view(), name='supplier_metrics'),
    
    # Charts and visualizations
    path('charts/price-trends/', views.PriceTrendChartView.as_view(), name='price_trend_chart'),
    path('charts/supplier-performance/', views.SupplierPerformanceChartView.as_view(), name='supplier_performance_chart'),
    path('charts/cost-analysis/', views.CostAnalysisChartView.as_view(), name='cost_analysis_chart'),
    
    # Tab content views for HTMX
    path('tab/insights/', views.InsightsTabView.as_view(), name='insights_tab'),
    path('tab/trends/', views.TrendsTabView.as_view(), name='trends_tab'),
    path('tab/predictions/', views.PredictionsTabView.as_view(), name='predictions_tab'),
    path('tab/benchmarks/', views.BenchmarksTabView.as_view(), name='benchmarks_tab'),
    path('tab/reports/', views.ReportsTabView.as_view(), name='reports_tab'),

    # Enhanced Analytics API endpoints (using real price data)
    path('api/price-trends/', api_views.price_trends_api, name='api_price_trends'),
    path('api/price-anomalies/', api_views.price_anomalies_api, name='api_price_anomalies'),
    path('api/savings-opportunities/', api_views.savings_opportunities_api, name='api_savings_opportunities'),
    path('api/supplier-comparison/', api_views.supplier_comparison_api, name='api_supplier_comparison'),
    path('api/price-forecast/', api_views.price_forecast_api, name='api_price_forecast'),
    path('api/upload-impact/', api_views.upload_impact_api, name='api_upload_impact'),
    path('api/dashboard-data/', api_views.analytics_dashboard_api, name='api_dashboard_data'),
]