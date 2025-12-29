"""
Procurement API serializers
"""
from rest_framework import serializers
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth.models import User
from apps.procurement.models import (
    Supplier, RFQ, Quote, RFQItem, QuoteItem, Contract,
    SupplierContact, SupplierDocument
)
from apps.pricing.models import Material
from apps.core.models import Organization
from apps.accounts.api.serializers import UserSerializer


class SupplierSerializer(serializers.ModelSerializer):
    """Serializer for Supplier model"""
    
    performance_score = serializers.SerializerMethodField()
    recent_quotes_count = serializers.SerializerMethodField()
    active_contracts_count = serializers.SerializerMethodField()
    primary_contact = serializers.SerializerMethodField()
    
    class Meta:
        model = Supplier
        fields = [
            'id', 'name', 'code', 'supplier_type', 'website',
            'primary_contact_name', 'primary_contact_email', 'primary_contact_phone',
            'address', 'country', 'region', 'tax_id', 'business_registration',
            'legal_name', 'payment_terms', 'currency', 'credit_limit',
            'rating', 'on_time_delivery_rate', 'quality_score',
            'risk_level', 'certifications', 'compliance_documents',
            'status', 'approved_by', 'approved_at', 'categories',
            'capabilities', 'notes', 'tags', 'created_at', 'updated_at',
            'performance_score', 'recent_quotes_count', 'active_contracts_count',
            'primary_contact'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'performance_score',
            'recent_quotes_count', 'active_contracts_count', 'primary_contact'
        ]
    
    def get_performance_score(self, obj):
        """Calculate overall performance score"""
        return obj.calculate_performance_score()
    
    def get_recent_quotes_count(self, obj):
        """Get count of recent quotes (last 90 days)"""
        return obj.get_recent_quotes().count()
    
    def get_active_contracts_count(self, obj):
        """Get count of active contracts"""
        return obj.contracts.filter(status='active').count()
    
    def get_primary_contact(self, obj):
        """Get primary contact information"""
        primary_contact = obj.contacts.filter(is_primary=True, is_active=True).first()
        if primary_contact:
            return SupplierContactSerializer(primary_contact).data
        return None


class SupplierListSerializer(serializers.ModelSerializer):
    """Minimal serializer for supplier lists"""
    
    performance_score = serializers.SerializerMethodField()
    
    class Meta:
        model = Supplier
        fields = [
            'id', 'name', 'code', 'supplier_type', 'country',
            'rating', 'status', 'performance_score'
        ]
    
    def get_performance_score(self, obj):
        """Calculate overall performance score"""
        return obj.calculate_performance_score()


class SupplierDetailSerializer(SupplierSerializer):
    """Detailed serializer for supplier details"""
    
    contacts = serializers.SerializerMethodField()
    documents = serializers.SerializerMethodField()
    recent_quotes = serializers.SerializerMethodField()
    
    class Meta(SupplierSerializer.Meta):
        fields = SupplierSerializer.Meta.fields + [
            'contacts', 'documents', 'recent_quotes'
        ]
    
    def get_contacts(self, obj):
        """Get supplier contacts"""
        contacts = obj.contacts.filter(is_active=True)
        return SupplierContactSerializer(contacts, many=True).data
    
    def get_documents(self, obj):
        """Get supplier documents"""
        documents = obj.documents.all()[:10]  # Limit to recent 10
        return SupplierDocumentSerializer(documents, many=True).data
    
    def get_recent_quotes(self, obj):
        """Get recent quotes from this supplier"""
        quotes = obj.get_recent_quotes()[:5]  # Limit to recent 5
        return QuoteListSerializer(quotes, many=True).data


