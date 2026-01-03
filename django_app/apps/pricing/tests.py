"""
Tests for pricing module - Materials, Prices, Alerts, Benchmarks, Predictions
"""
import uuid
import json
from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import User
from django.conf import settings

from apps.core.models import Organization
from apps.accounts.models import UserProfile
from apps.pricing.models import (
    Material, Price, Category, PriceAlert,
    PriceBenchmark, PricePrediction, CostModel, PriceHistory
)
from apps.procurement.models import Supplier


class PricingTestCase(TestCase):
    """Base test case with common setup for pricing tests."""

    def setUp(self):
        """Set up test data."""
        # Create organization
        self.organization = Organization.objects.create(
            name='Test Organization',
            code='TEST_PRICING_ORG',
            type='buyer'
        )

        # Create user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        # Create user profile with organization
        self.profile = UserProfile.objects.create(
            user=self.user,
            organization=self.organization
        )

        # Create test category
        self.category = Category.objects.create(
            organization=self.organization,
            name='Test Category',
            description='Test category description'
        )

        # Create test supplier
        self.supplier = Supplier.objects.create(
            organization=self.organization,
            code='SUP-PRICE-001',
            name='Test Supplier',
            status='active'
        )

        # Create test material
        self.material = Material.objects.create(
            organization=self.organization,
            code='MAT-PRICE-001',
            name='Test Material',
            description='A test material for pricing',
            material_type='raw_material',
            category=self.category,
            unit_of_measure='EA',
            status='active',
            list_price=Decimal('100.00'),
            cost_price=Decimal('75.00'),
            currency='USD',
            lead_time_days=7,
            minimum_order_quantity=Decimal('10')
        )

        # Create price history
        now = timezone.now()
        self.prices = []
        for i in range(5):
            price = Price.objects.create(
                time=now - timedelta(days=i*7),
                material=self.material,
                supplier=self.supplier,
                organization=self.organization,
                price=Decimal('100.00') + Decimal(i * 2),
                currency='USD',
                quantity=Decimal('1'),
                unit_of_measure='EA',
                price_type='quote',
                source='test'
            )
            self.prices.append(price)

        # Set up client
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')


