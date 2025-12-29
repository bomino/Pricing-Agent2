"""
Optimized version of column mapping view
"""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.cache import cache_page
from django.core.cache import cache
import json
import logging

from .models import DataUpload, DataMappingTemplate, DataIngestionLog

logger = logging.getLogger(__name__)


@login_required
def column_mapping_fast(request, upload_id):
    """Fast column mapping interface with caching"""
    organization = request.user.profile.organization if hasattr(request.user, 'profile') else None
    upload = get_object_or_404(DataUpload, id=upload_id, organization=organization)
    
    if request.method == "POST":
        # Handle mapping save
        mappings = json.loads(request.body)
        upload.column_mapping = mappings
        upload.status = 'ready_to_process'
        upload.save()
        
        # Clear cache
        cache.delete(f'mapping_context_{upload_id}')
        
        return JsonResponse({'success': True, 'message': 'Mappings saved'})
    
    # Try to get cached context
    cache_key = f'mapping_context_{upload_id}'
    context = cache.get(cache_key)
    
    if not context:
        # Build minimal context
        context = {
            'upload': {
                'id': str(upload.id),
                'filename': upload.original_filename,
                'total_rows': upload.total_rows,
                'data_type': upload.data_type,
            },
            'columns': [],
            'target_fields': get_target_fields_list(upload.data_type),
            'suggested_mappings': {},
            'preview_data': []
        }
        
        # Get column names only (not full schema)
        if upload.detected_schema and 'columns' in upload.detected_schema:
            context['columns'] = list(upload.detected_schema['columns'].keys())[:50]  # Limit columns
            
            # Get suggested mappings if available
            if 'suggested_mappings' in upload.detected_schema:
                context['suggested_mappings'] = upload.detected_schema['suggested_mappings']
        
        # Get minimal preview (3 rows max)
        try:
            if upload.file and upload.file_format == 'csv':
                import pandas as pd
                upload.file.seek(0)
                df = pd.read_csv(upload.file, nrows=3)
                context['preview_data'] = df.fillna('').to_dict('records')
        except Exception as e:
            logger.warning(f"Could not load preview: {str(e)}")
        
        # Cache for 5 minutes
        cache.set(cache_key, context, 300)
    
    return render(request, 'data_ingestion/mapping_fast.html', context)


def get_target_fields_list(data_type):
    """Get simplified target fields list"""
    fields_map = {
        'purchase_orders': [
            {'name': 'po_number', 'required': True, 'description': 'Purchase Order Number'},
            {'name': 'supplier_name', 'required': True, 'description': 'Supplier/Vendor Name'},
            {'name': 'material_description', 'required': True, 'description': 'Item/Material Description'},
            {'name': 'quantity', 'required': True, 'description': 'Order Quantity'},
            {'name': 'unit_price', 'required': True, 'description': 'Price per Unit'},
            {'name': 'total_price', 'required': False, 'description': 'Total Line Amount'},
            {'name': 'currency', 'required': False, 'description': 'Currency Code'},
            {'name': 'purchase_date', 'required': False, 'description': 'Order Date'},
        ],
        'invoices': [
            {'name': 'invoice_number', 'required': True, 'description': 'Invoice Number'},
            {'name': 'supplier_name', 'required': True, 'description': 'Supplier Name'},
            {'name': 'total_amount', 'required': True, 'description': 'Invoice Total'},
            {'name': 'invoice_date', 'required': True, 'description': 'Invoice Date'},
        ]
    }
    return fields_map.get(data_type, fields_map['purchase_orders'])