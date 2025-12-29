"""
Management command to test the optimized data processor
"""
import time
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from apps.core.models import Organization
from apps.data_ingestion.models import DataUpload, ProcurementDataStaging
from apps.data_ingestion.services.optimized_processor import OptimizedDataProcessor
from apps.data_ingestion.services.data_processor import DataProcessor

User = get_user_model()


class Command(BaseCommand):
    help = 'Test the optimized data processor and compare performance'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--upload-id',
            type=str,
            help='Specific upload ID to process'
        )
        parser.add_argument(
            '--compare',
            action='store_true',
            help='Compare with original processor'
        )
        parser.add_argument(
            '--create-test-data',
            action='store_true',
            help='Create test staging data'
        )
    
    def handle(self, *args, **options):
        upload_id = options.get('upload_id')
        compare = options.get('compare')
        create_test = options.get('create_test_data')
        
        if create_test:
            upload_id = self.create_test_data()
            self.stdout.write(self.style.SUCCESS(f'Created test upload: {upload_id}'))
        
        if not upload_id:
            # Get the latest upload
            upload = DataUpload.objects.filter(
                status__in=['mapping', 'pending', 'validating']
            ).first()
            
            if not upload:
                self.stdout.write(self.style.ERROR('No uploads available for processing'))
                return
            
            upload_id = str(upload.id)
        
        # Test optimized processor
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('Testing Optimized Processor'))
        self.stdout.write(self.style.SUCCESS('='*60))
        
        # Reset upload status
        upload = DataUpload.objects.get(id=upload_id)
        upload.status = 'processing'
        upload.processed_rows = 0
        upload.save()
        
        # Reset staging records
        ProcurementDataStaging.objects.filter(upload=upload).update(
            is_processed=False,
            processed_at=None
        )
        
        start_time = time.time()
        processor = OptimizedDataProcessor()
        
        # Add progress callback for visual feedback
        def show_progress(current, total):
            percent = int((current / total) * 100) if total > 0 else 0
            bar_length = 40
            filled = int(bar_length * current / total) if total > 0 else 0
            bar = '#' * filled + '-' * (bar_length - filled)
            self.stdout.write(f'\rProgress: |{bar}| {percent}% ({current}/{total})', ending='')
            self.stdout.flush()
        
        processor.progress_callback = show_progress
        
        result = processor.process_upload(upload_id)
        elapsed = time.time() - start_time
        
        self.stdout.write('')  # New line after progress bar
        
        if result.get('success'):
            self.stdout.write(self.style.SUCCESS(f'\nOptimized Processor Results:'))
            self.stdout.write(f'  Time: {elapsed:.2f} seconds')
            self.stdout.write(f'  Processed: {result["processed"]} records')
            self.stdout.write(f'  Errors: {result["errors"]}')
            self.stdout.write(f'  Duplicates: {result["duplicates"]}')
            self.stdout.write(f'  Created Suppliers: {result["created_suppliers"]}')
            self.stdout.write(f'  Created Materials: {result["created_materials"]}')
            self.stdout.write(f'  Created POs: {result["created_pos"]}')
            self.stdout.write(f'  Throughput: {result["processed"]/elapsed:.1f} records/second')
        else:
            self.stdout.write(self.style.ERROR(f'\nOptimized Processor Failed:'))
            self.stdout.write(f'  Error: {result.get("error", "Unknown error")}')
        
        if compare:
            # Test original processor for comparison
            self.stdout.write(self.style.SUCCESS('\n' + '='*60))
            self.stdout.write(self.style.SUCCESS('Testing Original Processor (for comparison)'))
            self.stdout.write(self.style.SUCCESS('='*60))
            
            # Reset again
            upload.status = 'processing'
            upload.processed_rows = 0
            upload.save()
            
            ProcurementDataStaging.objects.filter(upload=upload).update(
                is_processed=False,
                processed_at=None
            )
            
            # Clean up created records
            from apps.procurement.models import PurchaseOrder, Supplier
            from apps.pricing.models import Material
            
            PurchaseOrder.objects.filter(
                created_at__gte=timezone.now() - timezone.timedelta(minutes=5)
            ).delete()
            Supplier.objects.filter(
                code__startswith='AUTO_'
            ).delete()
            Material.objects.filter(
                code__startswith='MAT_'
            ).delete()
            
            start_time = time.time()
            old_processor = DataProcessor()
            old_result = old_processor.process_upload(upload_id)
            old_elapsed = time.time() - start_time
            
            self.stdout.write(self.style.SUCCESS(f'\nOriginal Processor Results:'))
            self.stdout.write(f'  Time: {old_elapsed:.2f} seconds')
            self.stdout.write(f'  Processed: {old_result["processed"]} records')
            self.stdout.write(f'  Throughput: {old_result["processed"]/old_elapsed:.1f} records/second')
            
            # Show improvement
            improvement = ((old_elapsed - elapsed) / old_elapsed) * 100
            speedup = old_elapsed / elapsed
            
            self.stdout.write(self.style.SUCCESS('\n' + '='*60))
            self.stdout.write(self.style.SUCCESS('Performance Comparison:'))
            self.stdout.write(self.style.SUCCESS('='*60))
            self.stdout.write(f'  Speed improvement: {improvement:.1f}%')
            self.stdout.write(f'  Speedup factor: {speedup:.1f}x faster')
            self.stdout.write(f'  Time saved: {old_elapsed - elapsed:.2f} seconds')
    
    def create_test_data(self):
        """Create test staging data for benchmarking"""
        # Get or create test organization and user
        org, _ = Organization.objects.get_or_create(
            name='Test Organization',
            defaults={'code': 'TEST'}
        )
        
        user = User.objects.filter(is_superuser=True).first()
        if not user:
            user = User.objects.create_superuser(
                username='test_admin',
                email='test@example.com',
                password='test123'
            )
        
        # Create upload
        upload = DataUpload.objects.create(
            organization=org,
            uploaded_by=user,
            original_filename='test_data.csv',
            file_format='csv',
            file_size=1024000,
            data_type='purchase_orders',
            status='validating',
            total_rows=1000
        )
        
        # Create staging records
        staging_records = []
        for i in range(1000):
            staging_records.append(
                ProcurementDataStaging(
                    upload=upload,
                    row_number=i + 1,
                    po_number=f'PO-TEST-{i:06d}',
                    supplier_name=f'Supplier {i % 50}',  # 50 unique suppliers
                    supplier_code=f'SUP{i % 50:03d}',
                    material_code=f'MAT{i % 100:04d}',  # 100 unique materials
                    material_description=f'Material {i % 100} - Test Item',
                    quantity=10 + (i % 100),
                    unit_price=100.00 + (i % 500),
                    total_price=(10 + (i % 100)) * (100.00 + (i % 500)),
                    currency='USD',
                    purchase_date=timezone.now().date(),
                    validation_status='valid',
                    raw_data={
                        'row': i,
                        'test': True
                    }
                )
            )
        
        ProcurementDataStaging.objects.bulk_create(staging_records)
        
        self.stdout.write(self.style.SUCCESS(f'Created {len(staging_records)} test staging records'))
        return str(upload.id)