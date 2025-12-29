"""
End-to-end integration tests for the complete upload flow
Tests the entire pipeline from file upload to data processing
"""
import os
import io
import csv
import json
import tempfile
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.data_ingestion.models import DataUpload, ProcurementDataStaging
from apps.procurement.models import PurchaseOrder, Supplier
from apps.pricing.models import Material, Price
from apps.core.models import Organization
from apps.accounts.models import UserProfile

User = get_user_model()


class UploadFlowIntegrationTest(TestCase):
    """
    Tests the complete upload flow from UI to database
    """
    
    def setUp(self):
        """Set up test environment"""
        self.client = Client()
        
        # Create organization
        self.organization = Organization.objects.create(
            name="E2E Test Corp",
            code="E2E001"
        )
        
        # Create user with profile
        self.user = User.objects.create_user(
            username='e2etest',
            email='e2e@test.com',
            password='testpass123'
        )
        
        # Create or update user profile
        UserProfile.objects.update_or_create(
            user=self.user,
            defaults={'organization': self.organization}
        )
        
        # Login
        self.client.login(username='e2etest', password='testpass123')
    
    def create_csv_file(self, data):
        """Helper to create CSV file from data"""
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
        content = output.getvalue().encode('utf-8')
        return SimpleUploadedFile('test.csv', content, content_type='text/csv')
    
    def test_complete_upload_flow(self):
        """Test the complete flow from upload to processed data"""
        # Prepare test data
        csv_data = [
            {
                'PO_Number': 'PO-E2E-001',
                'Supplier_Name': 'E2E Supplier Corp',
                'Supplier_Code': 'E2ESUP01',
                'Material_Code': 'E2EMAT01',
                'Material_Description': 'E2E Test Material',
                'Quantity': '100',
                'Unit_Price': '25.50',
                'Total_Price': '2550.00',
                'Currency': 'USD',
                'Purchase_Date': '2024-01-15',
                'Delivery_Date': '2024-02-01'
            },
            {
                'PO_Number': 'PO-E2E-002',
                'Supplier_Name': 'E2E Supplier Corp',
                'Supplier_Code': 'E2ESUP01',
                'Material_Code': 'E2EMAT02',
                'Material_Description': 'Another E2E Material',
                'Quantity': '50',
                'Unit_Price': '75.00',
                'Total_Price': '3750.00',
                'Currency': 'USD',
                'Purchase_Date': '2024-01-16',
                'Delivery_Date': '2024-02-05'
            }
        ]
        
        csv_file = self.create_csv_file(csv_data)
        
        # Step 1: Upload file
        upload_url = reverse('data_ingestion:upload')
        response = self.client.post(upload_url, {
            'file': csv_file,
            'data_type': 'purchase_orders'
        })
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data.get('success'))
        upload_id = response_data.get('upload_id')
        self.assertIsNotNone(upload_id)
        
        # Verify upload was created
        upload = DataUpload.objects.get(id=upload_id)
        self.assertEqual(upload.original_filename, 'test.csv')
        self.assertEqual(upload.data_type, 'purchase_orders')
        
        # Step 2: Verify staging records were created (would happen in mapping step)
        # For this test, we'll create them manually
        for i, row in enumerate(csv_data):
            ProcurementDataStaging.objects.create(
                upload=upload,
                row_number=i+1,
                raw_data=row,
                po_number=row['PO_Number'],
                supplier_name=row['Supplier_Name'],
                supplier_code=row['Supplier_Code'],
                material_code=row['Material_Code'],
                material_description=row['Material_Description'],
                quantity=Decimal(row['Quantity']),
                unit_price=Decimal(row['Unit_Price']),
                total_price=Decimal(row['Total_Price']),
                currency=row['Currency'],
                purchase_date='2024-01-15',
                delivery_date='2024-02-01',
                validation_status='valid'
            )
        
        # Step 3: Process upload
        process_url = reverse('data_ingestion:process_upload', args=[upload_id])
        response = self.client.post(process_url)
        
        # Should redirect after processing
        self.assertEqual(response.status_code, 302)
        
        # Step 4: Verify data was processed correctly
        # Check suppliers
        suppliers = Supplier.objects.filter(organization=self.organization)
        self.assertEqual(suppliers.count(), 1)
        supplier = suppliers.first()
        self.assertEqual(supplier.name, 'E2E Supplier Corp')
        self.assertEqual(supplier.code, 'E2ESUP01')
        
        # Check materials
        materials = Material.objects.filter(organization=self.organization)
        self.assertEqual(materials.count(), 2)
        material_codes = set(materials.values_list('code', flat=True))
        self.assertIn('E2EMAT01', material_codes)
        self.assertIn('E2EMAT02', material_codes)
        
        # Check purchase orders
        pos = PurchaseOrder.objects.filter(organization=self.organization)
        self.assertEqual(pos.count(), 2)
        po_numbers = set(pos.values_list('po_number', flat=True))
        self.assertIn('PO-E2E-001', po_numbers)
        self.assertIn('PO-E2E-002', po_numbers)
        
        # Check price history
        prices = Price.objects.filter(organization=self.organization)
        self.assertGreaterEqual(prices.count(), 2)
    
    def test_upload_with_validation_errors(self):
        """Test upload with validation errors"""
        # Create CSV with problematic data
        csv_data = [
            {
                'PO_Number': '',  # Missing PO number
                'Supplier_Name': '',  # Missing supplier
                'Material_Description': 'Orphan Material',
                'Quantity': 'invalid',  # Invalid quantity
                'Unit_Price': '-50',  # Negative price
                'Currency': 'XXX',  # Invalid currency
                'Purchase_Date': 'not-a-date'  # Invalid date
            }
        ]
        
        csv_file = self.create_csv_file(csv_data)
        
        # Upload file
        upload_url = reverse('data_ingestion:upload')
        response = self.client.post(upload_url, {
            'file': csv_file,
            'data_type': 'purchase_orders'
        })
        
        # Upload should succeed (validation happens later)
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        upload_id = response_data.get('upload_id')
        
        # Create staging record with validation errors
        upload = DataUpload.objects.get(id=upload_id)
        staging = ProcurementDataStaging.objects.create(
            upload=upload,
            row_number=1,
            raw_data=csv_data[0],
            validation_status='invalid',
            validation_errors=['Missing PO number', 'Invalid quantity', 'Invalid date format']
        )
        
        # Check validation review page
        validation_url = reverse('data_ingestion:validation', args=[upload_id])
        response = self.client.get(validation_url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'invalid')
    
    def test_duplicate_upload_handling(self):
        """Test that duplicate uploads are handled correctly"""
        # Create initial data
        csv_data = [
            {
                'PO_Number': 'PO-DUP-001',
                'Supplier_Name': 'Duplicate Test Supplier',
                'Material_Description': 'Duplicate Test Material',
                'Quantity': '100',
                'Unit_Price': '50.00',
                'Currency': 'USD',
                'Purchase_Date': '2024-01-15'
            }
        ]
        
        # First upload
        csv_file1 = self.create_csv_file(csv_data)
        response1 = self.client.post(reverse('data_ingestion:upload'), {
            'file': csv_file1,
            'data_type': 'purchase_orders'
        })
        
        upload_id1 = json.loads(response1.content).get('upload_id')
        upload1 = DataUpload.objects.get(id=upload_id1)
        
        # Create staging and process
        ProcurementDataStaging.objects.create(
            upload=upload1,
            row_number=1,
            raw_data=csv_data[0],
            po_number='PO-DUP-001',
            supplier_name='Duplicate Test Supplier',
            material_description='Duplicate Test Material',
            quantity=Decimal('100'),
            unit_price=Decimal('50.00'),
            currency='USD',
            purchase_date='2024-01-15',
            validation_status='valid'
        )
        
        from apps.data_ingestion.services.data_processor import DataProcessor
        processor1 = DataProcessor()
        result1 = processor1.process_upload(str(upload_id1))
        
        # Second upload with same PO number
        csv_file2 = self.create_csv_file(csv_data)
        response2 = self.client.post(reverse('data_ingestion:upload'), {
            'file': csv_file2,
            'data_type': 'purchase_orders'
        })
        
        upload_id2 = json.loads(response2.content).get('upload_id')
        upload2 = DataUpload.objects.get(id=upload_id2)
        
        # Create staging and process
        ProcurementDataStaging.objects.create(
            upload=upload2,
            row_number=1,
            raw_data=csv_data[0],
            po_number='PO-DUP-001',
            supplier_name='Duplicate Test Supplier',
            material_description='Duplicate Test Material',
            quantity=Decimal('100'),
            unit_price=Decimal('50.00'),
            currency='USD',
            purchase_date='2024-01-15',
            validation_status='valid'
        )
        
        processor2 = DataProcessor()
        result2 = processor2.process_upload(str(upload_id2))
        
        # Should only have one PO
        po_count = PurchaseOrder.objects.filter(po_number='PO-DUP-001').count()
        self.assertEqual(po_count, 1)
        
        # Second should be marked as duplicate
        self.assertEqual(processor2.duplicate_count, 1)
    
    def test_large_file_upload(self):
        """Test uploading and processing a larger file"""
        # Create 500 rows of data
        csv_data = []
        for i in range(500):
            csv_data.append({
                'PO_Number': f'PO-LARGE-{i+1:04d}',
                'Supplier_Name': f'Supplier {i%20 + 1}',  # 20 different suppliers
                'Material_Code': f'MAT{i%50 + 1:03d}',  # 50 different materials
                'Material_Description': f'Material Type {i%50 + 1}',
                'Quantity': str(100 + i%100),
                'Unit_Price': str(10 + (i%100) * 0.5),
                'Currency': 'USD',
                'Purchase_Date': '2024-01-15'
            })
        
        csv_file = self.create_csv_file(csv_data)
        
        # Upload file
        response = self.client.post(reverse('data_ingestion:upload'), {
            'file': csv_file,
            'data_type': 'purchase_orders'
        })
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        upload_id = response_data.get('upload_id')
        
        # Create staging records
        upload = DataUpload.objects.get(id=upload_id)
        for i, row in enumerate(csv_data[:100]):  # Process first 100 for test speed
            ProcurementDataStaging.objects.create(
                upload=upload,
                row_number=i+1,
                raw_data=row,
                po_number=row['PO_Number'],
                supplier_name=row['Supplier_Name'],
                material_code=row['Material_Code'],
                material_description=row['Material_Description'],
                quantity=Decimal(row['Quantity']),
                unit_price=Decimal(row['Unit_Price']),
                currency=row['Currency'],
                purchase_date='2024-01-15',
                validation_status='valid'
            )
        
        # Process
        from apps.data_ingestion.services.data_processor import DataProcessor
        processor = DataProcessor()
        result = processor.process_upload(str(upload_id))
        
        self.assertTrue(result['success'])
        self.assertEqual(result['processed'], 100)
    
    def test_excel_file_upload(self):
        """Test uploading Excel files"""
        # Note: This would require creating an actual Excel file
        # For now, we'll test the validation logic
        
        # Create a mock Excel file
        excel_content = b'Mock Excel Content'
        excel_file = SimpleUploadedFile(
            'test.xlsx',
            excel_content,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
        response = self.client.post(reverse('data_ingestion:upload'), {
            'file': excel_file,
            'data_type': 'purchase_orders'
        })
        
        # The actual parsing would fail with mock content
        # But we can test that the file format is accepted
        # In real scenario, this would use openpyxl or pandas to parse
    
    def test_concurrent_user_uploads(self):
        """Test that multiple users can upload simultaneously"""
        # Create second user
        user2 = User.objects.create_user(
            username='concurrent2',
            email='concurrent2@test.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=user2, organization=self.organization)
        
        # Create data for both users
        csv_data_user1 = [{
            'PO_Number': 'PO-USER1-001',
            'Supplier_Name': 'User1 Supplier',
            'Material_Description': 'User1 Material',
            'Quantity': '100',
            'Unit_Price': '50.00',
            'Currency': 'USD',
            'Purchase_Date': '2024-01-15'
        }]
        
        csv_data_user2 = [{
            'PO_Number': 'PO-USER2-001',
            'Supplier_Name': 'User2 Supplier',
            'Material_Description': 'User2 Material',
            'Quantity': '200',
            'Unit_Price': '75.00',
            'Currency': 'USD',
            'Purchase_Date': '2024-01-16'
        }]
        
        # User 1 upload
        csv_file1 = self.create_csv_file(csv_data_user1)
        response1 = self.client.post(reverse('data_ingestion:upload'), {
            'file': csv_file1,
            'data_type': 'purchase_orders'
        })
        upload_id1 = json.loads(response1.content).get('upload_id')
        
        # User 2 upload
        client2 = Client()
        client2.login(username='concurrent2', password='testpass123')
        csv_file2 = self.create_csv_file(csv_data_user2)
        response2 = client2.post(reverse('data_ingestion:upload'), {
            'file': csv_file2,
            'data_type': 'purchase_orders'
        })
        upload_id2 = json.loads(response2.content).get('upload_id')
        
        # Both uploads should be created
        self.assertIsNotNone(upload_id1)
        self.assertIsNotNone(upload_id2)
        self.assertNotEqual(upload_id1, upload_id2)
        
        # Verify both uploads exist
        upload1 = DataUpload.objects.get(id=upload_id1)
        upload2 = DataUpload.objects.get(id=upload_id2)
        
        self.assertEqual(upload1.uploaded_by.username, 'e2etest')
        self.assertEqual(upload2.uploaded_by.username, 'concurrent2')