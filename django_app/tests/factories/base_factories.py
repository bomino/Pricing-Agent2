"""
Base factories for Django models using factory_boy.
"""
import factory
import factory.fuzzy
from decimal import Decimal
from datetime import datetime, timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.core.models import Organization, Tenant, Category
from apps.accounts.models import User

# Get the User model
User = get_user_model()


class OrganizationFactory(factory.django.DjangoModelFactory):
    """Factory for Organization model."""
    
    class Meta:
        model = Organization
    
    name = factory.Faker('company')
    slug = factory.LazyAttribute(lambda obj: obj.name.lower().replace(' ', '-'))
    is_active = True
    description = factory.Faker('text', max_nb_chars=200)
    website = factory.Faker('url')
    contact_email = factory.Faker('email')
    contact_phone = factory.Faker('phone_number')
    address = factory.Faker('address')
    
    # Settings as JSON field
    settings = factory.LazyFunction(lambda: {
        'default_currency': 'USD',
        'timezone': 'UTC',
        'business_type': 'manufacturing'
    })
    
    created_at = factory.LazyFunction(timezone.now)
    updated_at = factory.LazyFunction(timezone.now)


class TenantFactory(factory.django.DjangoModelFactory):
    """Factory for Tenant model."""
    
    class Meta:
        model = Tenant
    
    organization = factory.SubFactory(OrganizationFactory)
    name = factory.Faker('company')
    slug = factory.LazyAttribute(lambda obj: obj.name.lower().replace(' ', '-'))
    schema_name = factory.LazyAttribute(lambda obj: f"tenant_{obj.slug}")
    is_active = True
    domain = factory.Faker('domain_name')
    
    # Configuration as JSON field
    config = factory.LazyFunction(lambda: {
        'features': ['pricing', 'rfq', 'analytics'],
        'limits': {
            'max_users': 100,
            'max_materials': 10000
        }
    })
    
    created_at = factory.LazyFunction(timezone.now)


class UserFactory(factory.django.DjangoModelFactory):
    """Factory for User model."""
    
    class Meta:
        model = User
    
    username = factory.Sequence(lambda n: f'user{n}')
    email = factory.Faker('email')
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    is_active = True
    is_staff = False
    is_superuser = False
    organization = factory.SubFactory(OrganizationFactory)
    
    # Profile data as JSON field
    profile_data = factory.LazyFunction(lambda: {
        'department': 'procurement',
        'job_title': 'buyer',
        'phone': '+1-555-123-4567'
    })
    
    date_joined = factory.LazyFunction(timezone.now)


class AdminUserFactory(UserFactory):
    """Factory for admin users."""
    
    is_staff = True
    is_superuser = True
    profile_data = factory.LazyFunction(lambda: {
        'department': 'admin',
        'job_title': 'system_admin',
        'phone': '+1-555-123-4567'
    })


class CategoryFactory(factory.django.DjangoModelFactory):
    """Factory for Category model."""
    
    class Meta:
        model = Category
    
    name = factory.Faker('word')
    slug = factory.LazyAttribute(lambda obj: obj.name.lower())
    description = factory.Faker('sentence')
    organization = factory.SubFactory(OrganizationFactory)
    parent = None
    is_active = True
    sort_order = factory.Sequence(lambda n: n)
    
    # Metadata as JSON field
    metadata = factory.LazyFunction(lambda: {
        'color': '#007bff',
        'icon': 'category-icon'
    })
    
    created_at = factory.LazyFunction(timezone.now)


class SubCategoryFactory(CategoryFactory):
    """Factory for subcategory."""
    
    parent = factory.SubFactory(CategoryFactory)


# Trait mixins for common variations
class ActiveModelTrait:
    """Trait for active models."""
    is_active = True


class InactiveModelTrait:
    """Trait for inactive models."""
    is_active = False


class RecentModelTrait:
    """Trait for recently created models."""
    created_at = factory.LazyFunction(lambda: timezone.now() - timedelta(days=1))
    updated_at = factory.LazyFunction(timezone.now)


class OldModelTrait:
    """Trait for old models."""
    created_at = factory.LazyFunction(lambda: timezone.now() - timedelta(days=365))
    updated_at = factory.LazyFunction(lambda: timezone.now() - timedelta(days=30))


# Factory sequences for consistent test data
class Sequences:
    """Common sequences for factory data."""
    
    @staticmethod
    def material_code():
        """Generate sequential material codes."""
        return factory.Sequence(lambda n: f'MAT{n:06d}')
    
    @staticmethod
    def supplier_code():
        """Generate sequential supplier codes."""
        return factory.Sequence(lambda n: f'SUP{n:04d}')
    
    @staticmethod
    def rfq_number():
        """Generate sequential RFQ numbers."""
        return factory.Sequence(lambda n: f'RFQ{n:06d}')
    
    @staticmethod
    def quote_number():
        """Generate sequential quote numbers."""
        return factory.Sequence(lambda n: f'QUO{n:06d}')


# Factory utilities
class FactoryUtils:
    """Utility functions for factories."""
    
    @staticmethod
    def random_decimal(min_value=0.01, max_value=1000.00, decimal_places=2):
        """Generate random decimal value."""
        return factory.fuzzy.FuzzyDecimal(
            low=Decimal(str(min_value)),
            high=Decimal(str(max_value)),
            precision=decimal_places
        )
    
    @staticmethod
    def random_positive_integer(min_value=1, max_value=1000):
        """Generate random positive integer."""
        return factory.fuzzy.FuzzyInteger(min_value, max_value)
    
    @staticmethod
    def random_date_range(start_days_ago=365, end_days_ago=0):
        """Generate random date within range."""
        start_date = timezone.now() - timedelta(days=start_days_ago)
        end_date = timezone.now() - timedelta(days=end_days_ago)
        return factory.fuzzy.FuzzyDateTime(start_date, end_date)
    
    @staticmethod
    def random_choice(choices):
        """Generate random choice from list."""
        return factory.fuzzy.FuzzyChoice(choices)
    
    @staticmethod
    def random_json_data(**kwargs):
        """Generate random JSON data with specified keys."""
        def generate_data():
            data = {}
            for key, value_generator in kwargs.items():
                if callable(value_generator):
                    data[key] = value_generator()
                else:
                    data[key] = value_generator
            return data
        
        return factory.LazyFunction(generate_data)


# Batch creation utilities
class BatchFactories:
    """Utilities for creating batches of related objects."""
    
    @staticmethod
    def create_organization_with_users(user_count=5, admin_count=1):
        """Create organization with multiple users."""
        org = OrganizationFactory()
        
        # Create regular users
        users = UserFactory.create_batch(
            user_count,
            organization=org
        )
        
        # Create admin users
        admins = AdminUserFactory.create_batch(
            admin_count,
            organization=org
        )
        
        return {
            'organization': org,
            'users': users,
            'admins': admins
        }
    
    @staticmethod
    def create_category_hierarchy(depth=3, children_per_level=3):
        """Create nested category hierarchy."""
        root_category = CategoryFactory()
        categories = [root_category]
        
        def create_level(parent, level, max_level):
            if level >= max_level:
                return
            
            for _ in range(children_per_level):
                child = CategoryFactory(parent=parent, organization=parent.organization)
                categories.append(child)
                create_level(child, level + 1, max_level)
        
        create_level(root_category, 1, depth)
        return categories