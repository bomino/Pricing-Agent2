"""
Management command to test the data integration pipeline
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.data_ingestion.models import DataUpload, ProcurementDataStaging
from apps.data_ingestion.services.data_processor import DataProcessor
from apps.core.models import Organization
from apps.procurement.models import PurchaseOrder, Supplier
from apps.pricing.models import Material
import pandas as pd
import io

User = get_user_model()


class Command(BaseCommand):
    help = 'Test the complete data integration pipeline'

    def handle(self, *args, **options):
        self.stdout.write("Testing Data Integration Pipeline...")
        
        # 1. Setup test data
        self.stdout.write("1. Setting up test organization and user...")
        org, _ = Organization.objects.get_or_create(
            name="Test Organization",
            defaults={'code': 'TEST01'}
        )
        
        user, _ = User.objects.get_or_create(
            username='testuser',
            defaults={
                'email': 'test@example.com',
                'is_staff': True
            }
        )
        
        # Ensure user has profile with organization
        if hasattr(user, 'profile'):
            user.profile.organization = org
            user.profile.save()
        
        # 2. Create sample data
        self.stdout.write("2. Creating sample CSV data...")
        csv_data = """PO_Number,Supplier_Name,Material_Description,Quantity,Unit_Price,Currency,Purchase_Date
PO-TEST-001,Test Supplier Inc,Test Material 1,100,25.50,USD,2024-01-15
PO-TEST-002,Another Supplier LLC,Test Material 2,50,120.00,USD,2024-01-16
PO-TEST-003,Test Supplier Inc,Test Material 3,75,85.00,USD,2024-01-17"""
        
        # 3. Simulate file upload
        self.stdout.write("3. Creating upload record...")
        file_content = csv_data.encode('utf-8')
        upload = DataUpload.objects.create(
            organization=org,
            uploaded_by=user,
            original_filename='test_pipeline.csv',
            file_format='csv',
            file_size=len(file_content),
            data_type='purchase_orders',
            status='pending'
        )
        
        # 4. Parse CSV and create staging records
        self.stdout.write("4. Parsing CSV and creating staging records...")
        df = pd.read_csv(io.StringIO(csv_data))
        
        for idx, row in df.iterrows():
            ProcurementDataStaging.objects.create(
                upload=upload,
                row_number=idx + 1,
                raw_data=row.to_dict(),  # Store the raw row data
                po_number=row.get('PO_Number'),
                supplier_name=row.get('Supplier_Name'),
                material_description=row.get('Material_Description'),
                quantity=float(row.get('Quantity', 0)),
                unit_price=float(row.get('Unit_Price', 0)),
                currency=row.get('Currency', 'USD'),
                purchase_date=pd.to_datetime(row.get('Purchase_Date')).date() if pd.notna(row.get('Purchase_Date')) else None,
                validation_status='valid',
                is_processed=False
            )
        
        upload.total_rows = len(df)
        upload.status = 'validated'
        upload.save()
        
        # 5. Show current state
        self.stdout.write("\n=== Before Processing ===")
        self.stdout.write(f"Staging Records: {ProcurementDataStaging.objects.filter(upload=upload).count()}")
        self.stdout.write(f"Suppliers: {Supplier.objects.count()}")
        self.stdout.write(f"Materials: {Material.objects.count()}")
        self.stdout.write(f"Purchase Orders: {PurchaseOrder.objects.count()}")
        
        # 6. Process the upload
        self.stdout.write("\n5. Processing upload through pipeline...")
        processor = DataProcessor()
        result = processor.process_upload(str(upload.id))
        
        # 7. Show results
        self.stdout.write("\n=== Processing Results ===")
        if result['success']:
            self.stdout.write(self.style.SUCCESS(f"✓ Successfully processed {result['processed']} records"))
            self.stdout.write(f"  - Created {result['created_suppliers']} new suppliers")
            self.stdout.write(f"  - Matched {result['matched_suppliers']} existing suppliers")
            self.stdout.write(f"  - Created {result['created_materials']} new materials")
            self.stdout.write(f"  - Matched {result['matched_materials']} existing materials")
            self.stdout.write(f"  - Created {result['created_pos']} purchase orders")
            self.stdout.write(f"  - Skipped {result['skipped']} duplicate POs")
        else:
            self.stdout.write(self.style.ERROR(f"✗ Processing failed: {result.get('error')}"))
        
        # 8. Show final state
        self.stdout.write("\n=== After Processing ===")
        self.stdout.write(f"Staging Records Processed: {ProcurementDataStaging.objects.filter(upload=upload, is_processed=True).count()}")
        self.stdout.write(f"Total Suppliers: {Supplier.objects.count()}")
        self.stdout.write(f"Total Materials: {Material.objects.count()}")
        self.stdout.write(f"Total Purchase Orders: {PurchaseOrder.objects.count()}")
        
        # 9. Show sample data
        self.stdout.write("\n=== Sample Data Created ===")
        for po in PurchaseOrder.objects.filter(organization=org)[:3]:
            self.stdout.write(f"PO: {po.po_number} | Supplier: {po.supplier.name if po.supplier else 'N/A'} | Total: ${po.total_amount}")
            for line in po.lines.all()[:2]:
                self.stdout.write(f"  - {line.material.description if line.material else 'Unknown'}: {line.quantity} @ ${line.unit_price}")
        
        self.stdout.write(self.style.SUCCESS("\n✓ Pipeline test completed!"))