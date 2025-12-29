"""
Factories for pricing-related models.
"""
import factory
import factory.fuzzy
from decimal import Decimal
from datetime import datetime, timedelta
from django.utils import timezone

from apps.pricing.models import Material, Price, PriceBenchmark, PriceAlert, CostModel
from .base_factories import (
    OrganizationFactory, UserFactory, CategoryFactory, 
    FactoryUtils, Sequences
)


class MaterialFactory(factory.django.DjangoModelFactory):
    """Factory for Material model."""
    
    class Meta:
        model = Material
    
    organization = factory.SubFactory(OrganizationFactory)
    code = Sequences.material_code()
    name = factory.Faker('sentence', nb_words=3)
    description = factory.Faker('text', max_nb_chars=500)
    
    material_type = FactoryUtils.random_choice([
        'raw_material', 'component', 'assembly', 'finished_good', 'service'
    ])
    
    category = factory.SubFactory(CategoryFactory)
    unit_of_measure = FactoryUtils.random_choice([
        'kg', 'lb', 'pieces', 'meters', 'feet', 'liters', 'gallons'
    ])
    
    # Physical properties
    weight = FactoryUtils.random_decimal(0.1, 1000.0)
    weight_unit = 'kg'
    
    dimensions = factory.LazyFunction(lambda: {
        'length': float(factory.Faker('pydecimal', left_digits=3, right_digits=2, positive=True).generate()),
        'width': float(factory.Faker('pydecimal', left_digits=3, right_digits=2, positive=True).generate()),
        'height': float(factory.Faker('pydecimal', left_digits=2, right_digits=2, positive=True).generate()),
        'unit': 'mm'
    })
    
    # Specifications and attributes
    specifications = factory.LazyFunction(lambda: {
        'grade': factory.Faker('word').generate(),
        'finish': factory.Faker('word').generate(),
        'tolerance': '±0.1mm',
        'standard': 'ISO9001'
    })
    
    attributes = factory.LazyFunction(lambda: {
        'color': factory.Faker('color_name').generate(),
        'recyclable': factory.Faker('boolean').generate(),
        'hazardous': False,
        'shelf_life_days': factory.Faker('random_int', min=30, max=3650).generate()
    })
    
    # Status and lifecycle
    status = FactoryUtils.random_choice([
        'active', 'inactive', 'discontinued', 'development'
    ])
    
    lifecycle_stage = FactoryUtils.random_choice([
        'design', 'prototype', 'production', 'mature', 'end_of_life'
    ])
    
    # Pricing information
    list_price = FactoryUtils.random_decimal(1.0, 10000.0)
    cost_price = factory.LazyAttribute(lambda obj: obj.list_price * Decimal('0.7') if obj.list_price else None)
    currency = 'USD'
    
    # Supply chain information
    lead_time_days = FactoryUtils.random_positive_integer(1, 120)
    minimum_order_quantity = FactoryUtils.random_decimal(1.0, 1000.0)
    
    # Compliance and certifications
    certifications = factory.LazyFunction(lambda: [
        'ISO9001', 'CE', 'RoHS'
    ])
    
    compliance_standards = factory.LazyFunction(lambda: [
        'REACH', 'WEEE', 'FDA'
    ])
    
    search_keywords = factory.LazyAttribute(
        lambda obj: f"{obj.name} {obj.material_type} {obj.category.name if obj.category else ''}"
    )
    
    created_at = factory.LazyFunction(timezone.now)
    updated_at = factory.LazyFunction(timezone.now)


