"""
Integration tests for Django API endpoints.
"""
import pytest
import json
from django.test import TransactionTestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient
from unittest.mock import patch, Mock
import responses

from apps.core.models import Organization, Tenant
from apps.pricing.models import Material, Price
from apps.procurement.models import Supplier, RFQ
from ..base import BaseAPITestCase

User = get_user_model()


class APIEndpointIntegrationTest(BaseAPITestCase):
    """Integration tests for API endpoints across different apps."""
    
    def setUp(self):
        super().setUp()
        self.supplier = Supplier.objects.create(
            organization=self.organization,
            name="Test Supplier Ltd",
            email="supplier@test.com",
            phone="+1234567890",
            status="active"
        )
        
        self.material = Material.objects.create(
            organization=self.organization,
            code="MAT001",
            name="Steel Plate",
            material_type="raw_material",
            unit_of_measure="kg",
            list_price=100.00
        )
    
    @responses.activate
    def test_rfq_creation_with_ml_prediction(self):
        """Test RFQ creation that triggers ML prediction."""
        # Mock ML service response
        responses.add(
            responses.POST,
            'http://testserver:8001/api/v1/predictions/',
            json={
                'prediction': 1250.50,
                'confidence': 0.85,
                'model_version': '1.0.0'
            },
            status=200
        )
        
        rfq_data = {
            'title': 'Steel Plates RFQ',
            'description': 'Need 1000 kg of steel plates',
            'materials': [
                {
                    'material_id': self.material.id,
                    'quantity': 1000,
                    'specifications': {
                        'grade': 'A36',
                        'thickness': '10mm'
                    }
                }
            ],
            'delivery_date': '2024-12-31',
            'delivery_location': 'New York, NY'
        }
        
        response = self.client.post(
            reverse('rfq-list'),
            data=json.dumps(rfq_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('predicted_price', response.data)
        self.assertEqual(response.data['predicted_price'], 1250.50)
    
    def test_material_price_history_api(self):
        """Test material price history API endpoint."""
        # Create price history
        from django.utils import timezone
        from datetime import timedelta
        
        prices = []
        for i in range(5):
            price = Price.objects.create(
                time=timezone.now() - timedelta(days=i),
                material=self.material,
                supplier=self.supplier,
                organization=self.organization,
                price=100.00 + i * 10,
                currency="USD",
                unit_of_measure="kg",
                price_type="quote"
            )
            prices.append(price)
        
        response = self.client.get(
            reverse('material-price-history', kwargs={'pk': self.material.id}),
            {'days': 30}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 5)
        self.assertTrue(all('price' in item for item in response.data['results']))
    
    def test_price_alert_trigger_workflow(self):
        """Test price alert trigger workflow."""
        from apps.pricing.models import PriceAlert
        
        # Create price alert
        alert = PriceAlert.objects.create(
            user=self.user,
            material=self.material,
            organization=self.organization,
            name="High Price Alert",
            alert_type="threshold",
            condition_type="above",
            threshold_value=120.00,
            status="active"
        )
        
        # Create price that should trigger alert
        Price.objects.create(
            time=timezone.now(),
            material=self.material,
            supplier=self.supplier,
            organization=self.organization,
            price=130.00,
            currency="USD",
            unit_of_measure="kg",
            price_type="market"
        )
        
        # Check alert status via API
        response = self.client.get(
            reverse('price-alert-detail', kwargs={'pk': alert.id})
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Alert should be triggered (this depends on implementation)
    
    def test_supplier_performance_analytics(self):
        """Test supplier performance analytics endpoint."""
        # Create multiple quotes from supplier
        quotes = []
        for i in range(3):
            quote = Price.objects.create(
                time=timezone.now() - timedelta(days=i),
                material=self.material,
                supplier=self.supplier,
                organization=self.organization,
                price=100.00 + i * 5,
                currency="USD",
                unit_of_measure="kg",
                price_type="quote"
            )
            quotes.append(quote)
        
        response = self.client.get(
            reverse('supplier-performance', kwargs={'pk': self.supplier.id})
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('quote_count', response.data)
        self.assertIn('average_price', response.data)
        self.assertIn('price_trend', response.data)
    
    def test_cross_app_data_consistency(self):
        """Test data consistency across different apps."""
        # Create RFQ
        rfq_data = {
            'title': 'Test RFQ',
            'description': 'Test description',
            'materials': [
                {
                    'material_id': self.material.id,
                    'quantity': 100
                }
            ]
        }
        
        rfq_response = self.client.post(
            reverse('rfq-list'),
            data=json.dumps(rfq_data),
            content_type='application/json'
        )
        
        rfq_id = rfq_response.data['id']
        
        # Create quote for the RFQ
        quote_data = {
            'rfq': rfq_id,
            'supplier': self.supplier.id,
            'total_price': 1000.00,
            'line_items': [
                {
                    'material': self.material.id,
                    'quantity': 100,
                    'unit_price': 10.00
                }
            ]
        }
        
        quote_response = self.client.post(
            reverse('quote-list'),
            data=json.dumps(quote_data),
            content_type='application/json'
        )
        
        self.assertEqual(quote_response.status_code, status.HTTP_201_CREATED)
        
        # Verify data consistency
        rfq_detail = self.client.get(
            reverse('rfq-detail', kwargs={'pk': rfq_id})
        )
        
        self.assertIn('quotes', rfq_detail.data)
        self.assertEqual(len(rfq_detail.data['quotes']), 1)
    
    @patch('apps.core.tasks.send_notification.delay')
    def test_notification_workflow(self, mock_send_notification):
        """Test notification workflow integration."""
        from apps.pricing.models import PriceAlert
        
        # Create alert with notifications enabled
        alert = PriceAlert.objects.create(
            user=self.user,
            material=self.material,
            organization=self.organization,
            name="Price Alert",
            alert_type="threshold",
            condition_type="above",
            threshold_value=120.00,
            email_notification=True
        )
        
        # Trigger alert condition
        Price.objects.create(
            time=timezone.now(),
            material=self.material,
            organization=self.organization,
            price=130.00,
            currency="USD",
            unit_of_measure="kg",
            price_type="market"
        )
        
        # Verify notification was queued
        mock_send_notification.assert_called()
    
    def test_multi_tenant_data_isolation(self):
        """Test data isolation between tenants."""
        # Create another organization and user
        other_org = Organization.objects.create(
            name="Other Org",
            slug="other-org",
            is_active=True
        )
        
        other_user = User.objects.create_user(
            username="otheruser",
            email="other@test.com",
            password="testpass123",
            organization=other_org
        )
        
        # Create material in other organization
        other_material = Material.objects.create(
            organization=other_org,
            code="MAT001",  # Same code as original
            name="Other Steel Plate",
            material_type="raw_material",
            unit_of_measure="kg"
        )
        
        # Authenticate as other user
        self.client.force_authenticate(user=other_user)
        
        # Try to access original material (should fail)
        response = self.client.get(
            reverse('material-detail', kwargs={'pk': self.material.id})
        )
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
        # Should only see materials from their organization
        response = self.client.get(reverse('material-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], other_material.id)
    
    def test_api_pagination_and_filtering(self):
        """Test API pagination and filtering across endpoints."""
        # Create multiple materials
        materials = []
        for i in range(25):  # More than default page size
            material = Material.objects.create(
                organization=self.organization,
                code=f"MAT{i:03d}",
                name=f"Material {i}",
                material_type="raw_material" if i % 2 == 0 else "component",
                unit_of_measure="kg",
                list_price=100.00 + i
            )
            materials.append(material)
        
        # Test pagination
        response = self.client.get(reverse('material-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('count', response.data)
        self.assertIn('next', response.data)
        self.assertIn('results', response.data)
        
        # Test filtering
        response = self.client.get(
            reverse('material-list'),
            {'material_type': 'raw_material'}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should only return raw materials
        for item in response.data['results']:
            self.assertEqual(item['material_type'], 'raw_material')
    
    def test_api_error_handling(self):
        """Test API error handling and response formats."""
        # Test 404 error
        response = self.client.get(
            reverse('material-detail', kwargs={'pk': 99999})
        )
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('detail', response.data)
        
        # Test 400 error (bad request)
        response = self.client.post(
            reverse('material-list'),
            data=json.dumps({'invalid': 'data'}),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Test permission error
        self.client.force_authenticate(user=None)  # Logout
        
        response = self.client.get(reverse('material-list'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class DatabaseIntegrationTest(TransactionTestCase):
    """Integration tests requiring database transactions."""
    
    def setUp(self):
        self.organization = Organization.objects.create(
            name="Test Organization",
            slug="test-org",
            is_active=True
        )
        
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            organization=self.organization
        )
        
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_concurrent_price_updates(self):
        """Test concurrent price updates don't cause race conditions."""
        import threading
        from django.utils import timezone
        
        material = Material.objects.create(
            organization=self.organization,
            code="CONCURRENT_TEST",
            name="Concurrent Test Material",
            material_type="raw_material",
            unit_of_measure="kg"
        )
        
        def create_price(price_value):
            Price.objects.create(
                time=timezone.now(),
                material=material,
                organization=self.organization,
                price=price_value,
                currency="USD",
                unit_of_measure="kg",
                price_type="quote"
            )
        
        # Create prices concurrently
        threads = []
        for i in range(5):
            thread = threading.Thread(target=create_price, args=(100.00 + i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Verify all prices were created
        price_count = Price.objects.filter(material=material).count()
        self.assertEqual(price_count, 5)
    
    def test_large_data_operations(self):
        """Test operations with large datasets."""
        # Create many materials for testing
        materials = []
        for i in range(1000):
            material = Material.objects.create(
                organization=self.organization,
                code=f"BULK{i:04d}",
                name=f"Bulk Material {i}",
                material_type="raw_material",
                unit_of_measure="kg"
            )
            materials.append(material)
        
        # Test bulk API operations
        response = self.client.get(reverse('material-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1000)
        
        # Test filtering performance
        response = self.client.get(
            reverse('material-list'),
            {'search': 'Bulk Material 1'}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should be responsive even with large dataset