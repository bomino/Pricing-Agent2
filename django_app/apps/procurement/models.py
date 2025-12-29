"""
Procurement and supplier management models
"""
import uuid
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.contrib.postgres.indexes import GinIndex
from django.utils import timezone
from apps.core.models import TimestampedModel, Organization
from django.contrib.auth.models import User
from apps.pricing.models import Material


class PurchaseOrder(TimestampedModel):
    """Purchase Order header"""
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='purchase_orders')
    po_number = models.CharField(max_length=50, db_index=True)
    supplier = models.ForeignKey('Supplier', on_delete=models.SET_NULL, null=True, related_name='purchase_orders')
    
    # Dates
    order_date = models.DateField()
    delivery_date = models.DateField(null=True, blank=True)
    
    # Financial
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'purchase_orders'
        unique_together = ['organization', 'po_number']
        ordering = ['-order_date', '-created_at']
    
    def __str__(self):
        return f"PO {self.po_number} - {self.supplier.name if self.supplier else 'No Supplier'}"


class PurchaseOrderLine(TimestampedModel):
    """Purchase Order line items"""
    
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='lines')
    line_number = models.CharField(max_length=10)
    material = models.ForeignKey(Material, on_delete=models.SET_NULL, null=True)
    
    # Quantities and pricing
    quantity = models.DecimalField(max_digits=15, decimal_places=3)
    unit_price = models.DecimalField(max_digits=15, decimal_places=4)
    total_price = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Delivery
    delivery_date = models.DateField(null=True, blank=True)
    
    class Meta:
        db_table = 'purchase_order_lines'
        unique_together = ['purchase_order', 'line_number']
        ordering = ['line_number']
    
    def __str__(self):
        return f"Line {self.line_number} - {self.material.name if self.material else 'No Material'}"


class Supplier(TimestampedModel):
    """Supplier master data"""
    
    SUPPLIER_TYPES = [
        ('manufacturer', 'Manufacturer'),
        ('distributor', 'Distributor'),
        ('reseller', 'Reseller'),
        ('service_provider', 'Service Provider'),
        ('contractor', 'Contractor'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('blacklisted', 'Blacklisted'),
        ('pending_approval', 'Pending Approval'),
        ('suspended', 'Suspended'),
    ]
    
    RISK_LEVELS = [
        ('low', 'Low Risk'),
        ('medium', 'Medium Risk'),
        ('high', 'High Risk'),
        ('critical', 'Critical Risk'),
    ]
    
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='suppliers')
    
    # Basic information
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=100, db_index=True)
    supplier_type = models.CharField(max_length=30, choices=SUPPLIER_TYPES)
    website = models.URLField(blank=True)
    
    # Contact information
    primary_contact_name = models.CharField(max_length=255, blank=True)
    primary_contact_email = models.EmailField(blank=True)
    primary_contact_phone = models.CharField(
        max_length=20, 
        blank=True,
        validators=[RegexValidator(
            regex=r'^\+?1?\d{9,15}$',
            message="Phone number must be entered in the format: '+999999999'."
        )]
    )
    
    # Address information
    address = models.JSONField(default=dict, blank=True)  # Structured address
    country = models.CharField(max_length=100, blank=True)
    region = models.CharField(max_length=100, blank=True)
    
    # Business information
    tax_id = models.CharField(max_length=50, blank=True)
    business_registration = models.CharField(max_length=100, blank=True)
    legal_name = models.CharField(max_length=255, blank=True)
    
    # Financial information
    payment_terms = models.CharField(max_length=100, blank=True)  # e.g., "Net 30"
    currency = models.CharField(max_length=3, default='USD')
    credit_limit = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    # Performance metrics
    rating = models.DecimalField(
        max_digits=3, 
        decimal_places=2, 
        null=True, 
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    on_time_delivery_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    quality_score = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # Risk and compliance
    risk_level = models.CharField(max_length=20, choices=RISK_LEVELS, default='medium')
    certifications = models.JSONField(default=list, blank=True)
    compliance_documents = models.JSONField(default=list, blank=True)
    
    # Status and lifecycle
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Categories and capabilities
    categories = models.ManyToManyField('core.Category', blank=True, related_name='suppliers')
    capabilities = models.JSONField(default=list, blank=True)
    
    # Additional metadata
    notes = models.TextField(blank=True)
    tags = models.JSONField(default=list, blank=True)
    
    class Meta:
        db_table = 'suppliers'
        unique_together = ['organization', 'code']
        ordering = ['name']
        indexes = [
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['supplier_type', 'status']),
            models.Index(fields=['country', 'region']),
            models.Index(fields=['rating']),
            GinIndex(fields=['capabilities']),
            GinIndex(fields=['tags']),
        ]
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    def get_absolute_url(self):
        """Return the URL for this supplier's detail page"""
        from django.urls import reverse
        return reverse('procurement:supplier_detail', kwargs={'pk': self.id})
    
    @property
    def is_approved(self):
        """Check if supplier is approved"""
        return self.status == 'active' and self.approved_at is not None
    
    def calculate_performance_score(self):
        """Calculate overall performance score"""
        metrics = []
        
        if self.rating is not None:
            metrics.append(float(self.rating) * 20)  # Convert 5-point scale to 100
        
        if self.on_time_delivery_rate is not None:
            metrics.append(float(self.on_time_delivery_rate))
        
        if self.quality_score is not None:
            metrics.append(float(self.quality_score))
        
        if metrics:
            return sum(metrics) / len(metrics)
        
        return None
    
    def get_recent_quotes(self, days=90):
        """Get recent quotes from this supplier"""
        from datetime import timedelta
        cutoff_date = timezone.now() - timedelta(days=days)
        return self.quotes.filter(submitted_at__gte=cutoff_date)


