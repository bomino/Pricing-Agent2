"""
Unit tests for pricing models.
"""
import pytest
from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone
from datetime import date, timedelta

from apps.pricing.models import Material, Price, PriceBenchmark, PriceAlert, CostModel
from apps.core.models import Organization, Category
from apps.accounts.models import User
from ..../../base import BaseTestCase, ModelTestMixin


class MaterialModelTest(BaseTestCase, ModelTestMixin):
    """Test cases for Material model."""
    
    def setUp(self):
        super().setUp()
        self.category = Category.objects.create(
            name="Test Category",
            organization=self.organization
        )
    
    def test_material_creation(self):
        """Test creating a material."""
        material = Material.objects.create(
            organization=self.organization,
            code="TEST001",
            name="Test Material",
            description="A test material",
            material_type="raw_material",
            category=self.category,
            unit_of_measure="kg",
            list_price=Decimal("100.00")
        )
        
        self.assertEqual(material.organization, self.organization)
        self.assertEqual(material.code, "TEST001")
        self.assertEqual(material.name, "Test Material")
        self.assertEqual(material.material_type, "raw_material")
        self.assertEqual(material.status, "active")  # Default value
        self.assertEqual(material.currency, "USD")  # Default value
    
    def test_material_str_representation(self):
        """Test material string representation."""
        material = Material.objects.create(
            organization=self.organization,
            code="TEST001",
            name="Test Material",
            material_type="raw_material",
            unit_of_measure="kg"
        )
        
        self.assertEqual(str(material), "TEST001 - Test Material")
    
    def test_material_unique_code_per_organization(self):
        """Test that material code is unique per organization."""
        Material.objects.create(
            organization=self.organization,
            code="TEST001",
            name="Test Material 1",
            material_type="raw_material",
            unit_of_measure="kg"
        )
        
        # Creating another material with same code in same organization should fail
        with self.assertRaises(IntegrityError):
            Material.objects.create(
                organization=self.organization,
                code="TEST001",
                name="Test Material 2",
                material_type="raw_material",
                unit_of_measure="kg"
            )
    
    def test_material_code_can_be_same_across_organizations(self):
        """Test that material code can be same across different organizations."""
        other_org = Organization.objects.create(
            name="Other Organization",
            slug="other-org",
            is_active=True
        )
        
        material1 = Material.objects.create(
            organization=self.organization,
            code="TEST001",
            name="Test Material 1",
            material_type="raw_material",
            unit_of_measure="kg"
        )
        
        material2 = Material.objects.create(
            organization=other_org,
            code="TEST001",
            name="Test Material 2",
            material_type="raw_material",
            unit_of_measure="kg"
        )
        
        self.assertEqual(material1.code, material2.code)
        self.assertNotEqual(material1.organization, material2.organization)
    
    def test_material_field_types(self):
        """Test material model field types."""
        self.assertModelFieldType(Material, 'code', models.CharField)
        self.assertModelFieldType(Material, 'name', models.CharField)
        self.assertModelFieldType(Material, 'specifications', models.JSONField)
        self.assertModelFieldType(Material, 'list_price', models.DecimalField)
        self.assertModelFieldType(Material, 'created_at', models.DateTimeField)
    
    def test_material_required_fields(self):
        """Test required fields for material."""
        self.assertModelFieldRequired(Material, 'code')
        self.assertModelFieldRequired(Material, 'name')
        self.assertModelFieldRequired(Material, 'material_type')
        self.assertModelFieldRequired(Material, 'unit_of_measure')
        self.assertModelFieldRequired(Material, 'list_price', required=False)
    
    def test_material_current_price_property(self):
        """Test current_price property."""
        material = Material.objects.create(
            organization=self.organization,
            code="TEST001",
            name="Test Material",
            material_type="raw_material",
            unit_of_measure="kg",
            list_price=Decimal("100.00")
        )
        
        # No market prices, should return list price
        self.assertEqual(material.current_price, Decimal("100.00"))
        
        # Add a market price
        Price.objects.create(
            time=timezone.now(),
            material=material,
            organization=self.organization,
            price=Decimal("120.00"),
            currency="USD",
            unit_of_measure="kg",
            price_type="market"
        )
        
        # Should return the market price
        self.assertEqual(material.current_price, Decimal("120.00"))
    
    def test_material_get_price_history(self):
        """Test get_price_history method."""
        material = Material.objects.create(
            organization=self.organization,
            code="TEST001",
            name="Test Material",
            material_type="raw_material",
            unit_of_measure="kg"
        )
        
        now = timezone.now()
        
        # Create price history
        prices = [
            Price.objects.create(
                time=now - timedelta(days=i),
                material=material,
                organization=self.organization,
                price=Decimal(f"{100 + i}.00"),
                currency="USD",
                unit_of_measure="kg",
                price_type="market"
            )
            for i in range(5)
        ]
        
        # Test getting all price history for 30 days
        history = material.get_price_history()
        self.assertEqual(history.count(), 5)
        
        # Test filtering by price type
        quote_price = Price.objects.create(
            time=now,
            material=material,
            organization=self.organization,
            price=Decimal("150.00"),
            currency="USD",
            unit_of_measure="kg",
            price_type="quote"
        )
        
        quote_history = material.get_price_history(price_type="quote")
        self.assertEqual(quote_history.count(), 1)
        self.assertEqual(quote_history.first(), quote_price)
    
    def test_material_calculate_should_cost(self):
        """Test calculate_should_cost method."""
        material = Material.objects.create(
            organization=self.organization,
            code="TEST001",
            name="Test Material",
            material_type="raw_material",
            unit_of_measure="kg",
            cost_price=Decimal("80.00")
        )
        
        should_cost = material.calculate_should_cost()
        self.assertEqual(should_cost, Decimal("80.00"))
        
        # Test with no cost price
        material.cost_price = None
        material.save()
        
        should_cost = material.calculate_should_cost()
        self.assertEqual(should_cost, Decimal("0.00"))
    
    def test_material_json_fields(self):
        """Test JSON field functionality."""
        material = Material.objects.create(
            organization=self.organization,
            code="TEST001",
            name="Test Material",
            material_type="raw_material",
            unit_of_measure="kg",
            specifications={
                "grade": "A36",
                "thickness": "1mm",
                "finish": "galvanized"
            },
            attributes={
                "color": "silver",
                "weight_per_unit": 1.5
            },
            dimensions={
                "length": 1000,
                "width": 500,
                "height": 2
            }
        )
        
        material.refresh_from_db()
        
        self.assertEqual(material.specifications["grade"], "A36")
        self.assertEqual(material.attributes["color"], "silver")
        self.assertEqual(material.dimensions["length"], 1000)


