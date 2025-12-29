"""
Pricing and material models
"""
import uuid
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.postgres.indexes import GinIndex
from apps.core.models import TimestampedModel, Organization
from django.contrib.auth.models import User


class Category(TimestampedModel):
    """Material categories for organization"""
    
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='material_categories')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subcategories')
    
    # Metadata
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        db_table = 'pricing_categories'
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
        ordering = ['name']
        unique_together = [['organization', 'name']]


class Material(TimestampedModel):
    """Material/Product catalog"""
    
    MATERIAL_TYPES = [
        ('raw_material', 'Raw Material'),
        ('component', 'Component'),
        ('assembly', 'Assembly'),
        ('finished_good', 'Finished Good'),
        ('service', 'Service'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('discontinued', 'Discontinued'),
        ('development', 'In Development'),
    ]
    
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='materials')
    code = models.CharField(max_length=100, db_index=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    material_type = models.CharField(max_length=20, choices=MATERIAL_TYPES)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Physical properties
    unit_of_measure = models.CharField(max_length=50)
    weight = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    weight_unit = models.CharField(max_length=10, default='kg')
    dimensions = models.JSONField(default=dict, blank=True)  # length, width, height
    
    # Specifications and attributes
    specifications = models.JSONField(default=dict, blank=True)
    attributes = models.JSONField(default=dict, blank=True)
    
    # Status and lifecycle
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    lifecycle_stage = models.CharField(max_length=50, blank=True)
    
    # Pricing information
    list_price = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    cost_price = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    currency = models.CharField(max_length=3, default='USD')
    
    # Supply chain information
    lead_time_days = models.PositiveIntegerField(null=True, blank=True)
    minimum_order_quantity = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    
    # Images and documents
    primary_image = models.ImageField(upload_to='materials/', blank=True, null=True)
    drawings = models.JSONField(default=list, blank=True)  # List of file paths
    datasheets = models.JSONField(default=list, blank=True)  # List of file paths
    
    # Compliance and certifications
    certifications = models.JSONField(default=list, blank=True)
    compliance_standards = models.JSONField(default=list, blank=True)
    
    # Search and indexing
    search_keywords = models.TextField(blank=True)
    
    class Meta:
        db_table = 'materials'
        unique_together = ['organization', 'code']
        ordering = ['code']
        indexes = [
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['category', 'material_type']),
            models.Index(fields=['code']),
            GinIndex(fields=['specifications']),
            GinIndex(fields=['attributes']),
        ]
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    @property
    def current_price(self):
        """Get current market price"""
        latest_price = self.prices.filter(price_type='market').order_by('-time').first()
        return latest_price.price if latest_price else self.list_price
    
    def get_price_history(self, days=30, price_type=None):
        """Get price history for the material"""
        from django.utils import timezone
        from datetime import timedelta
        
        queryset = self.prices.filter(
            time__gte=timezone.now() - timedelta(days=days)
        ).order_by('-time')
        
        if price_type:
            queryset = queryset.filter(price_type=price_type)
        
        return queryset
    
    def calculate_should_cost(self):
        """Calculate should-cost based on specifications and market data"""
        # This would implement should-cost calculation logic
        # For now, return a placeholder
        return self.cost_price or Decimal('0.00')


class Price(models.Model):
    """Time-series pricing data (TimescaleDB hypertable)"""
    
    PRICE_TYPES = [
        ('quote', 'Quote Price'),
        ('contract', 'Contract Price'),
        ('market', 'Market Price'),
        ('predicted', 'ML Predicted Price'),
        ('should_cost', 'Should Cost'),
        ('benchmark', 'Benchmark Price'),
    ]
    
    # Primary fields
    time = models.DateTimeField(db_index=True)  # Partition key for TimescaleDB
    material = models.ForeignKey(Material, on_delete=models.CASCADE, related_name='prices')
    supplier = models.ForeignKey('procurement.Supplier', on_delete=models.CASCADE, null=True, blank=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    
    # Price information
    price = models.DecimalField(max_digits=15, decimal_places=4)
    currency = models.CharField(max_length=3, default='USD')
    quantity = models.DecimalField(max_digits=15, decimal_places=4, default=1)
    unit_of_measure = models.CharField(max_length=50)
    price_type = models.CharField(max_length=20, choices=PRICE_TYPES)
    
    # Validity period
    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)
    
    # Additional context
    source = models.CharField(max_length=100, blank=True)  # Data source
    confidence_score = models.DecimalField(
        max_digits=5, 
        decimal_places=4, 
        null=True, 
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(1)]
    )
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        db_table = 'prices'
        ordering = ['-time']
        indexes = [
            models.Index(fields=['material', '-time']),
            models.Index(fields=['supplier', '-time']),
            models.Index(fields=['organization', 'price_type', '-time']),
            models.Index(fields=['price_type', '-time']),
            models.Index(fields=['valid_from', 'valid_to']),
        ]
    
    def __str__(self):
        return f"{self.material.code} - {self.price} {self.currency} - {self.time}"
    
    @property
    def is_valid(self):
        """Check if price is currently valid"""
        from django.utils import timezone
        today = timezone.now().date()
        
        if self.valid_from and today < self.valid_from:
            return False
        if self.valid_to and today > self.valid_to:
            return False
        return True
    
    @property
    def unit_price(self):
        """Calculate unit price"""
        if self.quantity > 0:
            return self.price / self.quantity
        return self.price