class RFQ(TimestampedModel):
    """Request for Quote"""
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('closed', 'Closed'),
        ('awarded', 'Awarded'),
        ('cancelled', 'Cancelled'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='rfqs')
    
    # Basic information
    rfq_number = models.CharField(max_length=100, unique=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Requestor information
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_rfqs')
    department = models.CharField(max_length=100, blank=True)
    cost_center = models.CharField(max_length=50, blank=True)
    
    # Timeline
    deadline = models.DateTimeField()
    required_delivery_date = models.DateField(null=True, blank=True)
    
    # Status and priority
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    
    # Suppliers
    invited_suppliers = models.ManyToManyField(Supplier, blank=True, related_name='invited_rfqs')
    public_rfq = models.BooleanField(default=False)  # Open to all suppliers
    
    # Terms and conditions
    terms_and_conditions = models.TextField(blank=True)
    payment_terms = models.CharField(max_length=100, blank=True)
    delivery_terms = models.CharField(max_length=100, blank=True)
    
    # Evaluation criteria
    evaluation_criteria = models.JSONField(default=dict, blank=True)
    
    # Documents and attachments
    attachments = models.JSONField(default=list, blank=True)
    
    # Workflow
    published_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    awarded_quote = models.ForeignKey('Quote', on_delete=models.SET_NULL, null=True, blank=True, related_name='awarded_rfqs')
    
    class Meta:
        db_table = 'rfqs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['status', 'deadline']),
            models.Index(fields=['created_by', '-created_at']),
            models.Index(fields=['priority', 'status']),
        ]
    
    def __str__(self):
        return f"{self.rfq_number} - {self.title}"
    
    def get_absolute_url(self):
        """Return the URL for this RFQ's detail page"""
        from django.urls import reverse
        return reverse('procurement:rfq_detail', kwargs={'pk': self.id})
    
    @property
    def is_expired(self):
        """Check if RFQ deadline has passed"""
        return timezone.now() > self.deadline
    
    @property
    def days_remaining(self):
        """Calculate days remaining until deadline"""
        if self.is_expired:
            return 0
        delta = self.deadline - timezone.now()
        return delta.days
    
    def publish(self, user):
        """Publish the RFQ"""
        self.status = 'published'
        self.published_at = timezone.now()
        self.save()
        
        # Send notifications to invited suppliers
        self.notify_suppliers()
    
    def close(self, user):
        """Close the RFQ"""
        self.status = 'closed'
        self.closed_at = timezone.now()
        self.save()
    
    def award_to_quote(self, quote, user):
        """Award RFQ to a specific quote"""
        self.awarded_quote = quote
        self.status = 'awarded'
        self.save()
        
        # Update quote status
        quote.status = 'accepted'
        quote.save()
    
    def notify_suppliers(self):
        """Send notifications to invited suppliers"""
        # Implement notification logic
        pass