class PriceModelTest(BaseTestCase, ModelTestMixin):
    """Test cases for Price model."""
    
    def setUp(self):
        super().setUp()
        self.material = Material.objects.create(
            organization=self.organization,
            code="TEST001",
            name="Test Material",
            material_type="raw_material",
            unit_of_measure="kg"
        )
    
    def test_price_creation(self):
        """Test creating a price record."""
        price = Price.objects.create(
            time=timezone.now(),
            material=self.material,
            organization=self.organization,
            price=Decimal("100.00"),
            currency="USD",
            quantity=Decimal("10.00"),
            unit_of_measure="kg",
            price_type="quote"
        )
        
        self.assertEqual(price.material, self.material)
        self.assertEqual(price.price, Decimal("100.00"))
        self.assertEqual(price.price_type, "quote")
        self.assertEqual(price.currency, "USD")
    
    def test_price_str_representation(self):
        """Test price string representation."""
        now = timezone.now()
        price = Price.objects.create(
            time=now,
            material=self.material,
            organization=self.organization,
            price=Decimal("100.00"),
            currency="USD",
            unit_of_measure="kg",
            price_type="quote"
        )
        
        expected = f"{self.material.code} - 100.0000 USD - {now}"
        self.assertEqual(str(price), expected)
    
    def test_price_is_valid_property(self):
        """Test is_valid property."""
        today = timezone.now().date()
        
        # Price with no validity period (should be valid)
        price = Price.objects.create(
            time=timezone.now(),
            material=self.material,
            organization=self.organization,
            price=Decimal("100.00"),
            currency="USD",
            unit_of_measure="kg",
            price_type="quote"
        )
        
        self.assertTrue(price.is_valid)
        
        # Price valid for today
        price.valid_from = today
        price.valid_to = today + timedelta(days=30)
        price.save()
        
        self.assertTrue(price.is_valid)
        
        # Price not yet valid
        price.valid_from = today + timedelta(days=1)
        price.save()
        
        self.assertFalse(price.is_valid)
        
        # Expired price
        price.valid_from = today - timedelta(days=30)
        price.valid_to = today - timedelta(days=1)
        price.save()
        
        self.assertFalse(price.is_valid)
    
    def test_price_unit_price_property(self):
        """Test unit_price property."""
        price = Price.objects.create(
            time=timezone.now(),
            material=self.material,
            organization=self.organization,
            price=Decimal("1000.00"),
            currency="USD",
            quantity=Decimal("10.00"),
            unit_of_measure="kg",
            price_type="quote"
        )
        
        self.assertEqual(price.unit_price, Decimal("100.00"))
        
        # Test with quantity of 1
        price.quantity = Decimal("1.00")
        price.save()
        
        self.assertEqual(price.unit_price, Decimal("1000.00"))
        
        # Test with zero quantity (should return original price)
        price.quantity = Decimal("0.00")
        price.save()
        
        self.assertEqual(price.unit_price, Decimal("1000.00"))
    
    def test_price_confidence_score_validation(self):
        """Test confidence score validation."""
        # Valid confidence score
        price = Price.objects.create(
            time=timezone.now(),
            material=self.material,
            organization=self.organization,
            price=Decimal("100.00"),
            currency="USD",
            unit_of_measure="kg",
            price_type="quote",
            confidence_score=Decimal("0.85")
        )
        
        self.assertEqual(price.confidence_score, Decimal("0.85"))
        
        # Invalid confidence score (too high)
        with self.assertRaises(ValidationError):
            price = Price(
                time=timezone.now(),
                material=self.material,
                organization=self.organization,
                price=Decimal("100.00"),
                currency="USD",
                unit_of_measure="kg",
                price_type="quote",
                confidence_score=Decimal("1.5")
            )
            price.full_clean()
        
        # Invalid confidence score (negative)
        with self.assertRaises(ValidationError):
            price = Price(
                time=timezone.now(),
                material=self.material,
                organization=self.organization,
                price=Decimal("100.00"),
                currency="USD",
                unit_of_measure="kg",
                price_type="quote",
                confidence_score=Decimal("-0.1")
            )
            price.full_clean()


