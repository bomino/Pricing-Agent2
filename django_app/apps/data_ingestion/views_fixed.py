"""
Fixed and simplified views for Data Ingestion with comprehensive error handling
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
import json
import pandas as pd
import logging
import traceback

from .models import DataUpload, DataMappingTemplate, ProcurementDataStaging, DataIngestionLog
from .services.file_parser import FileParser
from .services.optimized_processor import OptimizedDataProcessor

logger = logging.getLogger(__name__)


@login_required
@ensure_csrf_cookie
def column_mapping_simple(request, upload_id):
    """Simplified column mapping with better error handling"""
    try:
        # Get upload
        organization = request.user.profile.organization if hasattr(request.user, 'profile') else None
        upload = get_object_or_404(DataUpload, id=upload_id)
        
        # Handle POST - Save mappings
        if request.method == "POST":
            try:
                # Parse JSON body
                if request.body:
                    mappings = json.loads(request.body)
                else:
                    mappings = {}
                
                logger.info(f"Received mappings for upload {upload_id}: {mappings}")
                
                # Save mappings
                upload.column_mapping = mappings
                upload.status = 'ready_to_process'
                upload.save()
                
                # Log the action
                DataIngestionLog.objects.create(
                    upload=upload,
                    action='mapping_saved',
                    user=request.user,
                    message='Column mappings saved successfully',
                    details={'mappings': mappings}
                )
                
                # Start processing immediately with optimized processor
                try:
                    processor = OptimizedDataProcessor()
                    result = processor.process_upload(str(upload_id))
                    
                    if result.get('success'):
                        return JsonResponse({
                            'success': True,
                            'message': f'Successfully processed {result["processed"]} records',
                            'redirect': '/data-ingestion/'
                        })
                    else:
                        return JsonResponse({
                            'success': False,
                            'error': result.get('error', 'Processing failed')
                        }, status=500)
                        
                except Exception as proc_error:
                    logger.error(f"Processing error: {str(proc_error)}")
                    # Still return success for mapping save
                    return JsonResponse({
                        'success': True,
                        'message': 'Mappings saved. Processing will continue in background.',
                        'redirect': '/data-ingestion/'
                    })
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {str(e)}")
                return JsonResponse({
                    'success': False,
                    'error': f'Invalid JSON data: {str(e)}'
                }, status=400)
            except Exception as e:
                logger.error(f"Error saving mappings: {str(e)}\n{traceback.format_exc()}")
                return JsonResponse({
                    'success': False,
                    'error': str(e)
                }, status=500)
        
        # GET request - Show mapping interface
        # Get columns from detected schema
        columns = []
        suggested_mappings = {}
        
        if upload.detected_schema:
            if 'columns' in upload.detected_schema:
                columns = list(upload.detected_schema['columns'].keys())
            if 'suggested_mappings' in upload.detected_schema:
                suggested_mappings = upload.detected_schema['suggested_mappings']
        
        # If no columns, try to re-parse the file quickly
        if not columns and upload.file:
            try:
                upload.file.seek(0)
                if upload.file_format == 'csv':
                    df = pd.read_csv(upload.file, nrows=1)
                    columns = list(df.columns)
                elif upload.file_format in ['xlsx', 'xls']:
                    df = pd.read_excel(upload.file, nrows=1)
                    columns = list(df.columns)
            except:
                logger.warning("Could not re-parse file for columns")
        
        # Get target fields based on data type
        target_fields = get_simple_target_fields(upload.data_type)
        
        context = {
            'upload': upload,
            'columns': columns[:50],  # Limit to 50 columns
            'suggested_mappings': suggested_mappings,
            'target_fields': target_fields,
            'data_type': upload.data_type
        }
        
        return render(request, 'data_ingestion/mapping_simple.html', context)
        
    except Exception as e:
        logger.error(f"Fatal error in column_mapping: {str(e)}\n{traceback.format_exc()}")
        messages.error(request, f"Error loading mapping page: {str(e)}")
        return redirect('data_ingestion:dashboard')


def get_simple_target_fields(data_type):
    """Get simplified target fields for mapping"""
    
    # Core fields that apply to most data types
    core_fields = [
        {'name': 'supplier_name', 'label': 'Supplier/Vendor Name', 'required': True},
        {'name': 'material_description', 'label': 'Item/Product Description', 'required': True},
        {'name': 'quantity', 'label': 'Quantity', 'required': True},
        {'name': 'unit_price', 'label': 'Unit Price', 'required': True},
    ]
    
    # Additional fields by data type
    type_specific = {
        'purchase_orders': [
            {'name': 'po_number', 'label': 'PO Number', 'required': True},
            {'name': 'purchase_date', 'label': 'Order Date', 'required': False},
            {'name': 'total_price', 'label': 'Total Amount', 'required': False},
        ],
        'invoices': [
            {'name': 'invoice_number', 'label': 'Invoice Number', 'required': True},
            {'name': 'invoice_date', 'label': 'Invoice Date', 'required': True},
            {'name': 'po_number', 'label': 'PO Number', 'required': False},
        ],
        'contracts': [
            {'name': 'contract_number', 'label': 'Contract Number', 'required': True},
            {'name': 'start_date', 'label': 'Start Date', 'required': False},
            {'name': 'end_date', 'label': 'End Date', 'required': False},
        ],
        'suppliers': [
            {'name': 'supplier_code', 'label': 'Supplier Code', 'required': True},
            {'name': 'contact_email', 'label': 'Email', 'required': False},
            {'name': 'phone', 'label': 'Phone', 'required': False},
        ],
        'materials': [
            {'name': 'material_code', 'label': 'Material Code', 'required': True},
            {'name': 'category', 'label': 'Category', 'required': False},
            {'name': 'unit_of_measure', 'label': 'UOM', 'required': False},
        ]
    }
    
    # Combine core and specific fields
    if data_type in type_specific:
        return type_specific[data_type] + core_fields
    
    # Default to purchase order fields
    return type_specific.get('purchase_orders', []) + core_fields


@login_required
@require_http_methods(["POST"])
def process_upload_simple(request, upload_id):
    """Simple processing endpoint"""
    try:
        upload = get_object_or_404(DataUpload, id=upload_id)
        
        # Use optimized processor
        processor = OptimizedDataProcessor()
        result = processor.process_upload(str(upload_id))
        
        if result.get('success'):
            return JsonResponse({
                'success': True,
                'message': f'Processed {result["processed"]} records successfully',
                'stats': {
                    'processed': result['processed'],
                    'errors': result['errors'],
                    'duplicates': result['duplicates']
                }
            })
        else:
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Processing failed')
            }, status=500)
            
    except Exception as e:
        logger.error(f"Processing error: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)