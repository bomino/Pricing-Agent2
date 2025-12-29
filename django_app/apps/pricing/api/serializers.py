"""
Serializers for pricing API endpoints
"""
from decimal import Decimal
from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.pricing.models import (
    Material,
    Price,
    PriceBenchmark,
    PriceAlert,
    PricePrediction,
    PriceHistory,
    CostModel,
    Category,
)
from apps.core.models import Category, Organization
from apps.accounts.models import User


class CategorySerializer(serializers.ModelSerializer):
    """Serializer for Category model"""
    
    parent_name = serializers.CharField(source='parent.name', read_only=True)
    children_count = serializers.SerializerMethodField()
    full_path = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = [
            'id', 'name', 'code', 'description', 'parent', 'parent_name',
            'level', 'is_active', 'metadata', 'children_count', 'full_path',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'level', 'created_at', 'updated_at']
    
    def get_children_count(self, obj):
        return obj.children.count()
    
    def get_full_path(self, obj):
        return obj.get_full_path()


class MaterialListSerializer(serializers.ModelSerializer):
    """Serializer for Material list view"""
    
    category_name = serializers.CharField(source='category.name', read_only=True)
    current_price = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = Material
        fields = [
            'id', 'code', 'name', 'material_type', 'category', 'category_name',
            'unit_of_measure', 'status', 'status_display', 'list_price',
            'current_price', 'currency', 'lead_time_days', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_current_price(self, obj):
        current = obj.current_price
        return str(current) if current else None


class MaterialDetailSerializer(serializers.ModelSerializer):
    """Serializer for Material detail view"""
    
    category_name = serializers.CharField(source='category.name', read_only=True)
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    current_price = serializers.SerializerMethodField()
    price_history = serializers.SerializerMethodField()
    
    class Meta:
        model = Material
        fields = [
            'id', 'organization', 'organization_name', 'code', 'name', 'description',
            'material_type', 'category', 'category_name', 'unit_of_measure',
            'weight', 'weight_unit', 'dimensions', 'specifications', 'attributes',
            'status', 'lifecycle_stage', 'list_price', 'cost_price', 'current_price',
            'currency', 'lead_time_days', 'minimum_order_quantity', 'primary_image',
            'drawings', 'datasheets', 'certifications', 'compliance_standards',
            'search_keywords', 'price_history', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'organization', 'current_price', 'price_history', 'created_at', 'updated_at']
    
    def get_current_price(self, obj):
        current = obj.current_price
        return str(current) if current else None
    
    def get_price_history(self, obj):
        recent_prices = obj.get_price_history(days=30)[:10]
        return PriceHistorySerializer(recent_prices, many=True).data
    
    def validate_code(self, value):
        """Validate material code uniqueness within organization"""
        organization = self.context['request'].organization
        queryset = Material.objects.filter(organization=organization, code=value)
        
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        
        if queryset.exists():
            raise serializers.ValidationError(
                "Material with this code already exists in your organization"
            )
        
        return value


class PriceHistorySerializer(serializers.ModelSerializer):
    """Serializer for price history"""
    
    material_code = serializers.CharField(source='material.code', read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    unit_price = serializers.SerializerMethodField()
    
    class Meta:
        model = Price
        fields = [
            'id', 'time', 'material', 'material_code', 'supplier', 'supplier_name',
            'price', 'unit_price', 'currency', 'quantity', 'unit_of_measure',
            'price_type', 'valid_from', 'valid_to', 'source', 'confidence_score'
        ]
        read_only_fields = ['id', 'unit_price']
    
    def get_unit_price(self, obj):
        return str(obj.unit_price)


class PriceCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating price records"""
    
    class Meta:
        model = Price
        fields = [
            'material', 'supplier', 'price', 'currency', 'quantity',
            'unit_of_measure', 'price_type', 'valid_from', 'valid_to',
            'source', 'confidence_score', 'metadata'
        ]
    
    def validate(self, attrs):
        """Validate price data"""
        if attrs.get('quantity', 0) <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero")
        
        if attrs.get('price', 0) <= 0:
            raise serializers.ValidationError("Price must be greater than zero")
        
        # Validate date range
        valid_from = attrs.get('valid_from')
        valid_to = attrs.get('valid_to')
        if valid_from and valid_to and valid_from >= valid_to:
            raise serializers.ValidationError("Valid from date must be before valid to date")
        
        return attrs
    
    def create(self, validated_data):
        """Create price with organization and user context"""
        validated_data['organization'] = self.context['request'].organization
        validated_data['created_by'] = self.context['request'].user
        validated_data['time'] = validated_data.get('time') or timezone.now()
        return super().create(validated_data)


class PriceBenchmarkSerializer(serializers.ModelSerializer):
    """Serializer for price benchmarks"""
    
    material_code = serializers.CharField(source='material.code', read_only=True)
    material_name = serializers.CharField(source='material.name', read_only=True)
    benchmark_type_display = serializers.CharField(source='get_benchmark_type_display', read_only=True)
    
    class Meta:
        model = PriceBenchmark
        fields = [
            'id', 'material', 'material_code', 'material_name', 'benchmark_type',
            'benchmark_type_display', 'benchmark_price', 'currency', 'quantity',
            'period_start', 'period_end', 'sample_size', 'min_price', 'max_price',
            'std_deviation', 'calculation_method', 'data_sources', 'confidence_level',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'organization', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        validated_data['organization'] = self.context['request'].organization
        return super().create(validated_data)


class PriceAlertSerializer(serializers.ModelSerializer):
    """Serializer for price alerts"""
    
    material_code = serializers.CharField(source='material.code', read_only=True)
    material_name = serializers.CharField(source='material.name', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = PriceAlert
        fields = [
            'id', 'user', 'user_name', 'material', 'material_code', 'material_name',
            'name', 'alert_type', 'condition_type', 'threshold_value', 'status',
            'last_triggered', 'trigger_count', 'email_notification', 'push_notification',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'organization', 'last_triggered', 'trigger_count', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        validated_data['organization'] = self.context['request'].organization
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class CostModelSerializer(serializers.ModelSerializer):
    """Serializer for cost models"""
    
    material_code = serializers.CharField(source='material.code', read_only=True)
    material_name = serializers.CharField(source='material.name', read_only=True)
    
    class Meta:
        model = CostModel
        fields = [
            'id', 'material', 'material_code', 'material_name', 'name',
            'model_type', 'version', 'parameters', 'cost_drivers',
            'accuracy_score', 'r_squared', 'mean_absolute_error',
            'is_active', 'last_trained', 'training_data_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'organization', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        validated_data['organization'] = self.context['request'].organization
        return super().create(validated_data)


# ML Integration Serializers
class PricePredictionRequestSerializer(serializers.Serializer):
    """Serializer for ML price prediction requests"""
    
    material_id = serializers.CharField()
    quantity = serializers.DecimalField(max_digits=15, decimal_places=4, min_value=0.0001)
    unit_of_measure = serializers.CharField(max_length=50)
    supplier_id = serializers.CharField(required=False, allow_blank=True)
    delivery_date = serializers.DateField(required=False)
    region = serializers.CharField(max_length=100, required=False, allow_blank=True)
    payment_terms = serializers.CharField(max_length=100, required=False, allow_blank=True)
    specifications = serializers.JSONField(required=False, default=dict)
    context = serializers.JSONField(required=False, default=dict)
    
    def validate_material_id(self, value):
        """Validate material exists and user has access"""
        try:
            organization = self.context['request'].organization
            material = Material.objects.get(id=value, organization=organization)
            return str(material.id)
        except Material.DoesNotExist:
            raise serializers.ValidationError("Material not found or access denied")


class BatchPredictionRequestSerializer(serializers.Serializer):
    """Serializer for batch prediction requests"""
    
    predictions = PricePredictionRequestSerializer(many=True)
    async_processing = serializers.BooleanField(default=False)
    callback_url = serializers.URLField(required=False, allow_blank=True)
    
    def validate_predictions(self, value):
        """Validate predictions list"""
        if not value:
            raise serializers.ValidationError("Predictions list cannot be empty")
        
        if len(value) > 1000:
            raise serializers.ValidationError("Maximum 1000 predictions per batch")
        
        return value


class AnomalyDetectionRequestSerializer(serializers.Serializer):
    """Serializer for anomaly detection requests"""
    
    prices = serializers.ListField(
        child=serializers.JSONField(),
        min_length=1,
        max_length=10000
    )
    sensitivity = serializers.FloatField(min_value=0.01, max_value=0.5, default=0.1)
    include_explanations = serializers.BooleanField(default=True)


class TrendAnalysisRequestSerializer(serializers.Serializer):
    """Serializer for trend analysis requests"""
    
    material_id = serializers.CharField()
    period_days = serializers.IntegerField(min_value=7, max_value=365, default=90)
    include_forecast = serializers.BooleanField(default=False)
    forecast_days = serializers.IntegerField(min_value=1, max_value=90, default=30)
    
    def validate_material_id(self, value):
        """Validate material exists and user has access"""
        try:
            organization = self.context['request'].organization
            material = Material.objects.get(id=value, organization=organization)
            return str(material.id)
        except Material.DoesNotExist:
            raise serializers.ValidationError("Material not found or access denied")


# HTMX Serializers for partial templates
class MaterialHTMXSerializer(serializers.ModelSerializer):
    """Simplified serializer for HTMX responses"""
    
    category_name = serializers.CharField(source='category.name', read_only=True)
    current_price = serializers.SerializerMethodField()
    
    class Meta:
        model = Material
        fields = [
            'id', 'code', 'name', 'category_name', 'unit_of_measure',
            'status', 'current_price', 'currency', 'updated_at'
        ]
    
    def get_current_price(self, obj):
        current = obj.current_price
        return float(current) if current else None


class PriceChartDataSerializer(serializers.Serializer):
    """Serializer for price chart data"""
    
    date = serializers.DateTimeField()
    price = serializers.DecimalField(max_digits=15, decimal_places=4)
    supplier = serializers.CharField(allow_blank=True)
    price_type = serializers.CharField()
    
    class Meta:
        fields = ['date', 'price', 'supplier', 'price_type']


class PricePredictionSerializer(serializers.ModelSerializer):
    """Serializer for PricePrediction model"""
    
    material_code = serializers.CharField(source='material.code', read_only=True)
    material_name = serializers.CharField(source='material.name', read_only=True)
    
    class Meta:
        model = PricePrediction
        fields = [
            'id', 'material', 'material_code', 'material_name',
            'predicted_price', 'confidence_interval', 'prediction_horizon_days',
            'model_version', 'model_confidence', 'accuracy_score',
            'status', 'prediction_date', 'features_used',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'organization', 'prediction_date', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        validated_data['organization'] = self.context['request'].user.profile.organization
        return super().create(validated_data)


class PriceHistoryDetailSerializer(serializers.ModelSerializer):
    """Serializer for PriceHistory model"""
    
    material_code = serializers.CharField(source='material.code', read_only=True)
    material_name = serializers.CharField(source='material.name', read_only=True)
    
    class Meta:
        model = PriceHistory
        fields = [
            'id', 'material', 'material_code', 'material_name',
            'price', 'currency', 'source', 'previous_price',
            'price_change', 'change_percentage', 'change_type',
            'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'organization', 'price_change', 'change_percentage',
            'change_type', 'created_at', 'updated_at'
        ]
    
    def create(self, validated_data):
        validated_data['organization'] = self.context['request'].user.profile.organization
        return super().create(validated_data)


class MaterialAnalyticsSerializer(serializers.Serializer):
    """Serializer for material analytics"""
    
    material = MaterialListSerializer()
    price_statistics = serializers.JSONField()
    trend_analysis = serializers.JSONField()
    supplier_analysis = serializers.JSONField()
    risk_assessment = serializers.JSONField()


class PricingStatsSerializer(serializers.Serializer):
    """Serializer for pricing statistics"""
    
    total_materials = serializers.IntegerField()
    active_materials = serializers.IntegerField()
    total_prices = serializers.IntegerField()
    unique_suppliers = serializers.IntegerField()
    
    # Price statistics
    average_price = serializers.DecimalField(max_digits=15, decimal_places=4)
    price_volatility = serializers.DecimalField(max_digits=5, decimal_places=2)
    
    # Trend data
    price_trends = serializers.JSONField()
    category_distribution = serializers.JSONField()
    supplier_distribution = serializers.JSONField()
    
    # Recent activity
    recent_price_updates = serializers.IntegerField()
    recent_predictions = serializers.IntegerField()
    recent_alerts = serializers.IntegerField()


class MarketIntelligenceSerializer(serializers.Serializer):
    """Serializer for market intelligence data"""
    
    material = MaterialListSerializer()
    market_price = serializers.DecimalField(max_digits=15, decimal_places=4)
    price_trend = serializers.CharField()  # up, down, stable
    volatility_score = serializers.DecimalField(max_digits=5, decimal_places=2)
    supplier_competition = serializers.JSONField()
    risk_factors = serializers.JSONField()
    recommendations = serializers.JSONField()


class PriceOptimizationSerializer(serializers.Serializer):
    """Serializer for price optimization recommendations"""
    
    material = MaterialListSerializer()
    current_price = serializers.DecimalField(max_digits=15, decimal_places=4)
    optimal_price = serializers.DecimalField(max_digits=15, decimal_places=4)
    savings_potential = serializers.DecimalField(max_digits=15, decimal_places=4)
    savings_percentage = serializers.DecimalField(max_digits=5, decimal_places=2)
    recommended_actions = serializers.JSONField()
    implementation_timeline = serializers.JSONField()