class RFQItem(TimestampedModel):
    """Individual items in an RFQ"""
    
    rfq = models.ForeignKey(RFQ, on_delete=models.CASCADE, related_name='items')
    material = models.ForeignKey(Material, on_delete=models.CASCADE)
    
    # Quantity and specifications
    quantity = models.DecimalField(max_digits=15, decimal_places=4)
    unit_of_measure = models.CharField(max_length=50)
    
    # Specifications
    specifications = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    
    # Delivery requirements
    required_delivery_date = models.DateField(null=True, blank=True)
    delivery_location = models.CharField(max_length=255, blank=True)
    
    # Reference information
    budget_estimate = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    last_purchase_price = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    
    class Meta:
        db_table = 'rfq_items'
        unique_together = ['rfq', 'material']
        ordering = ['material__code']
    
    def __str__(self):
        return f"{self.rfq.rfq_number} - {self.material.code} ({self.quantity})"


class Quote(TimestampedModel):
    """Supplier quotes in response to RFQs"""
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('withdrawn', 'Withdrawn'),
        ('expired', 'Expired'),
    ]
    
    rfq = models.ForeignKey(RFQ, on_delete=models.CASCADE, related_name='quotes')
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='quotes')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='quotes')
    
    # Basic information
    quote_number = models.CharField(max_length=100)
    reference_number = models.CharField(max_length=100, blank=True)  # Supplier's internal reference
    
    # Pricing
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Terms
    validity_period = models.PositiveIntegerField(help_text="Validity period in days")
    payment_terms = models.CharField(max_length=100, blank=True)
    delivery_terms = models.CharField(max_length=100, blank=True)
    lead_time_days = models.PositiveIntegerField(null=True, blank=True)
    
    # Status and timeline
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    submitted_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Evaluation
    technical_score = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    commercial_score = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    overall_score = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # Comments and notes
    supplier_notes = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)
    
    # Attachments
    attachments = models.JSONField(default=list, blank=True)
    
    # Evaluation metadata
    evaluated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    evaluated_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'quotes'
        unique_together = ['rfq', 'supplier']
        ordering = ['-submitted_at']
        indexes = [
            models.Index(fields=['rfq', 'status']),
            models.Index(fields=['supplier', 'status']),
            models.Index(fields=['organization', '-submitted_at']),
            models.Index(fields=['status', 'expires_at']),
        ]
    
    def __str__(self):
        return f"{self.quote_number} - {self.supplier.name}"
    
    @property
    def is_expired(self):
        """Check if quote has expired"""
        return self.expires_at and timezone.now() > self.expires_at
    
    @property
    def days_until_expiry(self):
        """Calculate days until quote expires"""
        if not self.expires_at or self.is_expired:
            return 0
        delta = self.expires_at - timezone.now()
        return delta.days
    
    def submit(self):
        """Submit the quote"""
        self.status = 'submitted'
        self.submitted_at = timezone.now()
        
        # Calculate expiry date
        if self.validity_period:
            self.expires_at = timezone.now() + timezone.timedelta(days=self.validity_period)
        
        self.save()
    
    def accept(self, user):
        """Accept the quote"""
        self.status = 'accepted'
        self.evaluated_by = user
        self.evaluated_at = timezone.now()
        self.save()
    
    def reject(self, reason, user):
        """Reject the quote"""
        self.status = 'rejected'
        self.rejection_reason = reason
        self.evaluated_by = user
        self.evaluated_at = timezone.now()
        self.save()
    
    def calculate_unit_prices(self):
        """Calculate unit prices for all items"""
        unit_prices = {}
        for item in self.items.all():
            if item.quantity > 0:
                unit_prices[item.material.id] = item.price / item.quantity
        return unit_prices


class QuoteItem(TimestampedModel):
    """Individual items in a quote"""
    
    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, related_name='items')
    rfq_item = models.ForeignKey(RFQItem, on_delete=models.CASCADE)
    material = models.ForeignKey(Material, on_delete=models.CASCADE)
    
    # Pricing
    price = models.DecimalField(max_digits=15, decimal_places=4)
    unit_price = models.DecimalField(max_digits=15, decimal_places=4)
    currency = models.CharField(max_length=3, default='USD')
    
    # Quantity and specifications
    quantity = models.DecimalField(max_digits=15, decimal_places=4)
    unit_of_measure = models.CharField(max_length=50)
    
    # Delivery
    lead_time_days = models.PositiveIntegerField(null=True, blank=True)
    delivery_date = models.DateField(null=True, blank=True)
    
    # Specifications and alternatives
    specifications = models.JSONField(default=dict, blank=True)
    alternative_offered = models.BooleanField(default=False)
    alternative_description = models.TextField(blank=True)
    
    # Comments
    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'quote_items'
        unique_together = ['quote', 'rfq_item']
        ordering = ['material__code']
    
    def __str__(self):
        return f"{self.quote.quote_number} - {self.material.code}"
    
    def save(self, *args, **kwargs):
        """Auto-calculate unit price"""
        if self.quantity > 0:
            self.unit_price = self.price / self.quantity
        super().save(*args, **kwargs)


