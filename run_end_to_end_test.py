"""
End-to-End Test of Price History Implementation
This script simulates the complete upload flow programmatically
"""
import os
import sys
import django
from pathlib import Path
import json

# Add Django app to path
sys.path.insert(0, 'django_app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pricing_agent.settings_local')
django.setup()

from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from apps.data_ingestion.models import DataUpload, ProcurementDataStaging
from apps.data_ingestion.services.optimized_processor import OptimizedDataProcessor
from apps.pricing.models import Price, Material
from apps.procurement.models import Supplier, PurchaseOrder
from apps.core.models import Organization
import pandas as pd

User = get_user_model()

def run_test():
    print("\n" + "="*60)
    print("END-TO-END TEST: PRICE HISTORY IMPLEMENTATION")
    print("="*60)

    # Step 1: Setup
    print("\n[STEP 1] Setting up test environment...")

    # Get or create organization
    org, created = Organization.objects.get_or_create(
        name="Test Organization",
        defaults={'code': 'TEST'}
    )
    print(f"  - Organization: {org.name}")

    # Get or create user
    user, created = User.objects.get_or_create(
        username='testuser',
        defaults={
            'email': 'test@example.com',
            'is_active': True
        }
    )
    if created:
        user.set_password('testpass123')
        user.save()
    print(f"  - User: {user.username}")

    # Record initial counts
    initial_prices = Price.objects.count()
    initial_suppliers = Supplier.objects.count()
    initial_materials = Material.objects.count()
    initial_pos = PurchaseOrder.objects.count()

    print(f"\n[INITIAL STATE]")
    print(f"  - Price Records: {initial_prices}")
    print(f"  - Suppliers: {initial_suppliers}")
    print(f"  - Materials: {initial_materials}")
    print(f"  - Purchase Orders: {initial_pos}")

    # Step 2: Create Upload
    print("\n[STEP 2] Creating file upload...")

    # Read the test CSV file
    csv_path = Path('test_procurement_data.csv')
    with open(csv_path, 'rb') as f:
        csv_content = f.read()

    # Create uploaded file object
    uploaded_file = SimpleUploadedFile(
        name='test_procurement_data.csv',
        content=csv_content,
        content_type='text/csv'
    )

    # Create DataUpload record
    upload = DataUpload.objects.create(
        uploaded_by=user,
        organization=org,
        original_filename='test_procurement_data.csv',
        file=uploaded_file,
        file_format='csv',
        file_size=len(csv_content),
        data_type='purchase_orders',  # Using valid choice from DATA_TYPE_CHOICES
        status='pending',
        total_rows=5
    )
    print(f"  - Created upload: {upload.id}")
    print(f"  - File: {upload.original_filename}")
    print(f"  - Status: {upload.status}")

    # Step 3: Parse and Stage Data
    print("\n[STEP 3] Parsing and staging data...")

    # Read CSV using pandas
    df = pd.read_csv(csv_path)
    print(f"  - Loaded {len(df)} rows from CSV")

    # Create staging records
    staging_records = []
    for idx, row in df.iterrows():
        # Convert row to dictionary for raw_data field
        raw_data_dict = row.to_dict()

        staging = ProcurementDataStaging.objects.create(
            upload=upload,
            row_number=idx + 1,  # Row numbers start at 1
            raw_data=raw_data_dict,  # Store original row data as JSON
            po_number=row['po_number'],
            supplier_name=row['supplier_name'],
            supplier_code=row['supplier_code'],
            material_code=row['material_code'],
            material_description=row['material_description'],
            quantity=row['quantity'],
            unit_price=row['unit_price'],
            total_price=row['total_price'],
            currency=row['currency'],
            purchase_date=row['purchase_date'],
            delivery_date=row['delivery_date'],
            validation_status='valid'
        )
        staging_records.append(staging)

    print(f"  - Created {len(staging_records)} staging records")

    # Step 4: Create Column Mapping
    print("\n[STEP 4] Setting up column mappings...")

    mapping_data = {
        'po_number': 'po_number',
        'supplier_name': 'supplier_name',
        'supplier_code': 'supplier_code',
        'material_code': 'material_code',
        'material_description': 'material_description',
        'quantity': 'quantity',
        'unit_price': 'unit_price',
        'total_price': 'total_price',
        'currency': 'currency',
        'purchase_date': 'purchase_date',
        'delivery_date': 'delivery_date'
    }

    # Save mapping to upload
    upload.column_mapping = mapping_data
    upload.status = 'ready_to_process'
    upload.save()
    print(f"  - Mapping saved: {len(mapping_data)} fields")
    print(f"  - Status updated to: {upload.status}")

    # Step 5: Process Data (THE CRITICAL STEP!)
    print("\n[STEP 5] Processing data to main tables...")
    print("  This is where Price history recording happens!")

    # Initialize processor
    processor = OptimizedDataProcessor()

    # Process the data using upload_id
    result = processor.process_upload(str(upload.id))

    print(f"\n  [PROCESSING RESULTS]")
    print(f"  - Records processed: {result['processed']}")
    print(f"  - Suppliers created: {result['created_suppliers']}")
    print(f"  - Suppliers matched: {result['matched_suppliers']}")
    print(f"  - Materials created: {result['created_materials']}")
    print(f"  - Materials matched: {result['matched_materials']}")
    print(f"  - Purchase Orders created: {result['created_pos']}")
    print(f"  - PRICE RECORDS CREATED: {result.get('created_prices', 0)}")  # KEY METRIC!

    # Update upload status
    upload.status = 'completed'
    upload.processed_rows = result['processed']
    upload.save()

    # Step 6: Verify Results
    print("\n[STEP 6] Verifying results...")

    # Get final counts
    final_prices = Price.objects.count()
    final_suppliers = Supplier.objects.count()
    final_materials = Material.objects.count()
    final_pos = PurchaseOrder.objects.count()

    print(f"\n  [FINAL STATE]")
    print(f"  - Price Records: {final_prices} (+{final_prices - initial_prices})")
    print(f"  - Suppliers: {final_suppliers} (+{final_suppliers - initial_suppliers})")
    print(f"  - Materials: {final_materials} (+{final_materials - initial_materials})")
    print(f"  - Purchase Orders: {final_pos} (+{final_pos - initial_pos})")

    # Check the new price records
    print("\n  [NEW PRICE RECORDS]")
    newest_prices = Price.objects.order_by('-time')[:5]
    for price in newest_prices:
        material_name = price.material.name if price.material else "Unknown"
        supplier_name = price.supplier.name if price.supplier else "N/A"
        po_number = price.metadata.get('po_number', 'N/A') if price.metadata else 'N/A'
        print(f"  - {material_name}: ${price.price} from {supplier_name} (PO: {po_number})")

    # Step 7: Test Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    expected_new_prices = 5
    actual_new_prices = final_prices - initial_prices

    if actual_new_prices == expected_new_prices:
        print(f"[SUCCESS] All {expected_new_prices} price records were created!")
        print("[SUCCESS] Phase 1 implementation is working correctly!")
    else:
        print(f"[ISSUE] Expected {expected_new_prices} new prices, got {actual_new_prices}")

    print("\n[TEST COMPLETE]")

    return {
        'success': actual_new_prices == expected_new_prices,
        'prices_created': actual_new_prices,
        'upload_id': str(upload.id),
        'initial_prices': initial_prices,
        'final_prices': final_prices
    }

if __name__ == "__main__":
    try:
        result = run_test()
        if result['success']:
            print("\n[PASSED] End-to-end test PASSED! Price history recording is fully functional.")
        else:
            print("\n[WARNING] Test completed but needs review.")
    except Exception as e:
        print(f"\n[ERROR] Error during test: {e}")
        import traceback
        traceback.print_exc()