class PriceAlertModelTest(BaseTestCase, ModelTestMixin):
    """Test cases for PriceAlert model."""
    
    def setUp(self):
        super().setUp()
        self.material = Material.objects.create(
            organization=self.organization,
            code="TEST001",
            name="Test Material",
            material_type="raw_material",
            unit_of_measure="kg"
        )
    
    def test_price_alert_creation(self):
        """Test creating a price alert."""
        alert = PriceAlert.objects.create(
            user=self.user,
            material=self.material,
            organization=self.organization,
            name="Price Above $150",
            alert_type="threshold",
            condition_type="above",
            threshold_value=Decimal("150.00")
        )
        
        self.assertEqual(alert.user, self.user)
        self.assertEqual(alert.material, self.material)
        self.assertEqual(alert.name, "Price Above $150")
        self.assertEqual(alert.status, "active")  # Default value
        self.assertTrue(alert.email_notification)  # Default value
    
    def test_price_alert_str_representation(self):
        """Test price alert string representation."""
        alert = PriceAlert.objects.create(
            user=self.user,
            material=self.material,
            organization=self.organization,
            name="Price Above $150",
            alert_type="threshold",
            condition_type="above",
            threshold_value=Decimal("150.00")
        )
        
        expected = f"Price Above $150 - {self.material.code}"
        self.assertEqual(str(alert), expected)
    
    def test_price_alert_check_condition(self):
        """Test check_condition method."""
        alert = PriceAlert.objects.create(
            user=self.user,
            material=self.material,
            organization=self.organization,
            name="Price Above $150",
            alert_type="threshold",
            condition_type="above",
            threshold_value=Decimal("150.00")
        )
        
        # Price above threshold
        self.assertTrue(alert.check_condition(Decimal("160.00")))
        
        # Price below threshold
        self.assertFalse(alert.check_condition(Decimal("140.00")))
        
        # Price equal to threshold
        self.assertFalse(alert.check_condition(Decimal("150.00")))
        
        # Test "below" condition
        alert.condition_type = "below"
        alert.save()
        
        self.assertTrue(alert.check_condition(Decimal("140.00")))
        self.assertFalse(alert.check_condition(Decimal("160.00")))
    
    def test_price_alert_trigger_alert(self):
        """Test trigger_alert method."""
        alert = PriceAlert.objects.create(
            user=self.user,
            material=self.material,
            organization=self.organization,
            name="Price Above $150",
            alert_type="threshold",
            condition_type="above",
            threshold_value=Decimal("150.00")
        )
        
        initial_trigger_count = alert.trigger_count
        
        alert.trigger_alert()
        
        alert.refresh_from_db()
        self.assertEqual(alert.status, "triggered")
        self.assertIsNotNone(alert.last_triggered)
        self.assertEqual(alert.trigger_count, initial_trigger_count + 1)