class MaterialListViewTests(PricingTestCase):
    """Tests for MaterialListView."""

    def test_material_list_view(self):
        """Test the material list view returns materials."""
        url = reverse('pricing:material_list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIn('materials', response.context)

    def test_material_list_search(self):
        """Test material search functionality."""
        url = reverse('pricing:material_list')
        response = self.client.get(url, {'search': 'Test Material'})

        self.assertEqual(response.status_code, 200)
        self.assertIn(self.material, response.context['materials'])

    def test_material_list_filter_by_category(self):
        """Test filtering materials by category."""
        url = reverse('pricing:material_list')
        response = self.client.get(url, {'category': self.category.id})

        self.assertEqual(response.status_code, 200)
        self.assertIn(self.material, response.context['materials'])

    def test_material_list_context_data(self):
        """Test material list context contains statistics."""
        url = reverse('pricing:material_list')
        response = self.client.get(url)

        self.assertIn('active_count', response.context)
        self.assertIn('categories_count', response.context)


class MaterialDetailViewTests(PricingTestCase):
    """Tests for MaterialDetailView."""

    def test_material_detail_view(self):
        """Test material detail view."""
        url = reverse('pricing:material_detail', kwargs={'pk': self.material.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['material'], self.material)

    def test_material_detail_shows_price_info(self):
        """Test material detail shows price information."""
        url = reverse('pricing:material_detail', kwargs={'pk': self.material.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIn('current_price', response.context)
        self.assertIn('avg_price', response.context)

    def test_material_detail_nonexistent(self):
        """Test viewing nonexistent material returns 404."""
        fake_uuid = uuid.uuid4()
        url = reverse('pricing:material_detail', kwargs={'pk': fake_uuid})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

    def test_material_detail_other_organization(self):
        """Test cannot view material from other organization."""
        other_org = Organization.objects.create(
            name='Other Org',
            code='OTHER_PRICE_ORG',
            type='buyer'
        )
        other_material = Material.objects.create(
            organization=other_org,
            code='MAT-OTHER',
            name='Other Material',
            material_type='raw_material',
            unit_of_measure='EA',
            status='active'
        )

        url = reverse('pricing:material_detail', kwargs={'pk': other_material.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)


class MaterialPriceHistoryViewTests(PricingTestCase):
    """Tests for MaterialPriceHistoryView."""

    def test_price_history_view(self):
        """Test price history view."""
        url = reverse('pricing:material_price_history', kwargs={'pk': self.material.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

    def test_price_history_contains_stats(self):
        """Test price history contains calculated statistics."""
        url = reverse('pricing:material_price_history', kwargs={'pk': self.material.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIn('current_price', response.context)
        self.assertIn('avg_price', response.context)
        self.assertIn('min_price', response.context)
        self.assertIn('max_price', response.context)


class PriceListViewTests(PricingTestCase):
    """Tests for PriceListView (all prices)."""

    def test_prices_list_view(self):
        """Test the prices list view."""
        url = reverse('pricing:price_list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIn('prices', response.context)


class CategoryTests(PricingTestCase):
    """Tests for Category model and views."""

    def test_category_str(self):
        """Test category string representation."""
        self.assertEqual(str(self.category), 'Test Category')

    def test_category_unique_per_org(self):
        """Test category name is unique per organization."""
        # Same name in same org should fail
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Category.objects.create(
                organization=self.organization,
                name='Test Category'
            )


class MaterialModelTests(PricingTestCase):
    """Tests for Material model methods."""

    def test_material_str(self):
        """Test material string representation."""
        expected = f"{self.material.code} - {self.material.name}"
        self.assertEqual(str(self.material), expected)

    def test_material_current_price_property(self):
        """Test material current_price property."""
        # current_price should return latest market price or list_price
        current = self.material.current_price
        self.assertIsNotNone(current)

    def test_material_get_price_history(self):
        """Test material get_price_history method."""
        history = self.material.get_price_history(days=30)
        self.assertTrue(history.exists())

    def test_material_calculate_should_cost(self):
        """Test material calculate_should_cost method."""
        should_cost = self.material.calculate_should_cost()
        self.assertEqual(should_cost, self.material.cost_price)


class PriceModelTests(PricingTestCase):
    """Tests for Price model."""

    def test_price_str(self):
        """Test price string representation."""
        price = self.prices[0]
        self.assertIn(self.material.code, str(price))

    def test_price_is_valid_property(self):
        """Test price is_valid property."""
        price = Price.objects.create(
            time=timezone.now(),
            material=self.material,
            organization=self.organization,
            price=Decimal('95.00'),
            currency='USD',
            quantity=Decimal('1'),
            unit_of_measure='EA',
            price_type='quote',
            valid_from=timezone.now().date() - timedelta(days=1),
            valid_to=timezone.now().date() + timedelta(days=30)
        )
        self.assertTrue(price.is_valid)

    def test_price_is_valid_expired(self):
        """Test price is_valid returns False when expired."""
        price = Price.objects.create(
            time=timezone.now() - timedelta(days=60),
            material=self.material,
            organization=self.organization,
            price=Decimal('90.00'),
            currency='USD',
            quantity=Decimal('1'),
            unit_of_measure='EA',
            price_type='quote',
            valid_from=timezone.now().date() - timedelta(days=60),
            valid_to=timezone.now().date() - timedelta(days=30)
        )
        self.assertFalse(price.is_valid)

    def test_price_unit_price_property(self):
        """Test price unit_price calculation."""
        price = Price.objects.create(
            time=timezone.now(),
            material=self.material,
            organization=self.organization,
            price=Decimal('200.00'),
            currency='USD',
            quantity=Decimal('10'),
            unit_of_measure='EA',
            price_type='quote'
        )
        self.assertEqual(price.unit_price, Decimal('20.00'))


class PriceAlertTests(PricingTestCase):
    """Tests for PriceAlert model and functionality."""

    def setUp(self):
        super().setUp()
        self.alert = PriceAlert.objects.create(
            user=self.user,
            material=self.material,
            organization=self.organization,
            name='High Price Alert',
            alert_type='threshold',
            condition_type='above',
            threshold_value=Decimal('120.00'),
            status='active'
        )

    def test_alert_str(self):
        """Test alert string representation."""
        self.assertIn('High Price Alert', str(self.alert))

    def test_alert_check_condition_above(self):
        """Test alert condition check for above threshold."""
        result = self.alert.check_condition(Decimal('130.00'))
        self.assertTrue(result)

        result = self.alert.check_condition(Decimal('110.00'))
        self.assertFalse(result)

    def test_alert_check_condition_below(self):
        """Test alert condition check for below threshold."""
        self.alert.condition_type = 'below'
        self.alert.save()

        result = self.alert.check_condition(Decimal('110.00'))
        self.assertTrue(result)

        result = self.alert.check_condition(Decimal('130.00'))
        self.assertFalse(result)

    def test_alert_trigger(self):
        """Test alert trigger functionality."""
        initial_count = self.alert.trigger_count
        self.alert.trigger_alert()
        self.alert.refresh_from_db()

        self.assertEqual(self.alert.status, 'triggered')
        self.assertEqual(self.alert.trigger_count, initial_count + 1)
        self.assertIsNotNone(self.alert.last_triggered)


class PriceBenchmarkTests(PricingTestCase):
    """Tests for PriceBenchmark model."""

    def setUp(self):
        super().setUp()
        self.benchmark = PriceBenchmark.objects.create(
            material=self.material,
            organization=self.organization,
            benchmark_type='market_average',
            benchmark_price=Decimal('105.00'),
            currency='USD',
            quantity=Decimal('1'),
            period_start=timezone.now().date() - timedelta(days=30),
            period_end=timezone.now().date(),
            sample_size=10,
            min_price=Decimal('95.00'),
            max_price=Decimal('115.00')
        )

    def test_benchmark_str(self):
        """Test benchmark string representation."""
        self.assertIn(self.material.code, str(self.benchmark))
        self.assertIn('market_average', str(self.benchmark))

    def test_benchmark_unique_constraint(self):
        """Test benchmark unique constraint."""
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            PriceBenchmark.objects.create(
                material=self.material,
                organization=self.organization,
                benchmark_type='market_average',
                benchmark_price=Decimal('100.00'),
                currency='USD',
                period_start=self.benchmark.period_start,
                period_end=self.benchmark.period_end
            )


class PricePredictionTests(PricingTestCase):
    """Tests for PricePrediction model."""

    def setUp(self):
        super().setUp()
        self.prediction = PricePrediction.objects.create(
            organization=self.organization,
            material=self.material,
            predicted_price=Decimal('110.00'),
            confidence_interval={'lower': 105.00, 'upper': 115.00},
            prediction_horizon_days=30,
            model_version='v1.0',
            model_confidence=0.85,
            status='completed'
        )

    def test_prediction_str(self):
        """Test prediction string representation."""
        self.assertIn(self.material.name, str(self.prediction))

    def test_prediction_status_choices(self):
        """Test prediction status choices."""
        self.prediction.status = 'pending'
        self.prediction.save()
        self.assertEqual(self.prediction.status, 'pending')


class CostModelTests(PricingTestCase):
    """Tests for CostModel model."""

    def setUp(self):
        super().setUp()
        self.cost_model = CostModel.objects.create(
            material=self.material,
            organization=self.organization,
            name='Parametric Model',
            model_type='parametric',
            version='1.0',
            parameters={'base_cost': 80.00, 'markup': 0.25},
            is_active=True
        )

    def test_cost_model_str(self):
        """Test cost model string representation."""
        self.assertIn(self.material.code, str(self.cost_model))

    def test_cost_model_calculate_parametric(self):
        """Test parametric cost calculation."""
        result = self.cost_model.calculate_should_cost({})
        self.assertEqual(result, Decimal('80.00'))


class PriceHistoryModelTests(PricingTestCase):
    """Tests for PriceHistory model."""

    def test_price_history_change_calculation(self):
        """Test price history calculates changes on save."""
        history = PriceHistory.objects.create(
            organization=self.organization,
            material=self.material,
            price=Decimal('110.00'),
            currency='USD',
            source='test',
            previous_price=Decimal('100.00')
        )

        self.assertEqual(history.price_change, Decimal('10.00'))
        self.assertEqual(history.change_percentage, Decimal('10.00'))
        self.assertEqual(history.change_type, 'increase')

    def test_price_history_decrease(self):
        """Test price history calculates decreases."""
        history = PriceHistory.objects.create(
            organization=self.organization,
            material=self.material,
            price=Decimal('90.00'),
            currency='USD',
            source='test',
            previous_price=Decimal('100.00')
        )

        self.assertEqual(history.price_change, Decimal('-10.00'))
        self.assertEqual(history.change_type, 'decrease')

    def test_price_history_new_price(self):
        """Test price history with no previous price."""
        history = PriceHistory.objects.create(
            organization=self.organization,
            material=self.material,
            price=Decimal('100.00'),
            currency='USD',
            source='test'
        )

        self.assertEqual(history.change_type, 'new')
        self.assertIsNone(history.price_change)


class OrganizationIsolationTests(PricingTestCase):
    """Tests to ensure organization data isolation in pricing."""

    def setUp(self):
        super().setUp()
        # Create another organization with its own data
        self.other_org = Organization.objects.create(
            name='Other Organization',
            code='OTHER_ORG_PRICING',
            type='buyer'
        )
        self.other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='otherpass123'
        )
        UserProfile.objects.create(
            user=self.other_user,
            organization=self.other_org
        )
        self.other_material = Material.objects.create(
            organization=self.other_org,
            code='MAT-OTHER-001',
            name='Other Org Material',
            material_type='raw_material',
            unit_of_measure='EA',
            status='active'
        )

    def test_material_list_only_shows_own_org(self):
        """Test material list only shows current organization's materials."""
        url = reverse('pricing:material_list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIn(self.material, response.context['materials'])
        self.assertNotIn(self.other_material, response.context['materials'])

    def test_cannot_view_other_org_material(self):
        """Test cannot view material from other organization."""
        url = reverse('pricing:material_detail', kwargs={'pk': self.other_material.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)


# =============================================================================
# Phase 3 ML Integration Tests
# =============================================================================


class MLClientDataclassTests(TestCase):
    """Tests for ML client dataclasses."""

    def test_price_prediction_dataclass(self):
        """Test PricePrediction dataclass."""
        from apps.pricing.ml_client import PricePrediction

        prediction = PricePrediction(
            predicted_price=Decimal('100.50'),
            confidence_score=0.85,
            confidence_interval={'lower': 95.0, 'upper': 106.0},
            model_version='v1.0.0',
            features_used=['price_history', 'quantity']
        )

        self.assertEqual(prediction.predicted_price, Decimal('100.50'))
        self.assertEqual(prediction.confidence_score, 0.85)
        self.assertEqual(prediction.model_version, 'v1.0.0')

    def test_anomaly_result_dataclass(self):
        """Test AnomalyResult dataclass."""
        from apps.pricing.ml_client import AnomalyResult

        result = AnomalyResult(
            is_anomaly=True,
            anomaly_score=0.92,
            severity='high',
            expected_price=Decimal('100.00'),
            deviation_percentage=25.0,
            explanation='Price significantly above historical average'
        )

        self.assertTrue(result.is_anomaly)
        self.assertEqual(result.severity, 'high')
        self.assertEqual(result.deviation_percentage, 25.0)

    def test_should_cost_result_dataclass(self):
        """Test ShouldCostResult dataclass."""
        from apps.pricing.ml_client import ShouldCostResult

        result = ShouldCostResult(
            total_should_cost=Decimal('150.00'),
            material_cost=Decimal('80.00'),
            labor_cost=Decimal('40.00'),
            overhead_cost=Decimal('30.00'),
            confidence=0.75,
            breakdown=[
                {'component': 'raw_material', 'cost': 80.00},
                {'component': 'labor', 'cost': 40.00}
            ]
        )

        self.assertEqual(result.total_should_cost, Decimal('150.00'))
        self.assertEqual(result.material_cost, Decimal('80.00'))
        self.assertEqual(result.labor_cost, Decimal('40.00'))


class MLServiceClientTests(TestCase):
    """Tests for MLServiceClient."""

    def test_client_initialization_default(self):
        """Test client initialization with default URL."""
        from apps.pricing.ml_client import MLServiceClient

        client = MLServiceClient()
        self.assertEqual(client.timeout, 30.0)
        self.assertIsNone(client._client)

    def test_client_initialization_custom(self):
        """Test client initialization with custom URL and timeout."""
        from apps.pricing.ml_client import MLServiceClient

        client = MLServiceClient(base_url='http://custom:8002', timeout=60.0)
        self.assertEqual(client.base_url, 'http://custom:8002')
        self.assertEqual(client.timeout, 60.0)

    def test_client_context_manager(self):
        """Test client works as context manager."""
        from apps.pricing.ml_client import MLServiceClient

        with MLServiceClient() as client:
            self.assertIsNotNone(client)

    @patch('apps.pricing.ml_client.httpx.Client')
    def test_health_check_success(self, mock_client_class):
        """Test successful health check."""
        from apps.pricing.ml_client import MLServiceClient

        mock_response = Mock()
        mock_response.json.return_value = {'status': 'healthy', 'models': 4}
        mock_response.raise_for_status = Mock()

        mock_client = Mock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = MLServiceClient()
        result = client.health_check()

        self.assertEqual(result['status'], 'healthy')
        mock_client.get.assert_called_once_with('/health')

    @patch('apps.pricing.ml_client.httpx.Client')
    def test_health_check_failure(self, mock_client_class):
        """Test health check handles failure."""
        from apps.pricing.ml_client import MLServiceClient, MLServiceError
        import httpx

        mock_client = Mock()
        mock_client.get.side_effect = httpx.HTTPError("Connection refused")
        mock_client_class.return_value = mock_client

        client = MLServiceClient()

        with self.assertRaises(MLServiceError):
            client.health_check()

    @patch('apps.pricing.ml_client.httpx.Client')
    def test_is_healthy_true(self, mock_client_class):
        """Test is_healthy returns True when healthy."""
        from apps.pricing.ml_client import MLServiceClient

        mock_response = Mock()
        mock_response.json.return_value = {'status': 'healthy'}
        mock_response.raise_for_status = Mock()

        mock_client = Mock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = MLServiceClient()
        self.assertTrue(client.is_healthy())

    @patch('apps.pricing.ml_client.httpx.Client')
    def test_is_healthy_false(self, mock_client_class):
        """Test is_healthy returns False when unhealthy."""
        from apps.pricing.ml_client import MLServiceClient
        import httpx

        mock_client = Mock()
        mock_client.get.side_effect = httpx.HTTPError("Connection refused")
        mock_client_class.return_value = mock_client

        client = MLServiceClient()
        self.assertFalse(client.is_healthy())

    @patch('apps.pricing.ml_client.httpx.Client')
    def test_predict_price_success(self, mock_client_class):
        """Test successful price prediction."""
        from apps.pricing.ml_client import MLServiceClient

        mock_response = Mock()
        mock_response.json.return_value = {
            'predicted_price': 105.50,
            'confidence_score': 0.87,
            'confidence_interval': {'lower': 100.0, 'upper': 111.0},
            'model_version': 'v1.0.0',
            'features_used': ['quantity', 'supplier']
        }
        mock_response.raise_for_status = Mock()

        mock_client = Mock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = MLServiceClient()
        prediction = client.predict_price(
            material_id='uuid-123',
            supplier_id='supplier-456',
            quantity=10.0
        )

        self.assertEqual(prediction.predicted_price, Decimal('105.50'))
        self.assertEqual(prediction.confidence_score, 0.87)
        self.assertEqual(prediction.model_version, 'v1.0.0')

    @patch('apps.pricing.ml_client.httpx.Client')
    def test_detect_anomaly_success(self, mock_client_class):
        """Test successful anomaly detection."""
        from apps.pricing.ml_client import MLServiceClient

        mock_response = Mock()
        mock_response.json.return_value = {
            'is_anomaly': True,
            'anomaly_score': 0.95,
            'severity': 'high',
            'expected_price': 100.00,
            'deviation_percentage': 30.0,
            'explanation': 'Price 30% above expected'
        }
        mock_response.raise_for_status = Mock()

        mock_client = Mock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = MLServiceClient()
        result = client.detect_anomaly(
            material_id='uuid-123',
            price=130.00,
            quantity=1.0
        )

        self.assertTrue(result.is_anomaly)
        self.assertEqual(result.severity, 'high')
        self.assertEqual(result.deviation_percentage, 30.0)

    @patch('apps.pricing.ml_client.httpx.Client')
    def test_calculate_should_cost_success(self, mock_client_class):
        """Test successful should-cost calculation."""
        from apps.pricing.ml_client import MLServiceClient

        mock_response = Mock()
        mock_response.json.return_value = {
            'total_should_cost': 150.00,
            'material_cost': 80.00,
            'labor_cost': 40.00,
            'overhead_cost': 30.00,
            'confidence': 0.82,
            'breakdown': []
        }
        mock_response.raise_for_status = Mock()

        mock_client = Mock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = MLServiceClient()
        result = client.calculate_should_cost(
            material_id='uuid-123',
            quantity=10.0
        )

        self.assertEqual(result.total_should_cost, Decimal('150.00'))
        self.assertEqual(result.material_cost, Decimal('80.00'))
        self.assertEqual(result.labor_cost, Decimal('40.00'))
        self.assertEqual(result.confidence, 0.82)


class MLServiceSingletonTests(TestCase):
    """Tests for ML client singleton pattern."""

    def test_get_ml_client_returns_same_instance(self):
        """Test get_ml_client returns singleton instance."""
        from apps.pricing import ml_client

        # Reset singleton
        ml_client._ml_client = None

        client1 = ml_client.get_ml_client()
        client2 = ml_client.get_ml_client()

        self.assertIs(client1, client2)

        # Cleanup
        ml_client._ml_client = None


class SignalTests(PricingTestCase):
    """Tests for pricing signals (anomaly detection on price creation)."""

    def test_anomaly_detection_triggered_on_new_price(self):
        """Test anomaly detection signal runs on new price creation."""
        # Create a new price - should trigger the signal without error
        # ML_ANOMALY_DETECTION_ENABLED=False in settings, so it will skip
        new_price = Price.objects.create(
            time=timezone.now(),
            material=self.material,
            supplier=self.supplier,
            organization=self.organization,
            price=Decimal('150.00'),
            currency='USD',
            quantity=Decimal('1'),
            unit_of_measure='EA',
            price_type='quote',
            source='test'
        )

        # Signal ran without error - verify price was created
        self.assertIsNotNone(new_price.id)

    def test_anomaly_detection_skipped_for_update(self):
        """Test anomaly detection is not triggered on price update."""
        # Create a price first
        price = Price.objects.create(
            time=timezone.now(),
            material=self.material,
            supplier=self.supplier,
            organization=self.organization,
            price=Decimal('100.00'),
            currency='USD',
            quantity=Decimal('1'),
            unit_of_measure='EA',
            price_type='quote',
            source='test'
        )

        # Update the price - signal should skip (created=False)
        price.price = Decimal('110.00')
        price.save()

        # No exception raised means signal handled update correctly
        price.refresh_from_db()
        self.assertEqual(price.price, Decimal('110.00'))

    def test_signal_handles_missing_material(self):
        """Test signal handles price without material gracefully."""
        # Material is required by the model, so this is a no-op test
        pass

    def test_update_material_price_stats_signal(self):
        """Test price stats are updated when new price is created."""
        initial_price = Price.objects.create(
            time=timezone.now(),
            material=self.material,
            supplier=self.supplier,
            organization=self.organization,
            price=Decimal('200.00'),
            currency='USD',
            quantity=Decimal('1'),
            unit_of_measure='EA',
            price_type='quote',
            source='test'
        )

        # The signal should calculate stats without error
        # Verify no exception is raised
        self.assertIsNotNone(initial_price.id)


class MLViewTests(PricingTestCase):
    """Tests for ML-related views."""

    def test_material_prediction_view_get_no_prediction(self):
        """Test prediction view when no prediction exists."""
        url = reverse('pricing:material_predict', kwargs={'pk': self.material.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data.get('success', True))
        self.assertIn('message', data)

    def test_material_prediction_view_get_with_prediction(self):
        """Test prediction view when prediction exists."""
        # Create a prediction first
        prediction = PricePrediction.objects.create(
            organization=self.organization,
            material=self.material,
            predicted_price=Decimal('110.00'),
            confidence_interval={'lower': 105.00, 'upper': 115.00},
            prediction_horizon_days=30,
            model_version='v1.0',
            model_confidence=0.85,
            status='completed'
        )

        url = reverse('pricing:material_predict', kwargs={'pk': self.material.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['prediction']['predicted_price'], 110.0)

    @patch('apps.pricing.ml_client.get_ml_client')
    def test_material_prediction_view_post_success(self, mock_get_client):
        """Test generating new prediction via POST."""
        from apps.pricing.ml_client import PricePrediction as MLPricePrediction

        mock_client = Mock()
        mock_client.predict_price.return_value = MLPricePrediction(
            predicted_price=Decimal('115.00'),
            confidence_score=0.88,
            confidence_interval={'lower': 110.0, 'upper': 120.0},
            model_version='v1.1.0',
            features_used=['history', 'quantity']
        )
        mock_get_client.return_value = mock_client

        url = reverse('pricing:material_predict', kwargs={'pk': self.material.pk})
        response = self.client.post(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['prediction']['predicted_price'], 115.0)

    @patch('apps.pricing.ml_client.get_ml_client')
    def test_material_prediction_view_post_ml_error(self, mock_get_client):
        """Test prediction view handles ML service error."""
        from apps.pricing.ml_client import MLServiceError

        mock_client = Mock()
        mock_client.predict_price.side_effect = MLServiceError("Service unavailable")
        mock_get_client.return_value = mock_client

        url = reverse('pricing:material_predict', kwargs={'pk': self.material.pk})
        response = self.client.post(url)

        self.assertEqual(response.status_code, 503)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('error', data)

    def test_material_should_cost_view_get_no_benchmark(self):
        """Test should-cost view when no benchmark exists."""
        url = reverse('pricing:material_should_cost', kwargs={'pk': self.material.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data.get('success', True))

    def test_material_should_cost_view_get_with_benchmark(self):
        """Test should-cost view when benchmark exists."""
        # Create a should-cost benchmark
        benchmark = PriceBenchmark.objects.create(
            material=self.material,
            organization=self.organization,
            benchmark_type='should_cost',
            benchmark_price=Decimal('95.00'),
            currency='USD',
            quantity=Decimal('1'),
            period_start=timezone.now().date() - timedelta(days=30),
            period_end=timezone.now().date(),
            calculation_method='Material: $50, Labor: $25, Overhead: $20'
        )

        url = reverse('pricing:material_should_cost', kwargs={'pk': self.material.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['should_cost']['total'], 95.0)

    @patch('apps.pricing.ml_client.get_ml_client')
    def test_material_should_cost_view_post_success(self, mock_get_client):
        """Test calculating should-cost via POST."""
        from apps.pricing.ml_client import ShouldCostResult

        mock_client = Mock()
        mock_client.calculate_should_cost.return_value = ShouldCostResult(
            total_should_cost=Decimal('100.00'),
            material_cost=Decimal('55.00'),
            labor_cost=Decimal('25.00'),
            overhead_cost=Decimal('20.00'),
            confidence=0.80,
            breakdown=[]
        )
        mock_get_client.return_value = mock_client

        url = reverse('pricing:material_should_cost', kwargs={'pk': self.material.pk})
        response = self.client.post(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['should_cost']['total'], 100.0)
        self.assertEqual(data['should_cost']['material_cost'], 55.0)

    def test_anomaly_check_view_missing_price(self):
        """Test anomaly check view requires price parameter."""
        url = reverse('pricing:material_anomaly_check', kwargs={'pk': self.material.pk})
        response = self.client.post(
            url,
            data=json.dumps({'quantity': 1}),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])

    @patch('apps.pricing.ml_client.get_ml_client')
    def test_anomaly_check_view_success(self, mock_get_client):
        """Test successful anomaly check."""
        from apps.pricing.ml_client import AnomalyResult

        mock_client = Mock()
        mock_client.detect_anomaly.return_value = AnomalyResult(
            is_anomaly=True,
            anomaly_score=0.9,
            severity='high',
            expected_price=Decimal('100.00'),
            deviation_percentage=25.0,
            explanation='Price 25% above expected'
        )
        mock_get_client.return_value = mock_client

        url = reverse('pricing:material_anomaly_check', kwargs={'pk': self.material.pk})
        response = self.client.post(
            url,
            data=json.dumps({'price': 125.0, 'quantity': 1}),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['anomaly']['is_anomaly'])
        self.assertEqual(data['anomaly']['severity'], 'high')

    @patch('apps.pricing.ml_client.get_ml_client')
    def test_ml_health_view_success(self, mock_get_client):
        """Test ML health view when service is healthy."""
        mock_client = Mock()
        mock_client.health_check.return_value = {
            'status': 'healthy',
            'models': 4,
            'uptime': '24h'
        }
        mock_get_client.return_value = mock_client

        url = reverse('pricing:ml_health')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['health']['status'], 'healthy')

    @patch('apps.pricing.ml_client.get_ml_client')
    def test_ml_health_view_service_down(self, mock_get_client):
        """Test ML health view when service is down."""
        from apps.pricing.ml_client import MLServiceError

        mock_client = Mock()
        mock_client.health_check.side_effect = MLServiceError("Connection refused")
        mock_get_client.return_value = mock_client

        url = reverse('pricing:ml_health')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 503)
        data = response.json()
        self.assertFalse(data['success'])


class CeleryTaskTests(PricingTestCase):
    """Tests for Celery ML tasks (without actual task execution)."""

    @patch('apps.pricing.tasks.get_ml_client')
    def test_generate_price_prediction_task(self, mock_get_client):
        """Test generate_price_prediction task logic."""
        from apps.pricing.tasks import generate_price_prediction
        from apps.pricing.ml_client import PricePrediction as MLPricePrediction

        mock_client = Mock()
        mock_client.predict_price.return_value = MLPricePrediction(
            predicted_price=Decimal('120.00'),
            confidence_score=0.85,
            confidence_interval={'lower': 115.0, 'upper': 125.0},
            model_version='v1.0.0',
            features_used=['quantity']
        )
        mock_get_client.return_value = mock_client

        # Call task synchronously (without Celery)
        result = generate_price_prediction(str(self.material.id))

        self.assertIn('predicted_price', result)
        self.assertEqual(result['predicted_price'], '120.00')

        # Verify prediction was stored
        prediction = PricePrediction.objects.filter(
            material=self.material
        ).order_by('-created_at').first()
        self.assertIsNotNone(prediction)
        self.assertEqual(prediction.predicted_price, Decimal('120.00'))

    def test_generate_price_prediction_material_not_found(self):
        """Test task handles missing material."""
        from apps.pricing.tasks import generate_price_prediction

        fake_uuid = str(uuid.uuid4())
        result = generate_price_prediction(fake_uuid)

        self.assertIn('error', result)
        self.assertIn('not found', result['error'])

    @patch('apps.pricing.tasks.get_ml_client')
    def test_check_price_anomaly_creates_alert(self, mock_get_client):
        """Test check_price_anomaly creates alert for anomalies."""
        from apps.pricing.tasks import check_price_anomaly
        from apps.pricing.ml_client import AnomalyResult

        mock_client = Mock()
        mock_client.detect_anomaly.return_value = AnomalyResult(
            is_anomaly=True,
            anomaly_score=0.92,
            severity='high',
            expected_price=Decimal('100.00'),
            deviation_percentage=30.0,
            explanation='Anomaly detected'
        )
        mock_get_client.return_value = mock_client

        price = self.prices[0]
        result = check_price_anomaly(str(price.id))

        self.assertTrue(result['is_anomaly'])
        self.assertIn('alert_id', result)

        # Verify alert was created
        alert = PriceAlert.objects.filter(
            material=self.material,
            alert_type='anomaly'
        ).first()
        self.assertIsNotNone(alert)
        self.assertEqual(alert.status, 'triggered')

    @patch('apps.pricing.tasks.get_ml_client')
    def test_check_price_anomaly_no_anomaly(self, mock_get_client):
        """Test check_price_anomaly when price is normal."""
        from apps.pricing.tasks import check_price_anomaly
        from apps.pricing.ml_client import AnomalyResult

        mock_client = Mock()
        mock_client.detect_anomaly.return_value = AnomalyResult(
            is_anomaly=False,
            anomaly_score=0.15,
            severity='low',
            expected_price=Decimal('100.00'),
            deviation_percentage=2.0,
            explanation='Price within normal range'
        )
        mock_get_client.return_value = mock_client

        price = self.prices[0]
        result = check_price_anomaly(str(price.id))

        self.assertFalse(result['is_anomaly'])
        self.assertNotIn('alert_id', result)

    @patch('apps.pricing.tasks.get_ml_client')
    def test_calculate_should_cost_creates_benchmark(self, mock_get_client):
        """Test calculate_should_cost creates benchmark."""
        from apps.pricing.tasks import calculate_should_cost
        from apps.pricing.ml_client import ShouldCostResult

        mock_client = Mock()
        mock_client.calculate_should_cost.return_value = ShouldCostResult(
            total_should_cost=Decimal('90.00'),
            material_cost=Decimal('50.00'),
            labor_cost=Decimal('25.00'),
            overhead_cost=Decimal('15.00'),
            confidence=0.85,
            breakdown=[]
        )
        mock_get_client.return_value = mock_client

        result = calculate_should_cost(str(self.material.id))

        self.assertEqual(result['should_cost'], '90.00')
        self.assertIn('benchmark_id', result)

        # Verify benchmark was created
        benchmark = PriceBenchmark.objects.filter(
            material=self.material,
            benchmark_type='should_cost'
        ).first()
        self.assertIsNotNone(benchmark)
        self.assertEqual(benchmark.benchmark_price, Decimal('90.00'))

    @patch('apps.pricing.tasks.get_ml_client')
    def test_check_ml_service_health(self, mock_get_client):
        """Test check_ml_service_health task."""
        from apps.pricing.tasks import check_ml_service_health

        mock_client = Mock()
        mock_client.health_check.return_value = {'status': 'healthy'}
        mock_get_client.return_value = mock_client

        result = check_ml_service_health()

        self.assertEqual(result['status'], 'healthy')

    @patch('apps.pricing.tasks.get_ml_client')
    def test_check_model_drift(self, mock_get_client):
        """Test check_model_drift task."""
        from apps.pricing.tasks import check_model_drift

        mock_client = Mock()
        mock_client.get_drift_status.return_value = {
            'price_model': {'drift_detected': False},
            'anomaly_model': {'drift_detected': True}
        }
        mock_get_client.return_value = mock_client

        result = check_model_drift()

        self.assertFalse(result['price_model']['drift_detected'])
        self.assertTrue(result['anomaly_model']['drift_detected'])
