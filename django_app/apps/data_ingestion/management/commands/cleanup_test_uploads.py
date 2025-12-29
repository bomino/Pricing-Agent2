"""
Management command to cleanup test uploads and data
"""
from django.core.management.base import BaseCommand
from django.db.models import Q
from apps.data_ingestion.models import DataUpload, ProcurementDataStaging, DataIngestionLog
from apps.procurement.models import PurchaseOrder, Supplier
from apps.pricing.models import Material


class Command(BaseCommand):
    help = 'Cleanup test uploads and generated test data'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Delete ALL uploads (use with caution)'
        )
        parser.add_argument(
            '--test-only',
            action='store_true',
            help='Delete only test uploads (test, basic_test, edge_, fuzzy_, etc.)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )
    
    def handle(self, *args, **options):
        delete_all = options.get('all')
        test_only = options.get('test_only', True)
        dry_run = options.get('dry_run')
        
        self.stdout.write('='*60)
        self.stdout.write('CLEANUP TEST UPLOADS')
        self.stdout.write('='*60)
        
        if dry_run:
            self.stdout.write(self.style.WARNING('[DRY RUN MODE - No data will be deleted]'))
        
        # Find uploads to delete
        if delete_all:
            uploads = DataUpload.objects.all()
            self.stdout.write(self.style.WARNING('Deleting ALL uploads'))
        else:
            # Test patterns
            test_patterns = [
                Q(original_filename__icontains='test'),
                Q(original_filename__istartswith='edge_'),
                Q(original_filename__istartswith='fuzzy_'),
                Q(original_filename__istartswith='basic_'),
                Q(original_filename='sample_procurement_data.csv'),
            ]
            
            query = test_patterns[0]
            for pattern in test_patterns[1:]:
                query |= pattern
            
            uploads = DataUpload.objects.filter(query)
            self.stdout.write('Deleting test uploads only')
        
        # Count what will be deleted
        upload_count = uploads.count()
        
        if upload_count == 0:
            self.stdout.write(self.style.SUCCESS('No uploads to delete'))
            return
        
        # Count associated records
        staging_count = 0
        log_count = 0
        file_count = 0
        
        self.stdout.write(f'\nFound {upload_count} upload(s) to delete:')
        self.stdout.write('-'*60)
        
        for upload in uploads:
            staging = ProcurementDataStaging.objects.filter(upload=upload).count()
            logs = DataIngestionLog.objects.filter(upload=upload).count()
            staging_count += staging
            log_count += logs
            
            if upload.file:
                file_count += 1
            
            self.stdout.write(f'{upload.original_filename}')
            self.stdout.write(f'  - Status: {upload.status}')
            self.stdout.write(f'  - Staging records: {staging}')
            self.stdout.write(f'  - Logs: {logs}')
            self.stdout.write(f'  - Has file: {"Yes" if upload.file else "No"}')
            self.stdout.write('')
        
        # Summary
        self.stdout.write('='*60)
        self.stdout.write('SUMMARY OF DATA TO DELETE:')
        self.stdout.write('='*60)
        self.stdout.write(f'Uploads: {upload_count}')
        self.stdout.write(f'Staging records: {staging_count}')
        self.stdout.write(f'Log entries: {log_count}')
        self.stdout.write(f'Files: {file_count}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n[DRY RUN - No data was deleted]'))
            return
        
        # Confirm deletion
        if not delete_all:
            confirm = input('\nProceed with deletion? (yes/no): ')
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.WARNING('Deletion cancelled'))
                return
        
        # Perform deletion
        self.stdout.write('\nDeleting data...')
        
        deleted_files = 0
        for upload in uploads:
            # Delete file from storage
            if upload.file:
                try:
                    upload.file.delete()
                    deleted_files += 1
                except:
                    pass
        
        # Delete staging records
        deleted_staging = ProcurementDataStaging.objects.filter(
            upload__in=uploads
        ).delete()[0]
        
        # Delete logs
        deleted_logs = DataIngestionLog.objects.filter(
            upload__in=uploads
        ).delete()[0]
        
        # Delete uploads
        deleted_uploads = uploads.delete()[0]
        
        # Also clean up auto-generated test data
        deleted_suppliers = 0
        deleted_materials = 0
        deleted_pos = 0
        
        if test_only or delete_all:
            # Delete auto-generated suppliers
            auto_suppliers = Supplier.objects.filter(
                Q(code__startswith='AUTO_') | 
                Q(code__startswith='SUP') |
                Q(name__regex=r'^Supplier \d+$')
            )
            deleted_suppliers = auto_suppliers.delete()[0]
            
            # Delete auto-generated materials
            auto_materials = Material.objects.filter(
                Q(code__startswith='MAT_') |
                Q(code__regex=r'^MAT\d{4}$') |
                Q(name__regex=r'^Material \d+')
            )
            deleted_materials = auto_materials.delete()[0]
            
            # Delete test POs
            test_pos = PurchaseOrder.objects.filter(
                Q(po_number__startswith='PO-TEST-') |
                Q(po_number__startswith='PO-')
            )
            deleted_pos = test_pos.delete()[0]
        
        # Final summary
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('CLEANUP COMPLETED'))
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(f'[OK] Deleted {deleted_uploads} uploads')
        self.stdout.write(f'[OK] Deleted {deleted_staging} staging records')
        self.stdout.write(f'[OK] Deleted {deleted_logs} log entries')
        self.stdout.write(f'[OK] Deleted {deleted_files} files')
        
        if deleted_suppliers or deleted_materials or deleted_pos:
            self.stdout.write(f'\nAuto-generated data cleaned:')
            self.stdout.write(f'[OK] Deleted {deleted_suppliers} test suppliers')
            self.stdout.write(f'[OK] Deleted {deleted_materials} test materials')
            self.stdout.write(f'[OK] Deleted {deleted_pos} test purchase orders')
        
        # Show remaining uploads
        remaining = DataUpload.objects.count()
        if remaining > 0:
            self.stdout.write(f'\n{remaining} upload(s) remaining in system')