class SupplierContactSerializer(serializers.ModelSerializer):
    """Serializer for SupplierContact model"""
    
    class Meta:
        model = SupplierContact
        fields = [
            'id', 'name', 'email', 'phone', 'role', 'department',
            'is_primary', 'is_active', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class SupplierDocumentSerializer(serializers.ModelSerializer):
    """Serializer for SupplierDocument model"""
    
    uploaded_by = UserSerializer(read_only=True)
    is_expired = serializers.SerializerMethodField()
    
    class Meta:
        model = SupplierDocument
        fields = [
            'id', 'document_type', 'document', 'description',
            'valid_from', 'valid_until', 'uploaded_by', 'uploaded_at',
            'is_expired'
        ]
        read_only_fields = ['id', 'uploaded_by', 'uploaded_at', 'is_expired']
    
    def get_is_expired(self, obj):
        """Check if document is expired"""
        if obj.valid_until:
            return timezone.now().date() > obj.valid_until
        return False


class MaterialSerializer(serializers.ModelSerializer):
    """Serializer for Material model (for RFQ items)"""
    
    class Meta:
        model = Material
        fields = ['id', 'code', 'name', 'description', 'unit_of_measure', 'current_price']
        read_only_fields = ['id', 'current_price']


class RFQItemSerializer(serializers.ModelSerializer):
    """Serializer for RFQItem model"""
    
    material = MaterialSerializer(read_only=True)
    material_id = serializers.UUIDField(write_only=True)
    
    class Meta:
        model = RFQItem
        fields = [
            'id', 'material', 'material_id', 'quantity', 'unit_of_measure',
            'specifications', 'notes', 'required_delivery_date',
            'delivery_location', 'budget_estimate', 'last_purchase_price',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'material', 'created_at', 'updated_at']
    
    def validate_material_id(self, value):
        """Validate material exists"""
        try:
            Material.objects.get(id=value)
            return value
        except Material.DoesNotExist:
            raise serializers.ValidationError("Material not found")


class RFQSerializer(serializers.ModelSerializer):
    """Serializer for RFQ model"""
    
    created_by = UserSerializer(read_only=True)
    invited_suppliers = SupplierListSerializer(many=True, read_only=True)
    invited_supplier_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False
    )
    items = RFQItemSerializer(many=True, read_only=True)
    quotes_count = serializers.SerializerMethodField()
    days_remaining = serializers.SerializerMethodField()
    
    class Meta:
        model = RFQ
        fields = [
            'id', 'rfq_number', 'title', 'description', 'created_by',
            'department', 'cost_center', 'deadline', 'required_delivery_date',
            'status', 'priority', 'invited_suppliers', 'invited_supplier_ids',
            'public_rfq', 'terms_and_conditions', 'payment_terms',
            'delivery_terms', 'evaluation_criteria', 'attachments',
            'published_at', 'closed_at', 'awarded_quote', 'items',
            'quotes_count', 'days_remaining', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'rfq_number', 'created_by', 'published_at', 'closed_at',
            'awarded_quote', 'items', 'quotes_count', 'days_remaining',
            'created_at', 'updated_at'
        ]
    
    def get_quotes_count(self, obj):
        """Get number of quotes received"""
        return obj.quotes.count()
    
    def get_days_remaining(self, obj):
        """Get days remaining until deadline"""
        return obj.days_remaining
    
    def create(self, validated_data):
        """Create RFQ with invited suppliers"""
        invited_supplier_ids = validated_data.pop('invited_supplier_ids', [])
        validated_data['created_by'] = self.context['request'].user
        
        # Auto-generate RFQ number
        from datetime import datetime
        validated_data['rfq_number'] = f"RFQ-{datetime.now().strftime('%Y%m%d')}-{timezone.now().microsecond}"
        
        rfq = RFQ.objects.create(**validated_data)
        
        # Add invited suppliers
        if invited_supplier_ids:
            suppliers = Supplier.objects.filter(id__in=invited_supplier_ids)
            rfq.invited_suppliers.set(suppliers)
        
        return rfq
    
    def update(self, instance, validated_data):
        """Update RFQ with invited suppliers"""
        invited_supplier_ids = validated_data.pop('invited_supplier_ids', None)
        
        instance = super().update(instance, validated_data)
        
        if invited_supplier_ids is not None:
            suppliers = Supplier.objects.filter(id__in=invited_supplier_ids)
            instance.invited_suppliers.set(suppliers)
        
        return instance


class RFQListSerializer(serializers.ModelSerializer):
    """Minimal serializer for RFQ lists"""
    
    created_by = UserSerializer(read_only=True)
    quotes_count = serializers.SerializerMethodField()
    days_remaining = serializers.SerializerMethodField()
    
    class Meta:
        model = RFQ
        fields = [
            'id', 'rfq_number', 'title', 'status', 'priority',
            'deadline', 'created_by', 'quotes_count', 'days_remaining',
            'created_at'
        ]
    
    def get_quotes_count(self, obj):
        """Get number of quotes received"""
        return obj.quotes.count()
    
    def get_days_remaining(self, obj):
        """Get days remaining until deadline"""
        return obj.days_remaining


class QuoteItemSerializer(serializers.ModelSerializer):
    """Serializer for QuoteItem model"""
    
    material = MaterialSerializer(read_only=True)
    rfq_item = RFQItemSerializer(read_only=True)
    
    class Meta:
        model = QuoteItem
        fields = [
            'id', 'material', 'rfq_item', 'price', 'unit_price',
            'currency', 'quantity', 'unit_of_measure', 'lead_time_days',
            'delivery_date', 'specifications', 'alternative_offered',
            'alternative_description', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'material', 'rfq_item', 'unit_price', 
            'created_at', 'updated_at'
        ]


