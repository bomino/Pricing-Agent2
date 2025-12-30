#!/usr/bin/env python
"""
Test Data Upload Functionality
Tests the data ingestion module with realistic procurement data
"""

import os
import sys
import django
from datetime import datetime
import pandas as pd

# Setup Django environment
sys.path.insert(0, 'django_app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pricing_agent.settings_local')
django.setup()

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.data_ingestion.models import DataUpload, ProcurementDataStaging
from apps.core.models import Organization

User = get_user_model()

def test_data_upload():
    """Test the data upload and ingestion process"""

    print("\n" + "="*60)
    print("TESTING DATA UPLOAD FUNCTIONALITY")
    print("="*60 + "\n")

    # Get user and organization
    try:
        user = User.objects.get(username='bomino')
        org = Organization.objects.get(code='VSTX001')
        print(f"[OK] Using user: {user.username}")
        print(f"[OK] Organization: {org.name}")
    except Exception as e:
        print(f"[ERROR] Setup failed: {e}")
        return

    # Read the test CSV file
    csv_file_path = "test_procurement_data.csv"
    if not os.path.exists(csv_file_path):
        print(f"[ERROR] Test file not found: {csv_file_path}")
        return

    # Read CSV to check data
    df = pd.read_csv(csv_file_path)
    print(f"\n[INFO] Test CSV Data Summary:")
    print(f"  - Total rows: {len(df)}")
    print(f"  - Columns: {len(df.columns)}")
    print(f"  - Date range: {df['purchase_date'].min()} to {df['purchase_date'].max()}")
    print(f"  - Unique POs: {df['po_number'].nunique()}")
    print(f"  - Unique Suppliers: {df['supplier_name'].nunique()}")
    print(f"  - Total value: ${df['total_price'].sum():,.2f}")

    # Simulate file upload
    print("\n[TEST] Creating DataUpload record...")
    try:
        with open(csv_file_path, 'rb') as f:
            file_content = f.read()

        # Create upload record
        upload = DataUpload.objects.create(
            organization=org,
            uploaded_by=user,
            file=SimpleUploadedFile("test_procurement_data.csv", file_content),
            original_filename="test_procurement_data.csv",
            file_format="csv",
            file_size=len(file_content),
            data_type='purchase_orders',
            status='pending',
            total_rows=len(df),
            processed_rows=0,
            failed_rows=0
        )
        print(f"[OK] DataUpload created: ID={upload.id}, Status={upload.status}")

        # Process and stage data
        print("\n[TEST] Staging procurement data...")
        staged_count = 0
        errors = []

        for index, row in df.iterrows():
            try:
                staging_record = ProcurementDataStaging.objects.create(
                    upload=upload,
                    row_number=index,
                    raw_data=row.to_dict(),
                    po_number=row.get('po_number'),
                    line_item_number=str(row.get('line_item_number', '')),
                    supplier_name=row.get('supplier_name'),
                    supplier_code=row.get('supplier_code'),
                    supplier_site=row.get('supplier_site'),
                    material_code=row.get('material_code'),
                    material_description=row.get('material_description'),
                    material_category=row.get('material_category'),
                    unit_price=float(row.get('unit_price', 0)),
                    quantity=float(row.get('quantity', 0)),
                    total_price=float(row.get('total_price', 0)),
                    currency=row.get('currency', 'USD'),
                    purchase_date=pd.to_datetime(row.get('purchase_date')).date() if pd.notna(row.get('purchase_date')) else None,
                    delivery_date=pd.to_datetime(row.get('delivery_date')).date() if pd.notna(row.get('delivery_date')) else None,
                    invoice_date=pd.to_datetime(row.get('invoice_date')).date() if pd.notna(row.get('invoice_date')) else None,
                    validation_status='pending'
                )
                staged_count += 1
            except Exception as e:
                errors.append(f"Row {index}: {str(e)[:50]}")

        print(f"[OK] Staged {staged_count}/{len(df)} records successfully")

        if errors:
            print(f"[WARNING] {len(errors)} errors occurred:")
            for error in errors[:5]:  # Show first 5 errors
                print(f"  - {error}")

        # Update upload status
        upload.status = 'ready_to_process'
        upload.processed_rows = staged_count
        upload.failed_rows = len(errors)
        upload.save()

        # Check staging table
        staged_records = ProcurementDataStaging.objects.filter(upload=upload)
        print(f"\n[VERIFICATION] Staging Table Status:")
        print(f"  - Total staged records: {staged_records.count()}")
        print(f"  - Unique materials: {staged_records.values('material_code').distinct().count()}")
        print(f"  - Unique suppliers: {staged_records.values('supplier_code').distinct().count()}")
        total_value = staged_records.aggregate(total=models.Sum('total_price'))['total']
        if total_value:
            print(f"  - Total value: ${total_value:,.2f}")
        else:
            print(f"  - Total value: $0.00")

    except Exception as e:
        print(f"[ERROR] Upload process failed: {e}")
        import traceback
        traceback.print_exc()
        return

    print("\n" + "="*60)
    print("DATA UPLOAD TEST COMPLETE")
    print("="*60)
    print(f"""
Next Steps:
1. Go to: http://localhost:8000/data-ingestion/upload/{upload.id}/
2. Review the uploaded data
3. Map columns if needed
4. Process to main tables

Upload Summary:
- Upload ID: {upload.id}
- File: {upload.original_filename}
- Records: {staged_count}
- Status: {upload.status}
    """)

    return upload

if __name__ == '__main__':
    from django.db import models
    upload = test_data_upload()