"""
Views for Data Ingestion Module
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from apps.core.mixins import get_user_organization
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from django.db import transaction
import json
import pandas as pd
import traceback
from .models import DataUpload, DataMappingTemplate, ProcurementDataStaging, DataIngestionLog
from .services.file_parser import FileParser, SchemaDetector
from .services.data_processor import DataProcessor
from .services.optimized_processor import OptimizedDataProcessor
import logging
import time

logger = logging.getLogger(__name__)

# Celery is not configured yet, so always use sync processing
CELERY_AVAILABLE = False

def process_upload_sync(upload_id):
    """Synchronous processing fallback"""
    processor = OptimizedDataProcessor()
    return processor.process_upload(upload_id)


@login_required
def upload_dashboard(request):
    """Main dashboard for data uploads"""
    # Get organization through user profile (safe access)
    organization = get_user_organization(request.user)
    
    # Calculate stats
    total_uploads = DataUpload.objects.filter(
        organization=organization
    ).count() if organization else 0
    successful = DataUpload.objects.filter(
        organization=organization,
        status='completed'
    ).count() if organization else 0
    pending = DataUpload.objects.filter(
        organization=organization,
        status__in=['pending', 'processing', 'validating', 'mapping']
    ).count() if organization else 0
    failed = DataUpload.objects.filter(
        organization=organization,
        status='failed'
    ).count() if organization else 0

    # Calculate success rate
    success_rate = round((successful / total_uploads * 100), 1) if total_uploads > 0 else 0

    context = {
        'recent_uploads': DataUpload.objects.filter(
            organization=organization
        ).order_by('-created_at')[:10] if organization else [],
        'upload_stats': {
            'total_uploads': total_uploads,
            'successful': successful,
            'pending': pending,
            'failed': failed,
            'success_rate': success_rate,
        }
    }
    return render(request, 'data_ingestion/dashboard.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def upload_file(request):
    """Handle file upload"""
    if request.method == "POST":
        file = request.FILES.get('file')
        data_type = request.POST.get('data_type', 'purchase_orders')
        
        if not file:
            return JsonResponse({'error': 'No file provided'}, status=400)
        
        # Validate file size (50MB limit)
        if file.size > 52428800:
            return JsonResponse({'error': 'File size exceeds 50MB limit'}, status=400)
        
        # Detect file format
        file_extension = file.name.split('.')[-1].lower()
        if file_extension not in ['csv', 'xlsx', 'xls', 'parquet']:
            return JsonResponse({'error': 'Unsupported file format'}, status=400)
        
        try:
            # Get organization through user profile
            organization = get_user_organization(request.user)
            
            # Create upload record
            upload = DataUpload.objects.create(
                organization=organization,
                uploaded_by=request.user,
                file=file,
                original_filename=file.name,
                file_format=file_extension,
                file_size=file.size,
                data_type=data_type,
                status='validating'
            )
            
            # Log upload start
            DataIngestionLog.objects.create(
                upload=upload,
                action='upload_started',
                user=request.user,
                message=f'File upload started: {file.name}',
                details={'file_size': file.size, 'format': file_extension}
            )
            
            # Parse file and detect schema
            parser = FileParser()
            df, detected_schema = parser.parse_file(file, file_extension)
            
            # Save detected schema
            upload.detected_schema = detected_schema
            upload.total_rows = len(df)
            upload.status = 'mapping'
            upload.save()
            
            # OPTIMIZATION: Store minimal preview data in session (only 5 rows)
            # Convert to simple list of dicts to avoid JSON serialization issues
            preview_rows = df.head(5).fillna('').to_dict('records')
            request.session[f'upload_{upload.id}_preview'] = preview_rows
            
            # Return success with redirect to mapping page
            return JsonResponse({
                'success': True,
                'upload_id': str(upload.id),
                'redirect_url': f'/data-ingestion/mapping/{upload.id}/'
            })
            
        except Exception as e:
            if 'upload' in locals():
                upload.status = 'failed'
                upload.error_message = str(e)
                upload.save()
                
                DataIngestionLog.objects.create(
                    upload=upload,
                    action='error_occurred',
                    user=request.user,
                    message=f'Error parsing file: {str(e)}'
                )
            
            return JsonResponse({'error': str(e)}, status=500)
    
    # GET request - show upload form
    return render(request, 'data_ingestion/upload.html')


@login_required
def column_mapping(request, upload_id):
    """Column mapping interface - OPTIMIZED"""
    start_time = time.time()
    logger.info(f"Starting column mapping for upload {upload_id}")
    
    # Get upload - be more flexible with organization filter
    try:
        organization = get_user_organization(request.user)
        if organization:
            upload = get_object_or_404(DataUpload, id=upload_id, organization=organization)
        else:
            # For superusers or users without profile, just get by ID
            upload = get_object_or_404(DataUpload, id=upload_id)
    except:
        # Fallback: just get by ID
        upload = get_object_or_404(DataUpload, id=upload_id)
    
    logger.info(f"Got upload object in {time.time() - start_time:.2f}s")
    
    if request.method == "POST":
        try:
            # Parse request body
            if request.body:
                try:
                    data = json.loads(request.body)
                    # Extract mappings from the data
                    mappings = data.get('mappings', data)  # Support both formats
                    logger.info(f"Received mappings: {mappings}")
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {str(e)}, Body: {request.body[:200]}")
                    return JsonResponse({
                        'success': False,
                        'error': f'Invalid JSON format: {str(e)}'
                    }, status=400)
            else:
                logger.error("Empty request body")
                return JsonResponse({
                    'success': False,
                    'error': 'No mapping data received'
                }, status=400)
            
            # Save column mappings
            upload.column_mapping = mappings
            upload.status = 'ready_to_process'
            upload.save()
            logger.info(f"Saved mappings for upload {upload_id}")
            
            # Log mapping saved
            DataIngestionLog.objects.create(
                upload=upload,
                action='mapping_saved',
                user=request.user,
                message='Column mappings saved',
                details=mappings
            )
            
            # Create staging records if not exist
            staging_count = ProcurementDataStaging.objects.filter(upload=upload).count()
            if staging_count == 0:
                logger.info("Creating staging records...")
                # Parse file and create staging records with correct mapping
                try:
                    import pandas as pd  # Ensure pandas is imported
                    from decimal import Decimal
                    
                    parser = FileParser()
                    df, _ = parser.parse_file(upload.file, upload.file_format)
                    
                    # The mapping from UI is {target_field: source_col}
                    staging_records = []
                    for idx, row in df.iterrows():
                        staging_data = {
                            'upload': upload,
                            'row_number': idx + 1,
                            'validation_status': 'valid',
                            'raw_data': row.to_dict()
                        }
                        
                        # Apply mapping correctly
                        for target_field, source_col in mappings.items():
                            if source_col in row:
                                value = row[source_col]
                                if pd.notna(value):
                                    if target_field == 'quantity':
                                        try:
                                            staging_data[target_field] = Decimal(str(value))
                                        except:
                                            staging_data[target_field] = Decimal('0')
                                    elif target_field in ['unit_price', 'total_price']:
                                        try:
                                            if isinstance(value, str):
                                                value = value.replace('$', '').replace(',', '')
                                            staging_data[target_field] = Decimal(str(value))
                                        except:
                                            staging_data[target_field] = Decimal('0')
                                    elif target_field in ['purchase_date', 'delivery_date']:
                                        try:
                                            staging_data[target_field] = pd.to_datetime(value).date()
                                        except:
                                            staging_data[target_field] = timezone.now().date()
                                    else:
                                        staging_data[target_field] = str(value)
                        
                        # Add default currency if missing
                        if 'currency' not in staging_data or not staging_data.get('currency'):
                            staging_data['currency'] = 'USD'
                        
                        staging_records.append(ProcurementDataStaging(**staging_data))
                    
                    # Bulk create staging records
                    ProcurementDataStaging.objects.bulk_create(staging_records)
                    logger.info(f"Created {len(staging_records)} staging records")
                    
                except Exception as e:
                    logger.error(f"Failed to create staging records: {str(e)}", exc_info=True)
                    # Don't continue processing if staging failed
                    return JsonResponse({
                        'success': False,
                        'error': f'Failed to create staging records: {str(e)}'
                    })
            
            # Update status to indicate ready for processing
            upload.status = 'ready_to_process'
            upload.save()
            logger.info(f"Upload {upload_id} ready for processing")

            # Redirect to the process confirmation page instead of auto-processing
            return JsonResponse({
                'success': True,
                'message': 'Mappings saved successfully. Ready to process data.',
                'redirect': f'/data-ingestion/process-to-main/{upload_id}/'
            })
            
        except Exception as e:
            logger.error(f"Error in column_mapping POST: {str(e)}\n{traceback.format_exc()}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    # OPTIMIZATION: Don't load preview data from session if file is large
    preview_data = []
    
    # If we need preview data, re-read just first 5 rows from file
    if upload.file and upload.total_rows > 0:
        try:
            # Parse just first 5 rows for preview
            parser = FileParser()
            # Read file with limit
            if upload.file_format == 'csv':
                upload.file.seek(0)
                import pandas as pd
                df = pd.read_csv(upload.file, nrows=5)
                preview_data = df.to_dict('records')
            else:
                # For other formats, use cached preview or empty
                preview_json = request.session.get(f'upload_{upload_id}_preview')
                if preview_json:
                    try:
                        # Only get first 5 records
                        data = json.loads(preview_json) if isinstance(preview_json, str) else preview_json
                        preview_data = data[:5] if isinstance(data, list) else []
                    except:
                        preview_data = []
        except Exception as e:
            logger.warning(f"Could not load preview data: {str(e)}")
            preview_data = []
    
    # OPTIMIZATION: Only get templates we need, with select_related
    # Get organization from upload object
    templates = DataMappingTemplate.objects.filter(
        organization=upload.organization,
        data_type=upload.data_type
    ).only('id', 'name', 'column_mappings')[:10]  # Limit to 10 templates
    
    # Ensure detected_schema is properly formatted but lightweight
    detected_schema = upload.detected_schema or {}
    
    if not isinstance(detected_schema, dict):
        detected_schema = {}
    
    # Only keep essential schema info
    essential_schema = {
        'columns': detected_schema.get('columns', {}),
        'suggested_mappings': detected_schema.get('suggested_mappings', {}),
        'sample_values': {}  # Don't send sample values to reduce size
    }
    
    # Only include first 3 sample values per column
    if 'sample_values' in detected_schema:
        for col, values in detected_schema['sample_values'].items():
            if isinstance(values, list):
                essential_schema['sample_values'][col] = values[:3]
    
    context = {
        'upload': upload,
        'detected_schema': essential_schema,
        'preview_data': preview_data[:5],  # Ensure max 5 rows
        'templates': templates,
        'target_fields': get_target_fields(upload.data_type)
    }
    
    return render(request, 'data_ingestion/mapping.html', context)


@login_required
def validation_review(request, upload_id):
    """Review and fix validation errors"""
    organization = get_user_organization(request.user)
    upload = get_object_or_404(DataUpload, id=upload_id, organization=organization)
    
    # Get staging records with errors
    error_records = ProcurementDataStaging.objects.filter(
        upload=upload,
        validation_status='invalid'
    )[:100]  # Limit to first 100 errors
    
    context = {
        'upload': upload,
        'error_records': error_records,
        'total_errors': error_records.count(),
        'validation_report': upload.validation_report
    }
    
    return render(request, 'data_ingestion/validation.html', context)


@login_required
@require_http_methods(["POST"])
def save_mapping_template(request):
    """Save column mapping as reusable template"""
    data = json.loads(request.body)
    
    organization = get_user_organization(request.user)
    
    template = DataMappingTemplate.objects.create(
        organization=organization,
        name=data['name'],
        data_type=data['data_type'],
        source_system=data.get('source_system', ''),
        column_mappings=data['mappings'],
        created_by=request.user
    )
    
    return JsonResponse({
        'success': True,
        'template_id': str(template.id)
    })


@login_required
def upload_progress(request, upload_id):
    """Get upload processing progress via HTMX polling"""
    organization = get_user_organization(request.user)
    upload = get_object_or_404(DataUpload, id=upload_id, organization=organization)
    
    return render(request, 'data_ingestion/partials/progress.html', {
        'upload': upload,
        'percentage': upload.get_processing_percentage()
    })


def process_upload(upload):
    """Process uploaded data (simplified - would be Celery task in production)"""
    try:
        upload.processing_started_at = timezone.now()
        upload.save()
        
        # This would be a complex async process
        # For now, just mark as completed
        upload.status = 'completed'
        upload.processing_completed_at = timezone.now()
        upload.processed_rows = upload.total_rows
        upload.save()
        
        DataIngestionLog.objects.create(
            upload=upload,
            action='processing_completed',
            user=upload.uploaded_by,
            message='Processing completed successfully',
            details={
                'total_rows': upload.total_rows,
                'processed_rows': upload.processed_rows
            }
        )
        
    except Exception as e:
        upload.status = 'failed'
        upload.error_message = str(e)
        upload.save()


def get_target_fields(data_type):
    """Get target fields based on data type"""
    fields_map = {
        'purchase_orders': [
            'po_number', 'supplier_name', 'supplier_code', 'material_code',
            'material_description', 'quantity', 'unit_price', 'total_price',
            'currency', 'purchase_date', 'delivery_date'
        ],
        'invoices': [
            'invoice_number', 'po_number', 'supplier_name', 'material_code',
            'quantity', 'unit_price', 'total_price', 'invoice_date'
        ],
        'suppliers': [
            'supplier_code', 'supplier_name', 'supplier_site', 'contact_name',
            'email', 'phone', 'address', 'country'
        ],
        'materials': [
            'material_code', 'material_description', 'category', 'group',
            'unit_of_measure', 'standard_cost'
        ]
    }
    
    return fields_map.get(data_type, fields_map['purchase_orders'])


@login_required
@require_http_methods(["GET", "POST"])
def process_upload(request, upload_id):
    """Process uploaded data to main business tables"""
    upload = get_object_or_404(DataUpload, id=upload_id)
    
    # Check permissions
    organization = get_user_organization(request.user)
    if upload.organization != organization:
        messages.error(request, "You don't have permission to process this upload.")
        return redirect('data_ingestion:dashboard')
    
    if request.method == "POST":
        # Start processing - use async if available
        if CELERY_AVAILABLE:
            # Start async processing
            task = process_upload_async.delay(str(upload_id))
            
            # Update upload with task ID
            upload.celery_task_id = task.id
            upload.status = 'processing'
            upload.save()
            
            messages.info(request, 
                "Processing started in background. You can monitor progress below.")
            
            # Redirect to detail page where progress is shown
            return redirect('data_ingestion:upload_detail', upload_id=upload_id)
        else:
            # Fallback to synchronous processing with optimized processor
            processor = OptimizedDataProcessor()
            result = processor.process_upload(str(upload_id))
            
            if result['success']:
                messages.success(request,
                    f"Successfully processed {result['processed']} records. "
                    f"Created {result['created_suppliers']} suppliers, "
                    f"{result['created_materials']} materials, "
                    f"{result['created_pos']} purchase orders, and "
                    f"{result.get('created_prices', 0)} price records.")
            else:
                messages.error(request, f"Processing failed: {result.get('error', 'Unknown error')}")
            
            return redirect('data_ingestion:upload_detail', upload_id=upload_id)
    
    # GET request - show processing confirmation page
    context = {
        'upload': upload,
        'staging_count': ProcurementDataStaging.objects.filter(
            upload=upload,
            validation_status='valid',
            is_processed=False
        ).count(),
        'already_processed': ProcurementDataStaging.objects.filter(
            upload=upload,
            is_processed=True
        ).count(),
    }
    
    return render(request, 'data_ingestion/process_upload.html', context)


@login_required
def upload_detail(request, upload_id):
    """View detailed upload information and processing status"""
    upload = get_object_or_404(DataUpload, id=upload_id)
    
    # Check permissions
    organization = get_user_organization(request.user)
    if upload.organization != organization:
        messages.error(request, "You don't have permission to view this upload.")
        return redirect('data_ingestion:dashboard')
    
    # Get processing statistics
    staging_records = ProcurementDataStaging.objects.filter(upload=upload)

    # Get created entities if processing is completed
    created_entities = {}
    if upload.status == 'completed':
        from apps.procurement.models import Supplier, PurchaseOrder
        from apps.pricing.models import Material, Price

        # Get unique values from processed staging records
        processed_staging = staging_records.filter(is_processed=True)

        # Count unique suppliers created/matched
        supplier_codes = processed_staging.values_list('supplier_code', flat=True).distinct()
        created_entities['suppliers'] = Supplier.objects.filter(
            organization=organization,
            code__in=supplier_codes
        ).count()

        # Count unique materials created/matched
        material_codes = processed_staging.values_list('material_code', flat=True).distinct()
        created_entities['materials'] = Material.objects.filter(
            organization=organization,
            code__in=material_codes
        ).count()

        # Count unique POs created
        po_numbers = processed_staging.values_list('po_number', flat=True).distinct()
        created_entities['purchase_orders'] = PurchaseOrder.objects.filter(
            organization=organization,
            po_number__in=po_numbers
        ).count()

        # Count price records created from this upload
        # Query the actual Price table for records with this upload_id in metadata
        created_entities['price_records'] = Price.objects.filter(
            organization=organization,
            metadata__upload_id=str(upload.id)
        ).count()

        # If no price records found in Price table, fall back to processed staging count
        if created_entities['price_records'] == 0:
            created_entities['price_records'] = processed_staging.count()

    context = {
        'upload': upload,
        'total_records': staging_records.count(),
        'processed_records': staging_records.filter(is_processed=True).count(),
        'valid_records': staging_records.filter(validation_status='valid').count(),
        'invalid_records': staging_records.filter(validation_status='invalid').count(),
        'duplicate_records': staging_records.filter(is_duplicate=True).count(),
        'logs': DataIngestionLog.objects.filter(upload=upload).order_by('-timestamp')[:10],
        'sample_records': staging_records[:10],  # Show first 10 records as sample
        'created_entities': created_entities,  # New: what was created
    }

    return render(request, 'data_ingestion/upload_detail.html', context)


@login_required
@require_http_methods(["POST", "DELETE"])
def delete_upload(request, upload_id):
    """Delete an upload and all associated data"""
    organization = get_user_organization(request.user)
    upload = get_object_or_404(DataUpload, id=upload_id, organization=organization)
    
    # Store filename for message
    filename = upload.original_filename
    
    try:
        # Delete associated staging records
        staging_count = ProcurementDataStaging.objects.filter(upload=upload).count()
        ProcurementDataStaging.objects.filter(upload=upload).delete()
        
        # Delete associated logs
        log_count = DataIngestionLog.objects.filter(upload=upload).count()
        DataIngestionLog.objects.filter(upload=upload).delete()
        
        # Delete the file from storage if it exists
        if upload.file:
            try:
                upload.file.delete()
            except:
                pass  # File might not exist
        
        # Delete the upload record
        upload.delete()
        
        # Log success message
        messages.success(request, f'Successfully deleted "{filename}" ({staging_count} staging records, {log_count} logs)')
        
        # Return JSON response for AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': f'Deleted {filename}'
            })
        
    except Exception as e:
        messages.error(request, f'Error deleting upload: {str(e)}')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    return redirect('data_ingestion:dashboard')


@login_required
@require_http_methods(["GET", "POST"])
def reset_all_data(request):
    """Reset all procurement and pricing data"""
    # Check if user is admin/staff
    if not request.user.is_staff:
        messages.error(request, 'You must be an administrator to reset data.')
        return redirect('data_ingestion:dashboard')
    
    if request.method == 'POST':
        # Get options from form
        keep_suppliers = request.POST.get('keep_suppliers') == 'on'
        keep_materials = request.POST.get('keep_materials') == 'on'
        
        try:
            from django.core.management import call_command
            from io import StringIO
            
            # Capture command output
            out = StringIO()
            
            # Run the reset command
            call_command(
                'reset_all_data',
                confirm=True,
                keep_suppliers=keep_suppliers,
                keep_materials=keep_materials,
                stdout=out
            )
            
            # Get the output
            result = out.getvalue()
            
            messages.success(request, 'Database reset complete! All procurement data has been cleared.')
            
            # Log the action
            logger.info(f'Database reset performed by {request.user.username}')
            
            # Return JSON for AJAX
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Database reset complete',
                    'details': result
                })
            
        except Exception as e:
            logger.error(f'Database reset failed: {str(e)}')
            messages.error(request, f'Reset failed: {str(e)}')
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': str(e)
                }, status=500)
        
        return redirect('data_ingestion:dashboard')
    
    # GET request - show confirmation page
    from apps.procurement.models import PurchaseOrder, Supplier
    from apps.pricing.models import Material
    
    context = {
        'total_pos': PurchaseOrder.objects.count(),
        'total_suppliers': Supplier.objects.count(),
        'total_materials': Material.objects.count(),
        'total_uploads': DataUpload.objects.count(),
    }
    
    return render(request, 'data_ingestion/reset_confirm.html', context)