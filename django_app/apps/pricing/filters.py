"""
Django filters for pricing API endpoints
"""
import django_filters
from django import forms
from django.db.models import Q
from apps.pricing.models import Material, Price, PriceBenchmark, PriceAlert


class MaterialFilter(django_filters.FilterSet):
    """Filter for Material model"""
    
    # Basic filters
    code = django_filters.CharFilter(lookup_expr='icontains')
    name = django_filters.CharFilter(lookup_expr='icontains')
    material_type = django_filters.ChoiceFilter(choices=Material.MATERIAL_TYPES)
    status = django_filters.MultipleChoiceFilter(choices=Material.STATUS_CHOICES)
    category = django_filters.ModelMultipleChoiceFilter(
        field_name='category',
        to_field_name='id',
        queryset=lambda request: None  # Set in __init__
    )
    
    # Price range filters
    min_list_price = django_filters.NumberFilter(field_name='list_price', lookup_expr='gte')
    max_list_price = django_filters.NumberFilter(field_name='list_price', lookup_expr='lte')
    min_cost_price = django_filters.NumberFilter(field_name='cost_price', lookup_expr='gte')
    max_cost_price = django_filters.NumberFilter(field_name='cost_price', lookup_expr='lte')
    
    # Date filters
    created_after = django_filters.DateFilter(field_name='created_at', lookup_expr='gte')
    created_before = django_filters.DateFilter(field_name='created_at', lookup_expr='lte')
    updated_after = django_filters.DateFilter(field_name='updated_at', lookup_expr='gte')
    updated_before = django_filters.DateFilter(field_name='updated_at', lookup_expr='lte')
    
    # Lead time filter
    max_lead_time = django_filters.NumberFilter(field_name='lead_time_days', lookup_expr='lte')
    
    # Has price filter
    has_current_price = django_filters.BooleanFilter(method='filter_has_current_price')
    
    # Full text search
    search = django_filters.CharFilter(method='filter_search')
    
    # Certification filter
    certifications = django_filters.CharFilter(method='filter_certifications')
    
    class Meta:
        model = Material
        fields = [
            'code', 'name', 'material_type', 'status', 'category',
            'min_list_price', 'max_list_price', 'min_cost_price', 'max_cost_price',
            'created_after', 'created_before', 'updated_after', 'updated_before',
            'max_lead_time', 'has_current_price', 'search', 'certifications'
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request:
            from apps.core.models import Category
            self.filters['category'].queryset = Category.objects.filter(is_active=True)
    
    def filter_has_current_price(self, queryset, name, value):
        """Filter materials with/without current prices"""
        if value:
            return queryset.filter(prices__isnull=False).distinct()
        else:
            return queryset.filter(prices__isnull=True).distinct()
    
    def filter_search(self, queryset, name, value):
        """Full text search across multiple fields"""
        if not value:
            return queryset
        
        return queryset.filter(
            Q(code__icontains=value) |
            Q(name__icontains=value) |
            Q(description__icontains=value) |
            Q(search_keywords__icontains=value) |
            Q(category__name__icontains=value)
        ).distinct()
    
    def filter_certifications(self, queryset, name, value):
        """Filter by certifications"""
        if not value:
            return queryset
        
        return queryset.filter(certifications__icontains=value)


class PriceFilter(django_filters.FilterSet):
    """Filter for Price model"""
    
    # Material filters
    material = django_filters.ModelChoiceFilter(
        queryset=lambda request: None  # Set in __init__
    )
    material_code = django_filters.CharFilter(
        field_name='material__code',
        lookup_expr='icontains'
    )
    material_category = django_filters.ModelChoiceFilter(
        field_name='material__category',
        queryset=lambda request: None  # Set in __init__
    )
    
    # Supplier filters
    supplier = django_filters.ModelChoiceFilter(
        queryset=lambda request: None  # Set in __init__
    )
    supplier_name = django_filters.CharFilter(
        field_name='supplier__name',
        lookup_expr='icontains'
    )
    
    # Price range filters
    min_price = django_filters.NumberFilter(field_name='price', lookup_expr='gte')
    max_price = django_filters.NumberFilter(field_name='price', lookup_expr='lte')
    
    # Quantity range filters
    min_quantity = django_filters.NumberFilter(field_name='quantity', lookup_expr='gte')
    max_quantity = django_filters.NumberFilter(field_name='quantity', lookup_expr='lte')
    
    # Price type filter
    price_type = django_filters.MultipleChoiceFilter(choices=Price.PRICE_TYPES)
    
    # Date range filters
    date_from = django_filters.DateTimeFilter(field_name='time', lookup_expr='gte')
    date_to = django_filters.DateTimeFilter(field_name='time', lookup_expr='lte')
    
    # Validity filters
    valid_only = django_filters.BooleanFilter(method='filter_valid_only')
    
    # Currency filter
    currency = django_filters.CharFilter()
    
    # Confidence score filter
    min_confidence = django_filters.NumberFilter(
        field_name='confidence_score',
        lookup_expr='gte'
    )
    
    # Source filter
    source = django_filters.CharFilter(lookup_expr='icontains')
    
    class Meta:
        model = Price
        fields = [
            'material', 'material_code', 'material_category',
            'supplier', 'supplier_name',
            'min_price', 'max_price', 'min_quantity', 'max_quantity',
            'price_type', 'date_from', 'date_to', 'valid_only',
            'currency', 'min_confidence', 'source'
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request and hasattr(self.request, 'organization'):
            from apps.procurement.models import Supplier
            from apps.core.models import Category
            
            self.filters['material'].queryset = Material.objects.filter(
                organization=self.request.organization
            )
            self.filters['material_category'].queryset = Category.objects.filter(
                is_active=True
            )
            self.filters['supplier'].queryset = Supplier.objects.filter(
                organization=self.request.organization,
                status='active'
            )
    
    def filter_valid_only(self, queryset, name, value):
        """Filter only currently valid prices"""
        if not value:
            return queryset
        
        from django.utils import timezone
        today = timezone.now().date()
        
        return queryset.filter(
            Q(valid_from__isnull=True) | Q(valid_from__lte=today),
            Q(valid_to__isnull=True) | Q(valid_to__gte=today)
        )


class PriceBenchmarkFilter(django_filters.FilterSet):
    """Filter for PriceBenchmark model"""
    
    # Material filters
    material = django_filters.ModelChoiceFilter(
        queryset=lambda request: None  # Set in __init__
    )
    material_code = django_filters.CharFilter(
        field_name='material__code',
        lookup_expr='icontains'
    )
    material_category = django_filters.ModelChoiceFilter(
        field_name='material__category',
        queryset=lambda request: None  # Set in __init__
    )
    
    # Benchmark type filter
    benchmark_type = django_filters.MultipleChoiceFilter(
        choices=PriceBenchmark.BENCHMARK_TYPES
    )
    
    # Price range filters
    min_benchmark_price = django_filters.NumberFilter(
        field_name='benchmark_price',
        lookup_expr='gte'
    )
    max_benchmark_price = django_filters.NumberFilter(
        field_name='benchmark_price',
        lookup_expr='lte'
    )
    
    # Period filters
    period_from = django_filters.DateFilter(field_name='period_start', lookup_expr='gte')
    period_to = django_filters.DateFilter(field_name='period_end', lookup_expr='lte')
    recent_period = django_filters.NumberFilter(method='filter_recent_period')
    
    # Confidence filter
    min_confidence = django_filters.NumberFilter(
        field_name='confidence_level',
        lookup_expr='gte'
    )
    
    # Sample size filter
    min_sample_size = django_filters.NumberFilter(
        field_name='sample_size',
        lookup_expr='gte'
    )
    
    class Meta:
        model = PriceBenchmark
        fields = [
            'material', 'material_code', 'material_category',
            'benchmark_type', 'min_benchmark_price', 'max_benchmark_price',
            'period_from', 'period_to', 'recent_period',
            'min_confidence', 'min_sample_size'
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request and hasattr(self.request, 'organization'):
            from apps.core.models import Category
            
            self.filters['material'].queryset = Material.objects.filter(
                organization=self.request.organization
            )
            self.filters['material_category'].queryset = Category.objects.filter(
                is_active=True
            )
    
    def filter_recent_period(self, queryset, name, value):
        """Filter benchmarks from recent period (days)"""
        if not value:
            return queryset
        
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_date = timezone.now().date() - timedelta(days=int(value))
        return queryset.filter(period_end__gte=cutoff_date)


class PriceAlertFilter(django_filters.FilterSet):
    """Filter for PriceAlert model"""
    
    # Material filters
    material = django_filters.ModelChoiceFilter(
        queryset=lambda request: None  # Set in __init__
    )
    material_code = django_filters.CharFilter(
        field_name='material__code',
        lookup_expr='icontains'
    )
    
    # Alert type filter
    alert_type = django_filters.MultipleChoiceFilter(choices=PriceAlert.ALERT_TYPES)
    
    # Status filter
    status = django_filters.MultipleChoiceFilter(choices=PriceAlert.STATUS_CHOICES)
    
    # Condition filter
    condition_type = django_filters.MultipleChoiceFilter(
        choices=PriceAlert.CONDITION_TYPES
    )
    
    # Threshold range
    min_threshold = django_filters.NumberFilter(
        field_name='threshold_value',
        lookup_expr='gte'
    )
    max_threshold = django_filters.NumberFilter(
        field_name='threshold_value',
        lookup_expr='lte'
    )
    
    # Recently triggered filter
    recently_triggered = django_filters.NumberFilter(method='filter_recently_triggered')
    
    # Notification preferences
    email_enabled = django_filters.BooleanFilter(field_name='email_notification')
    push_enabled = django_filters.BooleanFilter(field_name='push_notification')
    
    class Meta:
        model = PriceAlert
        fields = [
            'material', 'material_code', 'alert_type', 'status', 'condition_type',
            'min_threshold', 'max_threshold', 'recently_triggered',
            'email_enabled', 'push_enabled'
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request and hasattr(self.request, 'organization'):
            self.filters['material'].queryset = Material.objects.filter(
                organization=self.request.organization
            )
    
    def filter_recently_triggered(self, queryset, name, value):
        """Filter alerts triggered within recent days"""
        if not value:
            return queryset
        
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=int(value))
        return queryset.filter(last_triggered__gte=cutoff_date)


# Custom filter widgets
class RangeWidget(forms.MultiWidget):
    """Widget for range inputs"""
    
    def __init__(self, attrs=None):
        widgets = (
            forms.NumberInput(attrs={'placeholder': 'Min'}),
            forms.NumberInput(attrs={'placeholder': 'Max'}),
        )
        super().__init__(widgets, attrs)
    
    def decompress(self, value):
        if value:
            return value.split(',')
        return [None, None]


class PriceRangeFilter(django_filters.Filter):
    """Custom filter for price ranges"""
    
    def filter(self, qs, value):
        if value:
            min_val, max_val = value.split(',')
            if min_val:
                qs = qs.filter(price__gte=float(min_val))
            if max_val:
                qs = qs.filter(price__lte=float(max_val))
        return qs