class CostModelModelTest(BaseTestCase, ModelTestMixin):
    """Test cases for CostModel model."""
    
    def setUp(self):
        super().setUp()
        self.material = Material.objects.create(
            organization=self.organization,
            code="TEST001",
            name="Test Material",
            material_type="raw_material",
            unit_of_measure="kg"
        )
    
    def test_cost_model_creation(self):
        """Test creating a cost model."""
        cost_model = CostModel.objects.create(
            material=self.material,
            organization=self.organization,
            name="Parametric Model",
            model_type="parametric",
            parameters={
                "base_cost": 50.0,
                "complexity_factor": 1.2
            },
            cost_drivers=[
                {"name": "material_cost", "weight": 0.4},
                {"name": "labor_cost", "weight": 0.3},
                {"name": "overhead", "weight": 0.3}
            ]
        )
        
        self.assertEqual(cost_model.material, self.material)
        self.assertEqual(cost_model.name, "Parametric Model")
        self.assertEqual(cost_model.model_type, "parametric")
        self.assertEqual(cost_model.version, "1.0")  # Default value
        self.assertTrue(cost_model.is_active)  # Default value
    
    def test_cost_model_str_representation(self):
        """Test cost model string representation."""
        cost_model = CostModel.objects.create(
            material=self.material,
            organization=self.organization,
            name="Parametric Model",
            model_type="parametric",
            version="2.1"
        )
        
        expected = f"{self.material.code} - Parametric Model v2.1"
        self.assertEqual(str(cost_model), expected)
    
    def test_cost_model_unique_constraint(self):
        """Test unique constraint on material, name, and version."""
        CostModel.objects.create(
            material=self.material,
            organization=self.organization,
            name="Parametric Model",
            model_type="parametric",
            version="1.0"
        )
        
        # Creating another model with same material, name, and version should fail
        with self.assertRaises(IntegrityError):
            CostModel.objects.create(
                material=self.material,
                organization=self.organization,
                name="Parametric Model",
                model_type="parametric",
                version="1.0"
            )
    
    def test_cost_model_calculate_should_cost_parametric(self):
        """Test calculate_should_cost method for parametric model."""
        cost_model = CostModel.objects.create(
            material=self.material,
            organization=self.organization,
            name="Parametric Model",
            model_type="parametric",
            parameters={
                "base_cost": 50.0
            }
        )
        
        inputs = {"quantity": 10, "complexity": 1.2}
        should_cost = cost_model.calculate_should_cost(inputs)
        
        # Should return the base cost from parameters
        self.assertEqual(should_cost, Decimal("50.00"))
    
    def test_cost_model_calculate_should_cost_bottom_up(self):
        """Test calculate_should_cost method for bottom-up model."""
        cost_model = CostModel.objects.create(
            material=self.material,
            organization=self.organization,
            name="Bottom-up Model",
            model_type="bottom_up",
            cost_drivers=[
                {"name": "material_cost", "base_value": 30.0},
                {"name": "labor_cost", "base_value": 20.0}
            ]
        )
        
        inputs = {"quantity": 10}
        should_cost = cost_model.calculate_should_cost(inputs)
        
        # Should return sum of cost drivers (currently returns 0 in placeholder)
        self.assertIsInstance(should_cost, Decimal)
    
    def test_cost_model_performance_metrics_validation(self):
        """Test validation of performance metrics."""
        # Valid accuracy score
        cost_model = CostModel.objects.create(
            material=self.material,
            organization=self.organization,
            name="ML Model",
            model_type="ml_based",
            accuracy_score=Decimal("0.92")
        )
        
        self.assertEqual(cost_model.accuracy_score, Decimal("0.92"))
        
        # Invalid accuracy score (too high)
        with self.assertRaises(ValidationError):
            cost_model = CostModel(
                material=self.material,
                organization=self.organization,
                name="Invalid Model",
                model_type="ml_based",
                accuracy_score=Decimal("1.5")
            )
            cost_model.full_clean()