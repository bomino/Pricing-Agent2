"""
Management command to check the status of the data integration pipeline
"""
from django.core.management.base import BaseCommand
from apps.data_ingestion.models import DataUpload, ProcurementDataStaging
from apps.procurement.models import PurchaseOrder, Supplier
from apps.pricing.models import Material, Price


class Command(BaseCommand):
    help = 'Check the status of the data integration pipeline'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== Data Integration Pipeline Status ==='))
        
        # Overall stats
        self.stdout.write(f'Total Uploads: {DataUpload.objects.count()}')
        self.stdout.write(f'Total Staging Records: {ProcurementDataStaging.objects.count()}')
        self.stdout.write(f'Processed Staging Records: {ProcurementDataStaging.objects.filter(is_processed=True).count()}')
        self.stdout.write(f'Total Suppliers: {Supplier.objects.count()}')
        self.stdout.write(f'Total Materials: {Material.objects.count()}')
        self.stdout.write(f'Total Purchase Orders: {PurchaseOrder.objects.count()}')
        self.stdout.write(f'Total Price History Records: {Price.objects.count()}')
        
        # Recent uploads
        self.stdout.write('\n' + self.style.SUCCESS('=== Recent Uploads ==='))
        for upload in DataUpload.objects.order_by('-created_at')[:5]:
            processed = ProcurementDataStaging.objects.filter(
                upload=upload, is_processed=True
            ).count()
            total = ProcurementDataStaging.objects.filter(upload=upload).count()
            self.stdout.write(
                f'{upload.original_filename}: {upload.status} ({processed}/{total} processed)'
            )
        
        # Recent purchase orders
        self.stdout.write('\n' + self.style.SUCCESS('=== Recent Purchase Orders ==='))
        for po in PurchaseOrder.objects.order_by('-created_at')[:5]:
            supplier_name = po.supplier.name if po.supplier else "No Supplier"
            self.stdout.write(
                f'PO {po.po_number}: {supplier_name} - ${po.total_amount} ({po.status})'
            )
        
        # Recent price records
        self.stdout.write('\n' + self.style.SUCCESS('=== Recent Price History ==='))
        for price in Price.objects.order_by('-time')[:5]:
            material_name = price.material.name if price.material else "Unknown"
            supplier_name = price.supplier.name if price.supplier else "Unknown"
            self.stdout.write(
                f'{material_name} from {supplier_name}: ${price.price} on {price.time.date()}'
            )
        
        self.stdout.write(self.style.SUCCESS('\n✓ Pipeline status check complete!'))