class SteelMaterialFactory(MaterialFactory):
    """Specialized factory for steel materials."""
    
    material_type = 'raw_material'
    name = factory.LazyAttribute(lambda obj: f"Steel Plate {obj.code}")
    
    specifications = factory.LazyFunction(lambda: {
        'grade': factory.Faker('random_element', elements=('A36', 'A572', 'A514')).generate(),
        'finish': 'hot_rolled',
        'thickness': f"{factory.Faker('random_int', min=5, max=50).generate()}mm",
        'surface_treatment': 'pickled_oiled'
    })
    
    attributes = factory.LazyFunction(lambda: {
        'tensile_strength': f"{factory.Faker('random_int', min=400, max=800).generate()} MPa",
        'yield_strength': f"{factory.Faker('random_int', min=250, max=600).generate()} MPa",
        'corrosion_resistant': False,
        'weldable': True
    })
    
    weight = FactoryUtils.random_decimal(10.0, 5000.0)
    unit_of_measure = 'kg'


class ElectronicComponentFactory(MaterialFactory):
    """Specialized factory for electronic components."""
    
    material_type = 'component'
    name = factory.LazyAttribute(lambda obj: f"Electronic Component {obj.code}")
    
    specifications = factory.LazyFunction(lambda: {
        'voltage_rating': f"{factory.Faker('random_int', min=3, max=24).generate()}V",
        'current_rating': f"{factory.Faker('pydecimal', left_digits=2, right_digits=2).generate()}A",
        'temperature_range': '-40°C to +85°C',
        'package_type': factory.Faker('random_element', elements=('SMD', 'THT', 'BGA')).generate()
    })
    
    attributes = factory.LazyFunction(lambda: {
        'lead_free': True,
        'rohs_compliant': True,
        'esd_sensitive': factory.Faker('boolean').generate(),
        'moisture_sensitive': factory.Faker('boolean').generate()
    })
    
    weight = FactoryUtils.random_decimal(0.001, 10.0)
    unit_of_measure = 'pieces'


class PriceFactory(factory.django.DjangoModelFactory):
    """Factory for Price model."""
    
    class Meta:
        model = Price
    
    time = FactoryUtils.random_date_range(30, 0)
    material = factory.SubFactory(MaterialFactory)
    organization = factory.SelfAttribute('material.organization')
    
    price = FactoryUtils.random_decimal(1.0, 10000.0)
    currency = 'USD'
    quantity = FactoryUtils.random_decimal(1.0, 1000.0)
    unit_of_measure = factory.SelfAttribute('material.unit_of_measure')
    
    price_type = FactoryUtils.random_choice([
        'quote', 'contract', 'market', 'predicted', 'should_cost', 'benchmark'
    ])
    
    # Validity period
    valid_from = factory.LazyFunction(lambda: timezone.now().date())
    valid_to = factory.LazyFunction(lambda: timezone.now().date() + timedelta(days=30))
    
    source = factory.Faker('company')
    confidence_score = FactoryUtils.random_decimal(0.1, 1.0, 4)
    
    metadata = factory.LazyFunction(lambda: {
        'negotiated': factory.Faker('boolean').generate(),
        'volume_discount': factory.Faker('pydecimal', left_digits=1, right_digits=3).generate(),
        'payment_terms': 'NET30'
    })
    
    created_by = factory.SubFactory(UserFactory)


class MarketPriceFactory(PriceFactory):
    """Factory for market prices."""
    
    price_type = 'market'
    source = 'Market Data Provider'
    confidence_score = FactoryUtils.random_decimal(0.8, 1.0, 4)


class QuotePriceFactory(PriceFactory):
    """Factory for quote prices."""
    
    price_type = 'quote'
    source = factory.Faker('company')
    confidence_score = FactoryUtils.random_decimal(0.9, 1.0, 4)
    
    metadata = factory.LazyFunction(lambda: {
        'quote_id': factory.Faker('uuid4').generate(),
        'valid_days': factory.Faker('random_int', min=15, max=90).generate(),
        'supplier_rating': factory.Faker('random_int', min=1, max=5).generate()
    })


class PredictedPriceFactory(PriceFactory):
    """Factory for ML predicted prices."""
    
    price_type = 'predicted'
    source = 'ML Prediction Service'
    confidence_score = FactoryUtils.random_decimal(0.6, 0.95, 4)
    
    metadata = factory.LazyFunction(lambda: {
        'model_version': '1.2.3',
        'prediction_timestamp': timezone.now().isoformat(),
        'feature_importance': {
            'material_type': 0.3,
            'quantity': 0.25,
            'market_conditions': 0.2,
            'supplier_tier': 0.15,
            'lead_time': 0.1
        }
    })


