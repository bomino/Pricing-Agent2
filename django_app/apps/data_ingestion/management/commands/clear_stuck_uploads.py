"""
Management command to clear stuck/processing uploads
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.data_ingestion.models import DataUpload, ProcurementDataStaging, DataIngestionLog


class Command(BaseCommand):
    help = 'Clear stuck uploads and reset their status'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Clear all processing uploads'
        )
        parser.add_argument(
            '--upload-id',
            type=str,
            help='Specific upload ID to clear'
        )
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Reset to pending status (default is to mark as failed)'
        )
    
    def handle(self, *args, **options):
        clear_all = options.get('all')
        upload_id = options.get('upload_id')
        reset = options.get('reset')
        
        # Find stuck uploads
        if upload_id:
            uploads = DataUpload.objects.filter(id=upload_id)
        elif clear_all:
            uploads = DataUpload.objects.filter(
                status__in=['processing', 'validating', 'mapping']
            )
        else:
            # Get uploads that have been processing for more than 5 minutes
            cutoff = timezone.now() - timezone.timedelta(minutes=5)
            uploads = DataUpload.objects.filter(
                status='processing',
                processing_started_at__lt=cutoff
            )
        
        if not uploads.exists():
            self.stdout.write(self.style.SUCCESS('No stuck uploads found'))
            return
        
        self.stdout.write(self.style.WARNING(f'Found {uploads.count()} stuck upload(s)'))
        
        for upload in uploads:
            self.stdout.write(f'\nProcessing upload: {upload.id}')
            self.stdout.write(f'  File: {upload.original_filename}')
            self.stdout.write(f'  Status: {upload.status}')
            self.stdout.write(f'  Total rows: {upload.total_rows}')
            self.stdout.write(f'  Processed rows: {upload.processed_rows}')
            
            if upload.processing_started_at:
                duration = (timezone.now() - upload.processing_started_at).total_seconds()
                self.stdout.write(f'  Processing time: {duration:.0f} seconds')
            
            # Clear staging records
            staging_count = ProcurementDataStaging.objects.filter(upload=upload).count()
            if staging_count > 0:
                self.stdout.write(f'  Staging records: {staging_count}')
                
                if reset:
                    # Reset staging records
                    ProcurementDataStaging.objects.filter(upload=upload).update(
                        is_processed=False,
                        processed_at=None,
                        validation_status='pending'
                    )
                    self.stdout.write(self.style.SUCCESS(f'  [OK] Reset {staging_count} staging records'))
                else:
                    # Delete staging records for failed uploads
                    ProcurementDataStaging.objects.filter(upload=upload).delete()
                    self.stdout.write(self.style.SUCCESS(f'  [OK] Deleted {staging_count} staging records'))
            
            # Update upload status
            if reset:
                upload.status = 'pending'
                upload.processed_rows = 0
                upload.failed_rows = 0
                upload.duplicate_rows = 0
                upload.processing_started_at = None
                upload.processing_completed_at = None
                upload.processing_duration_seconds = None
                upload.processing_progress = 0
                upload.error_message = ''
                upload.celery_task_id = ''
                upload.save()
                
                # Log the reset
                DataIngestionLog.objects.create(
                    upload=upload,
                    action='upload_reset',
                    user=upload.uploaded_by,
                    message='Upload reset via management command',
                    details={'reason': 'stuck_processing'}
                )
                
                self.stdout.write(self.style.SUCCESS(f'  [OK] Reset upload to pending status'))
            else:
                upload.status = 'failed'
                upload.error_message = 'Processing terminated - stuck in processing state'
                upload.processing_completed_at = timezone.now()
                if upload.processing_started_at:
                    duration = (upload.processing_completed_at - upload.processing_started_at).total_seconds()
                    upload.processing_duration_seconds = int(duration)
                upload.save()
                
                # Log the failure
                DataIngestionLog.objects.create(
                    upload=upload,
                    action='upload_terminated',
                    user=upload.uploaded_by,
                    message='Upload terminated due to stuck processing',
                    details={'reason': 'stuck_processing', 'processed': upload.processed_rows}
                )
                
                self.stdout.write(self.style.SUCCESS(f'  [OK] Marked upload as failed'))
        
        self.stdout.write(self.style.SUCCESS(f'\n[OK] Cleared {uploads.count()} upload(s)'))
        
        # Show summary of remaining uploads
        remaining = DataUpload.objects.filter(
            status__in=['pending', 'mapping', 'validating']
        ).count()
        
        if remaining > 0:
            self.stdout.write(self.style.WARNING(f'\n{remaining} upload(s) ready for processing'))
        
        # Suggest next steps
        if reset and uploads.count() > 0:
            self.stdout.write(self.style.SUCCESS('\nNext steps:'))
            self.stdout.write('1. Visit /data-ingestion/ to view cleared uploads')
            self.stdout.write('2. Click on an upload to resume processing')
            self.stdout.write('3. The optimized processor will handle it efficiently')