class PriceBenchmark(TimestampedModel):
    """Price benchmarking data"""
    
    BENCHMARK_TYPES = [
        ('market_average', 'Market Average'),
        ('lowest_quote', 'Lowest Quote'),
        ('preferred_supplier', 'Preferred Supplier'),
        ('historical_average', 'Historical Average'),
        ('should_cost', 'Should Cost'),
    ]
    
    material = models.ForeignKey(Material, on_delete=models.CASCADE, related_name='benchmarks')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    benchmark_type = models.CharField(max_length=30, choices=BENCHMARK_TYPES)
    
    # Benchmark values
    benchmark_price = models.DecimalField(max_digits=15, decimal_places=4)
    currency = models.CharField(max_length=3, default='USD')
    quantity = models.DecimalField(max_digits=15, decimal_places=4, default=1)
    
    # Period information
    period_start = models.DateField()
    period_end = models.DateField()
    
    # Statistics
    sample_size = models.PositiveIntegerField(default=1)
    min_price = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    max_price = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    std_deviation = models.DecimalField(max_digits=15, decimal_places=8, null=True, blank=True)
    
    # Metadata
    calculation_method = models.TextField(blank=True)
    data_sources = models.JSONField(default=list, blank=True)
    confidence_level = models.DecimalField(
        max_digits=5, 
        decimal_places=4, 
        null=True, 
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(1)]
    )
    
    class Meta:
        db_table = 'price_benchmarks'
        unique_together = ['material', 'organization', 'benchmark_type', 'period_start', 'period_end']
        ordering = ['-period_end']
        indexes = [
            models.Index(fields=['material', 'benchmark_type', '-period_end']),
            models.Index(fields=['organization', '-period_end']),
        ]
    
    def __str__(self):
        return f"{self.material.code} - {self.benchmark_type} - {self.benchmark_price}"