class PriceBenchmarkFactory(factory.django.DjangoModelFactory):
    """Factory for PriceBenchmark model."""
    
    class Meta:
        model = PriceBenchmark
    
    material = factory.SubFactory(MaterialFactory)
    organization = factory.SelfAttribute('material.organization')
    
    benchmark_type = FactoryUtils.random_choice([
        'market_average', 'lowest_quote', 'preferred_supplier', 
        'historical_average', 'should_cost'
    ])
    
    benchmark_price = FactoryUtils.random_decimal(1.0, 10000.0)
    currency = 'USD'
    quantity = FactoryUtils.random_decimal(1.0, 1000.0)
    
    # Period information
    period_start = factory.LazyFunction(lambda: timezone.now().date() - timedelta(days=30))
    period_end = factory.LazyFunction(lambda: timezone.now().date())
    
    # Statistics
    sample_size = FactoryUtils.random_positive_integer(10, 100)
    min_price = factory.LazyAttribute(lambda obj: obj.benchmark_price * Decimal('0.8'))
    max_price = factory.LazyAttribute(lambda obj: obj.benchmark_price * Decimal('1.3'))
    std_deviation = factory.LazyAttribute(lambda obj: obj.benchmark_price * Decimal('0.15'))
    
    calculation_method = factory.Faker('sentence')
    data_sources = factory.LazyFunction(lambda: [
        'supplier_quotes', 'market_data', 'historical_prices'
    ])
    
    confidence_level = FactoryUtils.random_decimal(0.8, 0.99, 4)
    
    created_at = factory.LazyFunction(timezone.now)
    updated_at = factory.LazyFunction(timezone.now)


class PriceAlertFactory(factory.django.DjangoModelFactory):
    """Factory for PriceAlert model."""
    
    class Meta:
        model = PriceAlert
    
    user = factory.SubFactory(UserFactory)
    material = factory.SubFactory(MaterialFactory)
    organization = factory.SelfAttribute('user.organization')
    
    name = factory.LazyAttribute(lambda obj: f"Price Alert for {obj.material.name}")
    
    alert_type = FactoryUtils.random_choice([
        'threshold', 'anomaly', 'trend', 'forecast'
    ])
    
    condition_type = FactoryUtils.random_choice([
        'above', 'below', 'change_percent', 'change_absolute'
    ])
    
    threshold_value = FactoryUtils.random_decimal(1.0, 1000.0)
    
    status = FactoryUtils.random_choice([
        'active', 'triggered', 'resolved', 'disabled'
    ])
    
    trigger_count = FactoryUtils.random_positive_integer(0, 10)
    
    email_notification = True
    push_notification = factory.Faker('boolean')
    
    created_at = factory.LazyFunction(timezone.now)
    updated_at = factory.LazyFunction(timezone.now)


