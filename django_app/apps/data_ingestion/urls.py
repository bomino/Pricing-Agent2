"""
URL Configuration for Data Ingestion Module
"""
from django.urls import path
from . import views
from . import conflict_views
from . import quality_views

app_name = 'data_ingestion'

urlpatterns = [
    # Main dashboard
    path('', views.upload_dashboard, name='dashboard'),
    
    # File upload
    path('upload/', views.upload_file, name='upload'),
    
    # Column mapping
    path('mapping/<uuid:upload_id>/', views.column_mapping, name='mapping'),
    
    # Alternative simplified mapping (if issues with main one)
    # path('mapping-simple/<uuid:upload_id>/', views_fixed.column_mapping_simple, name='mapping_simple'),
    
    # Validation review
    path('validation/<uuid:upload_id>/', views.validation_review, name='validation'),
    
    # Progress tracking (HTMX endpoint)
    path('progress/<uuid:upload_id>/', views.upload_progress, name='progress'),
    
    # Save mapping template
    path('api/save-template/', views.save_mapping_template, name='save_template'),
    
    # Process to main tables
    path('process-to-main/<uuid:upload_id>/', views.process_upload, name='process_upload'),
    
    # Upload detail view
    path('detail/<uuid:upload_id>/', views.upload_detail, name='upload_detail'),
    
    # Delete upload
    path('delete/<uuid:upload_id>/', views.delete_upload, name='delete_upload'),
    
    # Reset all data (admin only)
    path('reset-data/', views.reset_all_data, name='reset_data'),

    # Conflict resolution URLs
    path('conflicts/<uuid:upload_id>/', conflict_views.conflict_list, name='conflict_list'),
    path('conflict/<uuid:conflict_id>/', conflict_views.conflict_detail, name='conflict_detail'),
    path('conflict/<uuid:conflict_id>/resolve/', conflict_views.resolve_conflict, name='resolve_conflict'),
    path('conflicts/bulk-resolve/', conflict_views.bulk_resolve_conflicts, name='bulk_resolve_conflicts'),
    path('api/conflict/<uuid:conflict_id>/', conflict_views.conflict_resolution_api, name='conflict_resolution_api'),

    # Data quality URLs
    path('quality/<uuid:upload_id>/', quality_views.data_quality_report, name='quality_report'),
    path('api/quality/<uuid:upload_id>/', quality_views.quality_score_api, name='quality_api'),
]