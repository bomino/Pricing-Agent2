"""
Management command to process pending uploads with the optimized processor
"""
import time
from django.core.management.base import BaseCommand
from apps.data_ingestion.models import DataUpload
from apps.data_ingestion.services.optimized_processor import OptimizedDataProcessor


class Command(BaseCommand):
    help = 'Process pending uploads using the optimized processor'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--upload-id',
            type=str,
            help='Specific upload ID to process'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Process all pending uploads'
        )
    
    def handle(self, *args, **options):
        upload_id = options.get('upload_id')
        process_all = options.get('all')
        
        if upload_id:
            uploads = DataUpload.objects.filter(id=upload_id)
        elif process_all:
            uploads = DataUpload.objects.filter(status='pending')
        else:
            # Process the first pending upload
            uploads = DataUpload.objects.filter(status='pending')[:1]
        
        if not uploads.exists():
            self.stdout.write(self.style.WARNING('No pending uploads found'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'\nProcessing {uploads.count()} upload(s) with optimized processor\n'))
        
        total_start = time.time()
        total_processed = 0
        total_errors = 0
        
        for upload in uploads:
            self.stdout.write('='*60)
            self.stdout.write(f'Processing: {upload.original_filename}')
            self.stdout.write(f'Upload ID: {upload.id}')
            self.stdout.write(f'Total rows: {upload.total_rows}')
            self.stdout.write('-'*60)
            
            # Initialize processor with progress callback
            processor = OptimizedDataProcessor()
            
            # Visual progress callback
            def show_progress(current, total):
                percent = int((current / total) * 100) if total > 0 else 0
                bar_length = 40
                filled = int(bar_length * current / total) if total > 0 else 0
                bar = '#' * filled + '-' * (bar_length - filled)
                self.stdout.write(f'\rProgress: |{bar}| {percent}% ({current}/{total})', ending='')
                self.stdout.flush()
            
            processor.progress_callback = show_progress
            
            # Process the upload
            start_time = time.time()
            
            try:
                result = processor.process_upload(str(upload.id))
                elapsed = time.time() - start_time
                
                self.stdout.write('')  # New line after progress bar
                
                if result.get('success'):
                    self.stdout.write(self.style.SUCCESS('\n[OK] Processing completed successfully!'))
                    self.stdout.write(f'  Time: {elapsed:.2f} seconds')
                    self.stdout.write(f'  Processed: {result["processed"]} records')
                    self.stdout.write(f'  Errors: {result["errors"]}')
                    self.stdout.write(f'  Duplicates: {result["duplicates"]}')
                    self.stdout.write(f'  Created Suppliers: {result["created_suppliers"]}')
                    self.stdout.write(f'  Created Materials: {result["created_materials"]}')
                    self.stdout.write(f'  Created POs: {result["created_pos"]}')
                    
                    if result["processed"] > 0:
                        throughput = result["processed"] / elapsed
                        self.stdout.write(f'  Throughput: {throughput:.1f} records/second')
                    
                    total_processed += result["processed"]
                    total_errors += result["errors"]
                else:
                    self.stdout.write(self.style.ERROR(f'\n[ERROR] Processing failed: {result.get("error")}'))
                    total_errors += 1
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'\n[ERROR] Exception during processing: {str(e)}'))
                total_errors += 1
            
            self.stdout.write('')
        
        # Summary
        total_elapsed = time.time() - total_start
        
        self.stdout.write('='*60)
        self.stdout.write(self.style.SUCCESS('SUMMARY'))
        self.stdout.write('='*60)
        self.stdout.write(f'Total uploads processed: {uploads.count()}')
        self.stdout.write(f'Total records processed: {total_processed}')
        self.stdout.write(f'Total errors: {total_errors}')
        self.stdout.write(f'Total time: {total_elapsed:.2f} seconds')
        
        if total_processed > 0:
            avg_throughput = total_processed / total_elapsed
            self.stdout.write(f'Average throughput: {avg_throughput:.1f} records/second')
        
        self.stdout.write(self.style.SUCCESS('\n[OK] All uploads processed!'))
        self.stdout.write('\nNext steps:')
        self.stdout.write('1. Visit /data-ingestion/ to view processed uploads')
        self.stdout.write('2. Check the imported data in /admin/')
        self.stdout.write('3. Review any errors in the upload details')