class CostModelFactory(factory.django.DjangoModelFactory):
    """Factory for CostModel model."""
    
    class Meta:
        model = CostModel
    
    material = factory.SubFactory(MaterialFactory)
    organization = factory.SelfAttribute('material.organization')
    
    name = factory.LazyAttribute(lambda obj: f"Cost Model for {obj.material.code}")
    
    model_type = FactoryUtils.random_choice([
        'parametric', 'bottom_up', 'regression', 'ml_based'
    ])
    
    version = factory.Faker('semantic_version')
    
    # Model parameters
    parameters = factory.LazyFunction(lambda: {
        'base_cost': float(factory.Faker('pydecimal', left_digits=3, right_digits=2).generate()),
        'labor_rate': 25.0,
        'overhead_rate': 0.15,
        'material_cost_multiplier': 1.2
    })
    
    cost_drivers = factory.LazyFunction(lambda: [
        {
            'name': 'material_cost',
            'weight': 0.4,
            'type': 'variable',
            'calculation': 'quantity * unit_cost'
        },
        {
            'name': 'labor_cost',
            'weight': 0.3,
            'type': 'variable',
            'calculation': 'hours * rate'
        },
        {
            'name': 'overhead',
            'weight': 0.3,
            'type': 'fixed',
            'calculation': 'percentage_of_direct_costs'
        }
    ])
    
    # Model performance metrics
    accuracy_score = FactoryUtils.random_decimal(0.7, 0.95, 4)
    r_squared = FactoryUtils.random_decimal(0.6, 0.9, 4)
    mean_absolute_error = FactoryUtils.random_decimal(5.0, 50.0, 2)
    
    is_active = True
    last_trained = factory.LazyFunction(timezone.now)
    training_data_count = FactoryUtils.random_positive_integer(100, 10000)
    
    created_at = factory.LazyFunction(timezone.now)
    updated_at = factory.LazyFunction(timezone.now)


# Batch creation utilities for pricing
class PricingBatchFactories:
    """Utilities for creating batches of pricing-related objects."""
    
    @staticmethod
    def create_material_with_price_history(days=30, prices_per_day=2):
        """Create material with extensive price history."""
        material = MaterialFactory()
        prices = []
        
        for day in range(days):
            date = timezone.now() - timedelta(days=day)
            for _ in range(prices_per_day):
                price = PriceFactory(
                    material=material,
                    time=date,
                    organization=material.organization
                )
                prices.append(price)
        
        return {
            'material': material,
            'prices': prices
        }
    
    @staticmethod
    def create_material_with_alerts(alert_count=3):
        """Create material with multiple price alerts."""
        material = MaterialFactory()
        alerts = []
        
        for i in range(alert_count):
            alert = PriceAlertFactory(
                material=material,
                organization=material.organization
            )
            alerts.append(alert)
        
        return {
            'material': material,
            'alerts': alerts
        }
    
    @staticmethod
    def create_pricing_dataset(material_count=50, price_count_per_material=20):
        """Create comprehensive pricing dataset for testing."""
        materials = MaterialFactory.create_batch(material_count)
        all_prices = []
        
        for material in materials:
            prices = PriceFactory.create_batch(
                price_count_per_material,
                material=material,
                organization=material.organization
            )
            all_prices.extend(prices)
        
        # Create some benchmarks
        benchmarks = [
            PriceBenchmarkFactory(material=material)
            for material in materials[:10]
        ]
        
        return {
            'materials': materials,
            'prices': all_prices,
            'benchmarks': benchmarks
        }


# Specialized factories for testing edge cases
class EdgeCasePricingFactories:
    """Factories for testing edge cases and error conditions."""
    
    @staticmethod
    def create_material_with_null_prices():
        """Create material with missing price information."""
        return MaterialFactory(
            list_price=None,
            cost_price=None,
            minimum_order_quantity=None
        )
    
    @staticmethod
    def create_expired_price():
        """Create price that has expired."""
        return PriceFactory(
            valid_from=timezone.now().date() - timedelta(days=60),
            valid_to=timezone.now().date() - timedelta(days=30)
        )
    
    @staticmethod
    def create_future_price():
        """Create price that is valid in the future."""
        return PriceFactory(
            valid_from=timezone.now().date() + timedelta(days=30),
            valid_to=timezone.now().date() + timedelta(days=60)
        )
    
    @staticmethod
    def create_zero_price():
        """Create price with zero value."""
        return PriceFactory(price=Decimal('0.00'))
    
    @staticmethod
    def create_negative_quantity():
        """Create price with negative quantity."""
        return PriceFactory(quantity=Decimal('-10.00'))
    
    @staticmethod
    def create_material_with_long_name():
        """Create material with extremely long name for testing limits."""
        return MaterialFactory(
            name='x' * 500,  # Very long name
            description='y' * 2000  # Very long description
        )