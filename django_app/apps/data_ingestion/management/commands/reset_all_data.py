"""
Management command to reset all procurement and pricing data
WARNING: This will delete all data except users and organizations
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone


class Command(BaseCommand):
    help = 'Reset all procurement and pricing data (keeps users and organizations)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Skip confirmation prompt',
        )
        parser.add_argument(
            '--keep-suppliers',
            action='store_true',
            help='Keep supplier master data',
        )
        parser.add_argument(
            '--keep-materials',
            action='store_true',
            help='Keep material master data',
        )

    def handle(self, *args, **options):
        if not options['confirm']:
            self.stdout.write(self.style.WARNING(
                '\n⚠️  WARNING: This will DELETE all procurement and pricing data!\n'
                'This includes:\n'
                '  - Purchase Orders and Order Lines\n'
                '  - RFQs and Quotes\n'
                '  - Price History\n'
                '  - Data Upload Records\n'
                '  - Staging Data\n'
            ))
            
            if not options['keep_suppliers']:
                self.stdout.write('  - All Suppliers\n')
            if not options['keep_materials']:
                self.stdout.write('  - All Materials and Categories\n')
            
            confirmation = input('\nType "RESET" to confirm: ')
            if confirmation != 'RESET':
                self.stdout.write(self.style.ERROR('Reset cancelled.'))
                return

        self.stdout.write(self.style.WARNING('Starting data reset...'))
        
        try:
            with transaction.atomic():
                # Import models
                from apps.procurement.models import (
                    PurchaseOrder, PurchaseOrderLine, 
                    RFQ, RFQItem, Quote, QuoteItem,
                    Supplier
                )
                from apps.pricing.models import (
                    Material, Price, PriceBenchmark, 
                    PriceAlert, Category, PriceHistory
                )
                from apps.data_ingestion.models import (
                    DataUpload, ProcurementDataStaging,
                    DataMappingTemplate, DataIngestionLog
                )
                from apps.analytics.models import Report
                
                # Delete transactional data
                deleted_counts = {}
                
                # Purchase Orders
                count = PurchaseOrderLine.objects.all().delete()[0]
                deleted_counts['PurchaseOrderLines'] = count
                self.stdout.write(f'  ✓ Deleted {count} purchase order lines')
                
                count = PurchaseOrder.objects.all().delete()[0]
                deleted_counts['PurchaseOrders'] = count
                self.stdout.write(f'  ✓ Deleted {count} purchase orders')
                
                # RFQs and Quotes
                count = QuoteItem.objects.all().delete()[0]
                deleted_counts['QuoteItems'] = count
                self.stdout.write(f'  ✓ Deleted {count} quote items')
                
                count = Quote.objects.all().delete()[0]
                deleted_counts['Quotes'] = count
                self.stdout.write(f'  ✓ Deleted {count} quotes')
                
                count = RFQItem.objects.all().delete()[0]
                deleted_counts['RFQItems'] = count
                self.stdout.write(f'  ✓ Deleted {count} RFQ items')
                
                count = RFQ.objects.all().delete()[0]
                deleted_counts['RFQs'] = count
                self.stdout.write(f'  ✓ Deleted {count} RFQs')
                
                # Pricing data
                count = Price.objects.all().delete()[0]
                deleted_counts['Prices'] = count
                self.stdout.write(f'  ✓ Deleted {count} price records')
                
                count = PriceBenchmark.objects.all().delete()[0]
                deleted_counts['Benchmarks'] = count
                self.stdout.write(f'  ✓ Deleted {count} benchmarks')
                
                count = PriceAlert.objects.all().delete()[0]
                deleted_counts['Alerts'] = count
                self.stdout.write(f'  ✓ Deleted {count} alerts')
                
                count = PriceHistory.objects.all().delete()[0]
                deleted_counts['PriceHistory'] = count
                self.stdout.write(f'  ✓ Deleted {count} price history records')
                
                # Data ingestion
                count = ProcurementDataStaging.objects.all().delete()[0]
                deleted_counts['StagingRecords'] = count
                self.stdout.write(f'  ✓ Deleted {count} staging records')
                
                count = DataUpload.objects.all().delete()[0]
                deleted_counts['DataUploads'] = count
                self.stdout.write(f'  ✓ Deleted {count} data uploads')
                
                # Analytics
                count = Report.objects.all().delete()[0]
                deleted_counts['Reports'] = count
                self.stdout.write(f'  ✓ Deleted {count} reports')
                
                # Master data (optional)
                if not options['keep_materials']:
                    count = Material.objects.all().delete()[0]
                    deleted_counts['Materials'] = count
                    self.stdout.write(f'  ✓ Deleted {count} materials')
                    
                    count = Category.objects.all().delete()[0]
                    deleted_counts['Categories'] = count
                    self.stdout.write(f'  ✓ Deleted {count} categories')
                
                if not options['keep_suppliers']:
                    count = Supplier.objects.all().delete()[0]
                    deleted_counts['Suppliers'] = count
                    self.stdout.write(f'  ✓ Deleted {count} suppliers')
                
                # Summary
                total_deleted = sum(deleted_counts.values())
                self.stdout.write(self.style.SUCCESS(
                    f'\n✅ Reset complete! Deleted {total_deleted} total records.'
                ))
                
                # Show what remains
                self.stdout.write('\n📊 Remaining data:')
                from apps.core.models import Organization
                from django.contrib.auth.models import User
                self.stdout.write(f'  - Organizations: {Organization.objects.count()}')
                self.stdout.write(f'  - Users: {User.objects.count()}')
                
                if options['keep_suppliers']:
                    self.stdout.write(f'  - Suppliers: {Supplier.objects.count()}')
                if options['keep_materials']:
                    self.stdout.write(f'  - Materials: {Material.objects.count()}')
                    self.stdout.write(f'  - Categories: {Category.objects.count()}')
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error during reset: {str(e)}'))
            raise