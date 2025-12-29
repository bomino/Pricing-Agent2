"""
Asynchronous tasks for data ingestion processing
"""
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache
import logging

from .models import DataUpload, DataIngestionLog
from .services.optimized_processor import OptimizedDataProcessor

logger = logging.getLogger(__name__)


@shared_task(bind=True, name='data_ingestion.process_upload')
def process_upload_async(self, upload_id: str):
    """
    Process upload asynchronously with progress tracking
    
    This task runs in the background and updates progress in cache
    for real-time UI updates
    """
    try:
        # Get upload record
        upload = DataUpload.objects.get(id=upload_id)
        
        # Update task ID for tracking
        upload.celery_task_id = self.request.id
        upload.save()
        
        # Initialize processor
        processor = OptimizedDataProcessor()
        
        # Set up progress callback
        def update_progress(current, total):
            """Update progress in cache for real-time updates"""
            progress = int((current / total) * 100) if total > 0 else 0
            cache.set(f'upload_progress_{upload_id}', {
                'current': current,
                'total': total,
                'percentage': progress,
                'status': 'processing'
            }, 300)  # Cache for 5 minutes
            
            # Update Celery task state
            self.update_state(
                state='PROGRESS',
                meta={
                    'current': current,
                    'total': total,
                    'percentage': progress
                }
            )
        
        # Process with callback
        processor.progress_callback = update_progress
        result = processor.process_upload(upload_id)
        
        # Clear progress cache
        cache.delete(f'upload_progress_{upload_id}')
        
        # Log completion
        DataIngestionLog.objects.create(
            upload=upload,
            action='async_processing_completed',
            user=upload.uploaded_by,
            message=f"Async processing completed: {result['processed']} records processed",
            details=result
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error in async processing for upload {upload_id}: {str(e)}")
        
        # Update upload status
        try:
            upload = DataUpload.objects.get(id=upload_id)
            upload.status = 'failed'
            upload.error_message = str(e)
            upload.save()
            
            # Log error
            DataIngestionLog.objects.create(
                upload=upload,
                action='async_processing_failed',
                user=upload.uploaded_by,
                message=f"Async processing failed: {str(e)}"
            )
        except:
            pass
        
        # Clear progress cache
        cache.delete(f'upload_progress_{upload_id}')
        
        raise


@shared_task(name='data_ingestion.cleanup_old_uploads')
def cleanup_old_uploads():
    """
    Periodic task to clean up old failed uploads and staging data
    """
    cutoff_date = timezone.now() - timezone.timedelta(days=30)
    
    # Delete old failed uploads
    old_failed = DataUpload.objects.filter(
        status='failed',
        created_at__lt=cutoff_date
    )
    
    count = old_failed.count()
    old_failed.delete()
    
    logger.info(f"Cleaned up {count} old failed uploads")
    
    return count


# For synchronous fallback (when Celery is not available)
def process_upload_sync(upload_id: str):
    """
    Synchronous version of upload processing
    Used when Celery is not configured
    """
    processor = OptimizedDataProcessor()
    return processor.process_upload(upload_id)