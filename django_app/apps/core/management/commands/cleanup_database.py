"""
Database cleanup command for production deployment
Removes test data while preserving essential records
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth.models import User
from apps.core.models import Organization
from apps.data_ingestion.models import DataUpload, ProcurementDataStaging
from apps.analytics.models import Report
from apps.procurement.models import Supplier, PurchaseOrder, RFQ, Quote
from apps.pricing.models import Material, Price
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Clean up test data from database while preserving essential records'

    def add_arguments(self, parser):
        parser.add_argument(
            '--keep-admin',
            action='store_true',
            help='Keep admin/superuser accounts',
        )
        parser.add_argument(
            '--keep-org',
            type=str,
            help='Keep specific organization by code',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        keep_admin = options.get('keep_admin', False)
        keep_org_code = options.get('keep_org')
        dry_run = options.get('dry_run', False)

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No data will be deleted'))

        # Clean up staging data
        staging_count = ProcurementDataStaging.objects.all().count()
        if staging_count > 0:
            self.stdout.write(f'Found {staging_count} staging records')
            if not dry_run:
                ProcurementDataStaging.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f'Deleted {staging_count} staging records'))

        # Clean up file uploads
        upload_count = DataUpload.objects.all().count()
        if upload_count > 0:
            self.stdout.write(f'Found {upload_count} file upload records')
            if not dry_run:
                DataUpload.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f'Deleted {upload_count} file upload records'))

        # Clean up test organizations
        orgs_to_delete = Organization.objects.all()
        if keep_org_code:
            orgs_to_delete = orgs_to_delete.exclude(code=keep_org_code)
            self.stdout.write(f'Keeping organization: {keep_org_code}')
        
        # Always keep at least one organization for the system
        if orgs_to_delete.count() == Organization.objects.count():
            # Keep the first organization or create a default one
            default_org = Organization.objects.first()
            if not default_org:
                default_org = Organization.objects.create(
                    name='Default Organization',
                    code='DEFAULT'
                )
                self.stdout.write(self.style.SUCCESS('Created default organization'))
            orgs_to_delete = orgs_to_delete.exclude(id=default_org.id)
            self.stdout.write(f'Keeping default organization: {default_org.code}')

        org_count = orgs_to_delete.count()
        if org_count > 0:
            self.stdout.write(f'Found {org_count} organizations to remove')
            if not dry_run:
                # Delete related data first
                for org in orgs_to_delete:
                    # Delete procurement data
                    Quote.objects.filter(organization=org).delete()
                    RFQ.objects.filter(organization=org).delete()
                    PurchaseOrder.objects.filter(organization=org).delete()
                    Supplier.objects.filter(organization=org).delete()
                    
                    # Delete pricing data
                    Price.objects.filter(organization=org).delete()
                    Material.objects.filter(organization=org).delete()
                    
                    # Delete analytics data
                    Report.objects.filter(organization=org).delete()
                
                orgs_to_delete.delete()
                self.stdout.write(self.style.SUCCESS(f'Deleted {org_count} organizations and related data'))

        # Clean up test users
        users_to_delete = User.objects.filter(username__icontains='test')
        if keep_admin:
            users_to_delete = users_to_delete.exclude(is_superuser=True)
            self.stdout.write('Keeping admin/superuser accounts')
        
        user_count = users_to_delete.count()
        if user_count > 0:
            self.stdout.write(f'Found {user_count} test users')
            if not dry_run:
                users_to_delete.delete()
                self.stdout.write(self.style.SUCCESS(f'Deleted {user_count} test users'))

        # Summary
        self.stdout.write(self.style.SUCCESS('\n=== Database Cleanup Summary ==='))
        self.stdout.write(f'Staging records: {staging_count}')
        self.stdout.write(f'File uploads: {upload_count}')
        self.stdout.write(f'Organizations: {org_count}')
        self.stdout.write(f'Test users: {user_count}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\nDRY RUN - No changes were made'))
        else:
            self.stdout.write(self.style.SUCCESS('\nDatabase cleanup completed successfully'))