class QuoteSerializer(serializers.ModelSerializer):
    """Serializer for Quote model"""
    
    supplier = SupplierListSerializer(read_only=True)
    rfq = RFQListSerializer(read_only=True)
    items = QuoteItemSerializer(many=True, read_only=True)
    evaluated_by = UserSerializer(read_only=True)
    days_until_expiry = serializers.SerializerMethodField()
    
    class Meta:
        model = Quote
        fields = [
            'id', 'quote_number', 'reference_number', 'supplier', 'rfq',
            'total_amount', 'currency', 'tax_amount', 'validity_period',
            'payment_terms', 'delivery_terms', 'lead_time_days',
            'status', 'submitted_at', 'expires_at', 'technical_score',
            'commercial_score', 'overall_score', 'supplier_notes',
            'internal_notes', 'rejection_reason', 'attachments',
            'evaluated_by', 'evaluated_at', 'items', 'days_until_expiry',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'supplier', 'rfq', 'submitted_at', 'expires_at',
            'evaluated_by', 'evaluated_at', 'items', 'days_until_expiry',
            'created_at', 'updated_at'
        ]
    
    def get_days_until_expiry(self, obj):
        """Get days until quote expires"""
        return obj.days_until_expiry


class QuoteListSerializer(serializers.ModelSerializer):
    """Minimal serializer for quote lists"""
    
    supplier = SupplierListSerializer(read_only=True)
    rfq = RFQListSerializer(read_only=True)
    days_until_expiry = serializers.SerializerMethodField()
    
    class Meta:
        model = Quote
        fields = [
            'id', 'quote_number', 'supplier', 'rfq', 'total_amount',
            'currency', 'status', 'overall_score', 'submitted_at',
            'expires_at', 'days_until_expiry'
        ]
    
    def get_days_until_expiry(self, obj):
        """Get days until quote expires"""
        return obj.days_until_expiry


class QuoteCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating quotes"""
    
    items_data = serializers.ListField(write_only=True)
    
    class Meta:
        model = Quote
        fields = [
            'quote_number', 'reference_number', 'total_amount', 'currency',
            'tax_amount', 'validity_period', 'payment_terms', 'delivery_terms',
            'lead_time_days', 'supplier_notes', 'attachments', 'items_data'
        ]
    
    def validate_items_data(self, value):
        """Validate quote items data"""
        if not value:
            raise serializers.ValidationError("At least one item is required")
        
        for item in value:
            if 'rfq_item_id' not in item:
                raise serializers.ValidationError("RFQ item ID is required for each item")
            if 'price' not in item:
                raise serializers.ValidationError("Price is required for each item")
            if 'quantity' not in item:
                raise serializers.ValidationError("Quantity is required for each item")
        
        return value
    
    def create(self, validated_data):
        """Create quote with items"""
        items_data = validated_data.pop('items_data')
        
        # Get RFQ and supplier from context
        rfq = self.context['rfq']
        supplier = self.context['supplier']
        
        quote = Quote.objects.create(
            rfq=rfq,
            supplier=supplier,
            organization=rfq.organization,
            **validated_data
        )
        
        # Create quote items
        for item_data in items_data:
            rfq_item_id = item_data.pop('rfq_item_id')
            rfq_item = RFQItem.objects.get(id=rfq_item_id, rfq=rfq)
            
            QuoteItem.objects.create(
                quote=quote,
                rfq_item=rfq_item,
                material=rfq_item.material,
                **item_data
            )
        
        return quote


class ContractSerializer(serializers.ModelSerializer):
    """Serializer for Contract model"""
    
    supplier = SupplierListSerializer(read_only=True)
    quote = QuoteListSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)
    approved_by = UserSerializer(read_only=True)
    days_until_expiry = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()
    
    class Meta:
        model = Contract
        fields = [
            'id', 'contract_number', 'title', 'contract_type', 'supplier',
            'quote', 'total_value', 'currency', 'payment_terms',
            'start_date', 'end_date', 'status', 'created_by',
            'approved_by', 'approved_at', 'contract_document',
            'attachments', 'terms_and_conditions', 'special_terms',
            'days_until_expiry', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'contract_number', 'supplier', 'quote', 'created_by',
            'approved_by', 'approved_at', 'days_until_expiry', 'is_active',
            'created_at', 'updated_at'
        ]
    
    def get_days_until_expiry(self, obj):
        """Get days until contract expires"""
        return obj.days_until_expiry
    
    def get_is_active(self, obj):
        """Check if contract is currently active"""
        return obj.is_active


class ContractListSerializer(serializers.ModelSerializer):
    """Minimal serializer for contract lists"""
    
    supplier = SupplierListSerializer(read_only=True)
    days_until_expiry = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()
    
    class Meta:
        model = Contract
        fields = [
            'id', 'contract_number', 'title', 'contract_type',
            'supplier', 'total_value', 'currency', 'status',
            'start_date', 'end_date', 'days_until_expiry',
            'is_active'
        ]
    
    def get_days_until_expiry(self, obj):
        """Get days until contract expires"""
        return obj.days_until_expiry
    
    def get_is_active(self, obj):
        """Check if contract is currently active"""
        return obj.is_active


class ProcurementStatsSerializer(serializers.Serializer):
    """Serializer for procurement statistics"""
    
    total_suppliers = serializers.IntegerField()
    active_suppliers = serializers.IntegerField()
    total_rfqs = serializers.IntegerField()
    open_rfqs = serializers.IntegerField()
    total_quotes = serializers.IntegerField()
    pending_quotes = serializers.IntegerField()
    total_contracts = serializers.IntegerField()
    active_contracts = serializers.IntegerField()
    
    # Value statistics
    total_contract_value = serializers.DecimalField(max_digits=15, decimal_places=2)
    average_quote_value = serializers.DecimalField(max_digits=15, decimal_places=2)
    
    # Performance metrics
    average_supplier_rating = serializers.DecimalField(max_digits=3, decimal_places=2)
    average_response_time = serializers.FloatField()  # days
    
    # Trend data
    suppliers_by_country = serializers.DictField()
    rfqs_by_status = serializers.DictField()
    quotes_by_status = serializers.DictField()
    contracts_by_type = serializers.DictField()


class SupplierPerformanceSerializer(serializers.Serializer):
    """Serializer for supplier performance metrics"""
    
    supplier = SupplierListSerializer()
    performance_score = serializers.DecimalField(max_digits=5, decimal_places=2)
    total_quotes = serializers.IntegerField()
    accepted_quotes = serializers.IntegerField()
    quote_acceptance_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    average_response_time = serializers.FloatField()  # days
    total_contract_value = serializers.DecimalField(max_digits=15, decimal_places=2)
    on_time_deliveries = serializers.IntegerField()
    total_deliveries = serializers.IntegerField()
    on_time_delivery_rate = serializers.DecimalField(max_digits=5, decimal_places=2)


class RFQAnalyticsSerializer(serializers.Serializer):
    """Serializer for RFQ analytics"""
    
    rfq = RFQListSerializer()
    quotes_received = serializers.IntegerField()
    average_quote_value = serializers.DecimalField(max_digits=15, decimal_places=2)
    lowest_quote_value = serializers.DecimalField(max_digits=15, decimal_places=2)
    highest_quote_value = serializers.DecimalField(max_digits=15, decimal_places=2)
    value_spread = serializers.DecimalField(max_digits=15, decimal_places=2)
    average_response_time = serializers.FloatField()  # hours
    savings_potential = serializers.DecimalField(max_digits=15, decimal_places=2)


class QuoteComparisonSerializer(serializers.Serializer):
    """Serializer for quote comparison"""
    
    rfq = RFQListSerializer()
    quotes = QuoteListSerializer(many=True)
    comparison_matrix = serializers.JSONField()
    recommendations = serializers.JSONField()
    scoring_criteria = serializers.JSONField()


class SupplierOnboardingSerializer(serializers.Serializer):
    """Serializer for supplier onboarding workflow"""
    
    basic_info = serializers.JSONField()
    contact_info = serializers.JSONField()
    business_info = serializers.JSONField()
    financial_info = serializers.JSONField()
    certifications = serializers.JSONField()
    references = serializers.JSONField()
    
    def validate(self, attrs):
        """Validate onboarding data"""
        required_fields = ['basic_info', 'contact_info', 'business_info']
        
        for field in required_fields:
            if not attrs.get(field):
                raise serializers.ValidationError(f"{field} is required")
        
        return attrs
    
    def create_supplier(self, organization, created_by):
        """Create supplier from onboarding data"""
        data = self.validated_data
        
        supplier = Supplier.objects.create(
            organization=organization,
            name=data['basic_info']['name'],
            code=data['basic_info']['code'],
            supplier_type=data['basic_info']['supplier_type'],
            website=data['basic_info'].get('website', ''),
            primary_contact_name=data['contact_info']['primary_contact_name'],
            primary_contact_email=data['contact_info']['primary_contact_email'],
            primary_contact_phone=data['contact_info'].get('primary_contact_phone', ''),
            address=data['contact_info'].get('address', {}),
            country=data['contact_info'].get('country', ''),
            region=data['contact_info'].get('region', ''),
            tax_id=data['business_info'].get('tax_id', ''),
            business_registration=data['business_info'].get('business_registration', ''),
            legal_name=data['business_info'].get('legal_name', ''),
            payment_terms=data['financial_info'].get('payment_terms', ''),
            currency=data['financial_info'].get('currency', 'USD'),
            certifications=data.get('certifications', []),
            status='pending_approval'
        )
        
        return supplier