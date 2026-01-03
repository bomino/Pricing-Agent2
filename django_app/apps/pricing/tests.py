"""
Tests for pricing module - Materials, Prices, Alerts, Benchmarks, Predictions
"""
import uuid
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import User

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
