"""
Management command to process data upload queue
Can be run as a background service in production
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.data_ingestion.models import DataUpload
from apps.data_ingestion.services.optimized_processor import OptimizedDataProcessor
import time
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Process data upload queue continuously'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--once',
            action='store_true',
            help='Process queue once and exit (instead of continuous loop)'
        )
        parser.add_argument(
            '--interval',
            type=int,
            default=5,
            help='Interval in seconds between queue checks (default: 5)'
        )
    
    def handle(self, *args, **options):
        once = options['once']
        interval = options['interval']
        
        processor = OptimizedDataProcessor()
        
        self.stdout.write(self.style.SUCCESS(
            f"{'Running once' if once else f'Starting queue processor (checking every {interval} seconds)'}"
        ))
        
        while True:
            # Get uploads ready for processing
            ready_uploads = DataUpload.objects.filter(
                status__in=['ready_to_process', 'mapping']
            ).exclude(
                column_mapping__isnull=True
            ).exclude(
                column_mapping={}
            )
            
            if ready_uploads.exists():
                self.stdout.write(f"Found {ready_uploads.count()} uploads to process")
                
                for upload in ready_uploads:
                    self.stdout.write(f"Processing: {upload.original_filename} (ID: {upload.id})")
                    
                    # Update status
                    upload.status = 'processing'
                    upload.save()
                    
                    try:
                        # Process the upload
                        start_time = time.time()
                        result = processor.process_upload(str(upload.id))
                        duration = time.time() - start_time
                        
                        if result.get('success'):
                            upload.status = 'completed'
                            upload.processed_rows = result.get('processed', 0)
                            upload.completed_at = timezone.now()
                            
                            self.stdout.write(self.style.SUCCESS(
                                f"  ✓ Processed {result['processed']} records in {duration:.2f}s"
                            ))
                            
                            # Log statistics
                            if result.get('created_suppliers'):
                                self.stdout.write(f"    - Created {result['created_suppliers']} suppliers")
                            if result.get('created_materials'):
                                self.stdout.write(f"    - Created {result['created_materials']} materials")
                            if result.get('created_pos'):
                                self.stdout.write(f"    - Created {result['created_pos']} purchase orders")
                            if result.get('duplicates'):
                                self.stdout.write(f"    - Skipped {result['duplicates']} duplicates")
                                
                        else:
                            upload.status = 'failed'
                            upload.error_message = result.get('error', 'Processing failed')
                            self.stdout.write(self.style.ERROR(
                                f"  ✗ Failed: {result.get('error', 'Unknown error')}"
                            ))
                        
                        upload.save()
                        
                    except Exception as e:
                        logger.error(f"Error processing upload {upload.id}: {str(e)}")
                        upload.status = 'failed'
                        upload.error_message = str(e)
                        upload.save()
                        
                        self.stdout.write(self.style.ERROR(
                            f"  ✗ Error: {str(e)}"
                        ))
            
            # Exit if running once
            if once:
                break
            
            # Sleep before next check
            time.sleep(interval)
        
        self.stdout.write(self.style.SUCCESS("Queue processing completed"))