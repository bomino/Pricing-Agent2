"""
Cleanup test data from previous test runs
"""
from django.core.management.base import BaseCommand
from apps.data_ingestion.models import DataUpload, ProcurementDataStaging
from apps.procurement.models import PurchaseOrder, Supplier
from apps.pricing.models import Material, Price
from apps.core.models import Organization


class Command(BaseCommand):
    help = 'Clean up test data from previous test runs'
    
    def handle(self, *args, **options):
        self.stdout.write('Cleaning up test data...')
        
        # Clean up test organization data
        test_orgs = Organization.objects.filter(code__in=['TEST_PIPELINE', 'TEST01', 'E2E001', 'INTTEST'])
        
        for org in test_orgs:
            # Delete all related data
            PurchaseOrder.objects.filter(organization=org).delete()
            Supplier.objects.filter(organization=org).delete()
            Material.objects.filter(organization=org).delete()
            Price.objects.filter(organization=org).delete()
            DataUpload.objects.filter(organization=org).delete()
            
            self.stdout.write(f'  Cleaned data for organization: {org.name}')
        
        # Clean up orphaned staging records
        ProcurementDataStaging.objects.filter(upload__organization__in=test_orgs).delete()
        
        self.stdout.write(self.style.SUCCESS('✓ Test data cleanup complete'))