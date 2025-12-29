import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pricing_agent.settings')
django.setup()

from apps.data_ingestion.models import DataUpload, ProcurementDataStaging
from apps.core.models import Organization
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
import pandas as pd
import io

# Clean up old test uploads
DataUpload.objects.all().delete()
ProcurementDataStaging.objects.all().delete()
print('Cleared old uploads')

# Create a test upload ready for mapping
User = get_user_model()
user = User.objects.filter(is_superuser=True).first()
if user:
    org, _ = Organization.objects.get_or_create(name='Test Org', defaults={'code': 'TEST'})
    
    # Create sample CSV data
    sample_data = {
        'PO_Number': ['PO-2024-001', 'PO-2024-002', 'PO-2024-003', 'PO-2024-004', 'PO-2024-005'],
        'Vendor': ['ABC Corp', 'XYZ Ltd', 'DEF Inc', 'GHI Co', 'JKL LLC'],
        'Item': ['Steel Bolts', 'Copper Wire', 'Aluminum Sheets', 'Plastic Pipes', 'Rubber Gaskets'],
        'Qty': [100, 50, 25, 200, 500],
        'Price': [1.50, 5.25, 45.00, 3.75, 0.25],
        'Total': [150.00, 262.50, 1125.00, 750.00, 125.00],
        'Date': ['2024-01-15', '2024-01-16', '2024-01-17', '2024-01-18', '2024-01-19']
    }
    
    # Create CSV file content
    df = pd.DataFrame(sample_data)
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    csv_content = csv_buffer.getvalue()
    
    # Create file object
    file_content = ContentFile(csv_content.encode('utf-8'))
    
    upload = DataUpload.objects.create(
        organization=org,
        uploaded_by=user,
        original_filename='sample_data.csv',
        file_format='csv',
        file_size=len(csv_content),
        data_type='purchase_orders',
        status='mapping',
        total_rows=len(df),
        detected_schema={
            'columns': {
                'PO_Number': {'data_type': 'string'},
                'Vendor': {'data_type': 'string'},
                'Item': {'data_type': 'string'},
                'Qty': {'data_type': 'float'},
                'Price': {'data_type': 'float'},
                'Total': {'data_type': 'float'},
                'Date': {'data_type': 'string'}
            },
            'suggested_mappings': {}
        }
    )
    
    # Save the file
    upload.file.save(f'sample_data_{upload.id}.csv', file_content, save=True)
    
    # Create staging records
    for i, row in df.iterrows():
        ProcurementDataStaging.objects.create(
            upload=upload,
            row_number=i + 1,
            raw_data=row.to_dict(),
            
            # Map to standard fields
            po_number=row['PO_Number'],
            supplier_name=row['Vendor'],
            material_description=row['Item'],
            quantity=row['Qty'],
            unit_price=row['Price'],
            total_price=row['Total'],
            purchase_date=row['Date'],
            
            validation_status='valid',
            is_processed=False
        )
    print(f'Created test upload: {upload.id}')
    print(f'\nYou can now test the mapping interface at:')
    print(f'http://localhost:8000/data-ingestion/mapping/{upload.id}/')
    print('\nThe interface should:')
    print('1. Auto-detect and map columns')
    print('2. Allow you to adjust mappings')
    print('3. Save successfully when you click "Save & Process"')
else:
    print('No superuser found. Please create one first.')
    print('Run: python manage.py createsuperuser')