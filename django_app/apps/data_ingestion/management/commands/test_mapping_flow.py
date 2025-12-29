"""
Test command to verify the complete upload and mapping flow works
"""
import json
from django.core.management.base import BaseCommand
from django.test import Client
from django.contrib.auth import get_user_model
from apps.core.models import Organization
from apps.accounts.models import UserProfile
from apps.data_ingestion.models import DataUpload
import pandas as pd
import io

User = get_user_model()


class Command(BaseCommand):
    help = 'Test the upload and mapping flow'
    
    def handle(self, *args, **options):
        self.stdout.write('='*60)
        self.stdout.write('TESTING UPLOAD AND MAPPING FLOW')
        self.stdout.write('='*60)
        
        # Setup test user and organization
        org, _ = Organization.objects.get_or_create(
            name='Test Organization',
            defaults={'code': 'TEST'}
        )
        
        user = User.objects.filter(is_superuser=True).first()
        if not user:
            user = User.objects.create_superuser(
                username='admin',
                email='admin@example.com',
                password='admin123'
            )
        
        # Ensure user has profile with organization
        if not hasattr(user, 'profile'):
            UserProfile.objects.create(user=user, organization=org)
        
        # Create test CSV data
        test_data = {
            'PO_Number': ['PO-001', 'PO-002', 'PO-003'],
            'Vendor_Name': ['ABC Corp', 'XYZ Ltd', 'DEF Inc'],
            'Item_Description': ['Bolts', 'Nuts', 'Washers'],
            'Qty': [100, 200, 300],
            'Unit_Cost': [1.50, 2.00, 0.50],
            'Total_Amount': [150.00, 400.00, 150.00],
            'Order_Date': ['2024-01-01', '2024-01-02', '2024-01-03']
        }
        
        df = pd.DataFrame(test_data)
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_content = csv_buffer.getvalue()
        
        self.stdout.write('\n1. TEST DATA CREATED')
        self.stdout.write(f'   Rows: {len(df)}')
        self.stdout.write(f'   Columns: {list(df.columns)}')
        
        # Simulate upload
        self.stdout.write('\n2. CREATING UPLOAD RECORD...')
        
        upload = DataUpload.objects.create(
            organization=org,
            uploaded_by=user,
            original_filename='test_mapping.csv',
            file_format='csv',
            file_size=len(csv_content),
            data_type='purchase_orders',
            status='mapping',
            total_rows=len(df),
            detected_schema={
                'columns': {col: {'data_type': str(df[col].dtype)} for col in df.columns},
                'suggested_mappings': {
                    'PO_Number': 'po_number',
                    'Vendor_Name': 'supplier_name',
                    'Item_Description': 'material_description',
                    'Qty': 'quantity',
                    'Unit_Cost': 'unit_price',
                    'Total_Amount': 'total_price',
                    'Order_Date': 'purchase_date'
                }
            }
        )
        
        self.stdout.write(f'   Upload ID: {upload.id}')
        self.stdout.write(f'   Status: {upload.status}')
        
        # Test mapping save
        self.stdout.write('\n3. TESTING MAPPING SAVE...')
        
        test_mappings = {
            'po_number': 'PO_Number',
            'supplier_name': 'Vendor_Name',
            'material_description': 'Item_Description',
            'quantity': 'Qty',
            'unit_price': 'Unit_Cost',
            'total_price': 'Total_Amount',
            'purchase_date': 'Order_Date'
        }
        
        # Simulate POST request
        from django.test import RequestFactory
        from apps.data_ingestion.views import column_mapping
        
        factory = RequestFactory()
        request = factory.post(
            f'/data-ingestion/mapping/{upload.id}/',
            data=json.dumps(test_mappings),
            content_type='application/json'
        )
        request.user = user
        
        # Add session
        from django.contrib.sessions.middleware import SessionMiddleware
        from django.contrib.messages.middleware import MessageMiddleware
        
        # Add session support
        middleware = SessionMiddleware(lambda x: None)
        middleware.process_request(request)
        request.session.save()
        
        # Add messages support
        messages_middleware = MessageMiddleware(lambda x: None)
        messages_middleware.process_request(request)
        
        try:
            response = column_mapping(request, upload.id)
            
            if response.status_code == 200:
                result = json.loads(response.content)
                if result.get('success'):
                    self.stdout.write(self.style.SUCCESS('   [OK] Mapping saved successfully'))
                    self.stdout.write(f'   Message: {result.get("message", "No message")}')
                else:
                    self.stdout.write(self.style.ERROR(f'   [FAIL] {result.get("error", "Unknown error")}'))
            else:
                self.stdout.write(self.style.ERROR(f'   [FAIL] HTTP {response.status_code}'))
                self.stdout.write(f'   Response: {response.content.decode()[:200]}')
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   [ERROR] {str(e)}'))
            import traceback
            traceback.print_exc()
        
        # Check if mappings were saved
        upload.refresh_from_db()
        self.stdout.write(f'\n4. VERIFICATION:')
        self.stdout.write(f'   Upload status: {upload.status}')
        self.stdout.write(f'   Mappings saved: {bool(upload.column_mapping)}')
        if upload.column_mapping:
            self.stdout.write(f'   Mapping count: {len(upload.column_mapping)}')
        
        # Cleanup
        self.stdout.write('\n5. CLEANUP')
        upload.delete()
        self.stdout.write('   [OK] Test upload deleted')
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write('TEST COMPLETE')
        self.stdout.write('='*60)
        self.stdout.write('\nTo fix any issues:')
        self.stdout.write('1. Check that CSRF is properly configured')
        self.stdout.write('2. Ensure session middleware is enabled')
        self.stdout.write('3. Verify JSON parsing in the view')
        self.stdout.write('4. Check browser console for JavaScript errors')
        self.stdout.write('5. Use the simplified mapping template if needed')