class PricePrediction(TimestampedModel):
    """ML-based price predictions"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='price_predictions')
    material = models.ForeignKey(Material, on_delete=models.CASCADE, related_name='predictions')
    
    # Prediction details
    predicted_price = models.DecimalField(max_digits=12, decimal_places=4)
    confidence_interval = models.JSONField(default=dict)  # {'lower': x, 'upper': y}
    prediction_horizon_days = models.IntegerField(default=30)
    
    # Model information
    model_version = models.CharField(max_length=50)
    model_confidence = models.FloatField(validators=[MinValueValidator(0), MaxValueValidator(1)])
    accuracy_score = models.FloatField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Metadata
    prediction_date = models.DateTimeField(auto_now_add=True)
    features_used = models.JSONField(default=list)
    
    def __str__(self):
        return f"{self.material.name} - {self.predicted_price} ({self.prediction_horizon_days} days)"
    
    class Meta:
        db_table = 'pricing_predictions'
        verbose_name = 'Price Prediction'
        verbose_name_plural = 'Price Predictions'
        ordering = ['-created_at']


class PriceAlert(TimestampedModel):
    """Price alerts and notifications"""
    
    ALERT_TYPES = [
        ('threshold', 'Price Threshold'),
        ('anomaly', 'Price Anomaly'),
        ('trend', 'Price Trend'),
        ('forecast', 'Price Forecast'),
    ]
    
    CONDITION_TYPES = [
        ('above', 'Above'),
        ('below', 'Below'),
        ('change_percent', 'Change Percentage'),
        ('change_absolute', 'Change Absolute'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('triggered', 'Triggered'),
        ('resolved', 'Resolved'),
        ('disabled', 'Disabled'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='price_alerts')
    material = models.ForeignKey(Material, on_delete=models.CASCADE, related_name='price_alerts')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    
    # Alert configuration
    name = models.CharField(max_length=255)
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    condition_type = models.CharField(max_length=20, choices=CONDITION_TYPES)
    threshold_value = models.DecimalField(max_digits=15, decimal_places=4)
    
    # Status and tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    last_triggered = models.DateTimeField(null=True, blank=True)
    trigger_count = models.PositiveIntegerField(default=0)
    
    # Notification settings
    email_notification = models.BooleanField(default=True)
    push_notification = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'price_alerts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['material', 'status']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.material.code}"
    
    def check_condition(self, current_price):
        """Check if alert condition is met"""
        if self.condition_type == 'above':
            return current_price > self.threshold_value
        elif self.condition_type == 'below':
            return current_price < self.threshold_value
        # Add more condition logic as needed
        return False
    
    def trigger_alert(self):
        """Trigger the alert"""
        from django.utils import timezone
        self.status = 'triggered'
        self.last_triggered = timezone.now()
        self.trigger_count += 1
        self.save()
        
        # Send notification (implement notification logic)
        self.send_notification()
    
    def send_notification(self):
        """Send alert notification"""
        # Implement notification sending logic
        pass


class CostModel(TimestampedModel):
    """Cost models for should-cost calculations"""
    
    MODEL_TYPES = [
        ('parametric', 'Parametric Model'),
        ('bottom_up', 'Bottom-up Model'),
        ('regression', 'Regression Model'),
        ('ml_based', 'ML-based Model'),
    ]
    
    material = models.ForeignKey(Material, on_delete=models.CASCADE, related_name='cost_models')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    
    # Model information
    name = models.CharField(max_length=255)
    model_type = models.CharField(max_length=20, choices=MODEL_TYPES)
    version = models.CharField(max_length=50, default='1.0')
    
    # Model parameters
    parameters = models.JSONField(default=dict)
    cost_drivers = models.JSONField(default=list)  # List of cost driver definitions
    
    # Model performance
    accuracy_score = models.DecimalField(
        max_digits=5, 
        decimal_places=4, 
        null=True, 
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(1)]
    )
    r_squared = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    mean_absolute_error = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    
    # Model status
    is_active = models.BooleanField(default=True)
    last_trained = models.DateTimeField(null=True, blank=True)
    training_data_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'cost_models'
        unique_together = ['material', 'name', 'version']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.material.code} - {self.name} v{self.version}"
    
    def calculate_should_cost(self, inputs):
        """Calculate should cost based on model"""
        # Implement should-cost calculation logic based on model type
        if self.model_type == 'parametric':
            return self._calculate_parametric_cost(inputs)
        elif self.model_type == 'bottom_up':
            return self._calculate_bottom_up_cost(inputs)
        # Add other model types
        return Decimal('0.00')
    
    def _calculate_parametric_cost(self, inputs):
        """Calculate cost using parametric model"""
        # Implement parametric cost calculation
        base_cost = self.parameters.get('base_cost', 0)
        # Add more calculation logic
        return Decimal(str(base_cost))
    
    def _calculate_bottom_up_cost(self, inputs):
        """Calculate cost using bottom-up approach"""
        # Implement bottom-up cost calculation
        total_cost = Decimal('0.00')
        for driver in self.cost_drivers:
            driver_cost = self._calculate_driver_cost(driver, inputs)
            total_cost += driver_cost
        return total_cost
    
    def _calculate_driver_cost(self, driver, inputs):
        """Calculate cost for a specific cost driver"""
        # Implement cost driver calculation
        return Decimal('0.00')


class PriceHistory(TimestampedModel):
    """Historical price tracking for materials"""
    
    CHANGE_TYPES = [
        ('increase', 'Price Increase'),
        ('decrease', 'Price Decrease'),
        ('stable', 'No Change'),
        ('new', 'New Price'),
    ]
    
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='price_history')
    material = models.ForeignKey(Material, on_delete=models.CASCADE, related_name='price_history')
    
    # Price information
    price = models.DecimalField(max_digits=12, decimal_places=4)
    currency = models.CharField(max_length=3, default='USD')
    source = models.CharField(max_length=100)
    
    # Change tracking
    previous_price = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    price_change = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    change_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    change_type = models.CharField(max_length=10, choices=CHANGE_TYPES, default='new')
    
    # Metadata
    notes = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.material.name} - {self.price} {self.currency} ({self.created_at})"
    
    def save(self, *args, **kwargs):
        """Calculate price changes before saving"""
        if self.previous_price:
            self.price_change = self.price - self.previous_price
            if self.previous_price > 0:
                self.change_percentage = (self.price_change / self.previous_price) * 100
                
            # Determine change type
            if self.price_change > 0:
                self.change_type = 'increase'
            elif self.price_change < 0:
                self.change_type = 'decrease'
            else:
                self.change_type = 'stable'
        else:
            self.change_type = 'new'
            
        super().save(*args, **kwargs)
    
    class Meta:
        db_table = 'pricing_price_history'
        verbose_name = 'Price History'
        verbose_name_plural = 'Price History'
        ordering = ['-created_at']