class Contract(TimestampedModel):
    """Procurement contracts"""
    
    CONTRACT_TYPES = [
        ('purchase_order', 'Purchase Order'),
        ('blanket_order', 'Blanket Order'),
        ('framework_agreement', 'Framework Agreement'),
        ('service_contract', 'Service Contract'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending_approval', 'Pending Approval'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('terminated', 'Terminated'),
        ('expired', 'Expired'),
    ]
    
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='contracts')
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='contracts')
    quote = models.ForeignKey(Quote, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Basic information
    contract_number = models.CharField(max_length=100, unique=True)
    title = models.CharField(max_length=255)
    contract_type = models.CharField(max_length=30, choices=CONTRACT_TYPES)
    
    # Financial terms
    total_value = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    payment_terms = models.CharField(max_length=100)
    
    # Timeline
    start_date = models.DateField()
    end_date = models.DateField()
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Approval workflow
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_contracts')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Documents
    contract_document = models.FileField(upload_to='contracts/', blank=True, null=True)
    attachments = models.JSONField(default=list, blank=True)
    
    # Terms and conditions
    terms_and_conditions = models.TextField(blank=True)
    special_terms = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'contracts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['supplier', 'status']),
            models.Index(fields=['contract_type', 'status']),
            models.Index(fields=['start_date', 'end_date']),
        ]
    
    def __str__(self):
        return f"{self.contract_number} - {self.supplier.name}"
    
    def get_absolute_url(self):
        """Return the URL for this contract's detail page"""
        from django.urls import reverse
        return reverse('procurement:contract_detail', kwargs={'pk': self.id})
    
    @property
    def is_active(self):
        """Check if contract is currently active"""
        from django.utils import timezone
        today = timezone.now().date()
        return (self.status == 'active' and 
                self.start_date <= today <= self.end_date)
    
    @property
    def days_until_expiry(self):
        """Calculate days until contract expires"""
        from django.utils import timezone
        today = timezone.now().date()
        if today > self.end_date:
            return 0
        return (self.end_date - today).days
    
    def approve(self, user):
        """Approve the contract"""
        self.status = 'active'
        self.approved_by = user
        self.approved_at = timezone.now()
        self.save()
    
    def terminate(self, reason=''):
        """Terminate the contract"""
        self.status = 'terminated'
        if reason:
            self.special_terms['termination_reason'] = reason
        self.save()
    
    class Meta:
        db_table = 'procurement_contracts'
        verbose_name = 'Contract'
        verbose_name_plural = 'Contracts'
        ordering = ['-created_at']


class SupplierContact(TimestampedModel):
    """Supplier contact information"""
    
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='contacts')
    
    # Contact details
    name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=50, blank=True)
    role = models.CharField(max_length=100, blank=True)
    department = models.CharField(max_length=100, blank=True)
    
    # Flags
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    # Notes
    notes = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.name} - {self.supplier.name}"
    
    class Meta:
        db_table = 'procurement_supplier_contacts'
        verbose_name = 'Supplier Contact'
        verbose_name_plural = 'Supplier Contacts'
        ordering = ['supplier', '-is_primary', 'name']


class SupplierDocument(TimestampedModel):
    """Documents related to suppliers"""
    
    DOCUMENT_TYPES = [
        ('certificate', 'Certificate'),
        ('license', 'License'),
        ('insurance', 'Insurance'),
        ('tax_document', 'Tax Document'),
        ('financial_statement', 'Financial Statement'),
        ('quality_certification', 'Quality Certification'),
        ('other', 'Other'),
    ]
    
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='documents')
    
    # Document information
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPES)
    document = models.FileField(upload_to='supplier_documents/%Y/%m/')
    description = models.TextField(blank=True)
    
    # Validity
    valid_from = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)
    
    # Metadata
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.document_type} - {self.supplier.name}"
    
    class Meta:
        db_table = 'procurement_supplier_documents'
        verbose_name = 'Supplier Document'
        verbose_name_plural = 'Supplier Documents'
        ordering = ['supplier', '-uploaded_at']