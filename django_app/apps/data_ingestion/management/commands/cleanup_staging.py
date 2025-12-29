"""
Management command to clean up processed staging data
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.data_ingestion.models import ProcurementDataStaging


class Command(BaseCommand):
    help = 'Clean up processed staging data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Delete processed staging data older than N days (default: 7)',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Delete all processed staging data regardless of age',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )

    def handle(self, *args, **options):
        days = options['days']
        all_processed = options['all']
        dry_run = options['dry_run']
        
        # Build the query
        queryset = ProcurementDataStaging.objects.filter(is_processed=True)
        
        if not all_processed:
            cutoff_date = timezone.now() - timedelta(days=days)
            queryset = queryset.filter(processed_at__lt=cutoff_date)
            self.stdout.write(f"Finding processed staging data older than {days} days...")
        else:
            self.stdout.write("Finding all processed staging data...")
        
        # Count records
        count = queryset.count()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS("No staging data to clean up"))
            return
        
        if dry_run:
            self.stdout.write(self.style.WARNING(f"DRY RUN: Would delete {count} staging records"))
            
            # Show sample of what would be deleted
            sample = queryset[:10]
            if sample:
                self.stdout.write("\nSample of records to be deleted:")
                for record in sample:
                    self.stdout.write(f"  - Upload: {record.upload.original_filename if record.upload else 'N/A'}, "
                                    f"Row: {record.row_number}, "
                                    f"Processed: {record.processed_at}")
        else:
            # Perform deletion
            deleted, _ = queryset.delete()
            self.stdout.write(self.style.SUCCESS(f"✓ Deleted {deleted} processed staging records"))
            
            # Show remaining counts
            remaining_total = ProcurementDataStaging.objects.count()
            remaining_processed = ProcurementDataStaging.objects.filter(is_processed=True).count()
            remaining_unprocessed = ProcurementDataStaging.objects.filter(is_processed=False).count()
            
            self.stdout.write(f"\nRemaining staging data:")
            self.stdout.write(f"  Total: {remaining_total}")
            self.stdout.write(f"  Processed: {remaining_processed}")
            self.stdout.write(f"  Unprocessed: {remaining_unprocessed}")