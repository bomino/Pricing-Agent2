# Procurement Modules Implementation Guide
## Complete Blueprint for Suppliers and RFQs Modules

---

## Table of Contents
1. [Overview](#overview)
2. [Database Schema](#database-schema)
3. [Models Implementation](#models-implementation)
4. [Forms Implementation](#forms-implementation)
5. [Views Implementation](#views-implementation)
6. [URL Configuration](#url-configuration)
7. [Templates Implementation](#templates-implementation)
8. [JavaScript Functions](#javascript-functions)
9. [API Implementation](#api-implementation)
10. [Test Data Setup](#test-data-setup)
11. [Integration Points](#integration-points)
12. [Security Considerations](#security-considerations)

---

## 1. Overview

### Module Purpose
The Procurement modules provide comprehensive supplier management and RFQ (Request for Quote) functionality for enterprise procurement operations.

### Technology Stack
- **Backend**: Django 5.0.1
- **Database**: PostgreSQL with TimescaleDB
- **Frontend**: HTMX, Alpine.js, Tailwind CSS
- **Date Pickers**: Flatpickr
- **Icons**: Font Awesome
- **Charts**: Chart.js

### Key Features
- Multi-tenant organization support
- Supplier lifecycle management
- RFQ creation and management
- Quote submission and comparison
- Performance tracking
- Cross-browser compatibility (including Firefox fixes)

---

## 2. Database Schema

### Suppliers Module Tables

```sql
-- Supplier Table
CREATE TABLE procurement_supplier (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES core_organization(id),
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    legal_name VARCHAR(255),
    supplier_type VARCHAR(50) CHECK (supplier_type IN ('manufacturer', 'distributor', 'reseller', 'service_provider', 'contractor')),
    status VARCHAR(50) DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'blacklisted', 'pending_approval', 'suspended')),
    risk_level VARCHAR(20) CHECK (risk_level IN ('low', 'medium', 'high', 'critical')),
    primary_contact_name VARCHAR(255),
    primary_contact_email VARCHAR(255),
    primary_contact_phone VARCHAR(50),
    address JSONB,
    country VARCHAR(100),
    region VARCHAR(100),
    website VARCHAR(500),
    tax_id VARCHAR(50),
    business_registration VARCHAR(100),
    payment_terms VARCHAR(50),
    currency VARCHAR(10) DEFAULT 'USD',
    credit_limit DECIMAL(15, 2),
    rating DECIMAL(3, 2) CHECK (rating >= 0 AND rating <= 5),
    on_time_delivery_rate DECIMAL(5, 2) CHECK (on_time_delivery_rate >= 0 AND on_time_delivery_rate <= 100),
    quality_score DECIMAL(5, 2) CHECK (quality_score >= 0 AND quality_score <= 100),
    certifications JSONB DEFAULT '[]',
    compliance_documents JSONB DEFAULT '[]',
    capabilities JSONB DEFAULT '[]',
    tags JSONB DEFAULT '[]',
    notes TEXT,
    approved_by_id UUID REFERENCES auth_user(id),
    approved_at TIMESTAMP,
    created_by_id UUID REFERENCES auth_user(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_supplier_org_status ON procurement_supplier(organization_id, status);
CREATE INDEX idx_supplier_type_status ON procurement_supplier(supplier_type, status);
CREATE INDEX idx_supplier_country_region ON procurement_supplier(country, region);
CREATE INDEX idx_supplier_rating ON procurement_supplier(rating);
CREATE INDEX idx_supplier_capabilities ON procurement_supplier USING gin(capabilities);
CREATE INDEX idx_supplier_tags ON procurement_supplier USING gin(tags);
```

### RFQs Module Tables

```sql
-- RFQ Table
CREATE TABLE procurement_rfq (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES core_organization(id),
    rfq_number VARCHAR(50) UNIQUE NOT NULL,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    status VARCHAR(50) DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'closed', 'awarded', 'cancelled')),
    priority VARCHAR(20) DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
    department VARCHAR(100),
    cost_center VARCHAR(50),
    deadline TIMESTAMP NOT NULL,
    required_delivery_date DATE,
    payment_terms VARCHAR(100),
    delivery_terms VARCHAR(100),
    terms_and_conditions TEXT,
    public_rfq BOOLEAN DEFAULT FALSE,
    evaluation_criteria JSONB DEFAULT '{}',
    attachments JSONB DEFAULT '[]',
    published_at TIMESTAMP,
    closed_at TIMESTAMP,
    awarded_quote_id UUID REFERENCES procurement_quote(id),
    created_by_id UUID NOT NULL REFERENCES auth_user(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- RFQ-Supplier Junction Table
CREATE TABLE procurement_rfq_suppliers (
    id SERIAL PRIMARY KEY,
    rfq_id UUID NOT NULL REFERENCES procurement_rfq(id) ON DELETE CASCADE,
    supplier_id UUID NOT NULL REFERENCES procurement_supplier(id) ON DELETE CASCADE,
    UNIQUE(rfq_id, supplier_id)
);

-- Indexes
CREATE INDEX idx_rfq_org_status ON procurement_rfq(organization_id, status);
CREATE INDEX idx_rfq_status_deadline ON procurement_rfq(status, deadline);
CREATE INDEX idx_rfq_created_by ON procurement_rfq(created_by_id, created_at DESC);
CREATE INDEX idx_rfq_priority_status ON procurement_rfq(priority, status);
```

### Quote Tables

```sql
-- Quote Table
CREATE TABLE procurement_quote (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES core_organization(id),
    rfq_id UUID NOT NULL REFERENCES procurement_rfq(id),
    supplier_id UUID NOT NULL REFERENCES procurement_supplier(id),
    quote_number VARCHAR(50) UNIQUE NOT NULL,
    reference_number VARCHAR(100),
    total_amount DECIMAL(15, 2) NOT NULL,
    currency VARCHAR(10) DEFAULT 'USD',
    tax_amount DECIMAL(15, 2) DEFAULT 0,
    validity_period INTEGER DEFAULT 30,
    payment_terms VARCHAR(100),
    delivery_terms VARCHAR(100),
    lead_time_days INTEGER,
    status VARCHAR(50) DEFAULT 'draft' CHECK (status IN ('draft', 'submitted', 'under_review', 'accepted', 'rejected', 'withdrawn', 'expired')),
    technical_score DECIMAL(5, 2),
    commercial_score DECIMAL(5, 2),
    overall_score DECIMAL(5, 2),
    supplier_notes TEXT,
    internal_notes TEXT,
    rejection_reason TEXT,
    evaluated_by_id UUID REFERENCES auth_user(id),
    evaluated_at TIMESTAMP,
    submitted_at TIMESTAMP,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(rfq_id, supplier_id)
);

-- Quote Item Table
CREATE TABLE procurement_quote_item (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    quote_id UUID NOT NULL REFERENCES procurement_quote(id) ON DELETE CASCADE,
    rfq_item_id UUID REFERENCES procurement_rfq_item(id),
    material_id UUID REFERENCES pricing_material(id),
    price DECIMAL(15, 2) NOT NULL,
    unit_price DECIMAL(15, 6),
    currency VARCHAR(10) DEFAULT 'USD',
    quantity DECIMAL(15, 4) NOT NULL,
    unit_of_measure VARCHAR(50),
    lead_time_days INTEGER,
    delivery_date DATE,
    specifications JSONB DEFAULT '{}',
    alternative_offered BOOLEAN DEFAULT FALSE,
    alternative_description TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

---

## 3. Models Implementation

### Supplier Model

```python
# django_app/apps/procurement/models.py

from django.db import models
from django.contrib.auth import get_user_model
from django.urls import reverse
from decimal import Decimal
import uuid

User = get_user_model()

class Supplier(BaseModel):
    """Supplier master data model"""

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

    organization = models.ForeignKey('core.Organization', on_delete=models.PROTECT)
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    legal_name = models.CharField(max_length=255, blank=True)
    supplier_type = models.CharField(max_length=50, choices=SUPPLIER_TYPES)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='active')
    risk_level = models.CharField(max_length=20, choices=RISK_LEVELS, default='low')

    # Contact Information
    primary_contact_name = models.CharField(max_length=255, blank=True)
    primary_contact_email = models.EmailField(blank=True)
    primary_contact_phone = models.CharField(max_length=50, blank=True)
    address = models.JSONField(default=dict, blank=True)
    country = models.CharField(max_length=100, blank=True)
    region = models.CharField(max_length=100, blank=True)
    website = models.URLField(max_length=500, blank=True)

    # Business Details
    tax_id = models.CharField(max_length=50, blank=True)
    business_registration = models.CharField(max_length=100, blank=True)
    payment_terms = models.CharField(max_length=50, blank=True)
    currency = models.CharField(max_length=10, default='USD')
    credit_limit = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)

    # Performance Metrics
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0, validators=[MinValueValidator(0), MaxValueValidator(5)])
    on_time_delivery_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    quality_score = models.DecimalField(max_digits=5, decimal_places=2, default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])

    # Compliance
    certifications = models.JSONField(default=list, blank=True)
    compliance_documents = models.JSONField(default=list, blank=True)

    # Additional
    categories = models.ManyToManyField('Category', blank=True)
    capabilities = models.JSONField(default=list, blank=True)
    tags = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True)

    # Approval
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_suppliers')
    approved_at = models.DateTimeField(null=True, blank=True)

    # Audit
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_suppliers')

    class Meta:
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
        return f"{self.name} ({self.code})"

    def get_absolute_url(self):
        return reverse('procurement:supplier_detail', kwargs={'pk': self.pk})

    @property
    def is_approved(self):
        return self.approved_by is not None

    def calculate_performance_score(self):
        """Calculate overall performance score"""
        scores = []
        if self.rating:
            scores.append(float(self.rating) * 20)  # Convert 5-point to 100-point
        if self.on_time_delivery_rate:
            scores.append(float(self.on_time_delivery_rate))
        if self.quality_score:
            scores.append(float(self.quality_score))

        return sum(scores) / len(scores) if scores else 0

    def get_recent_quotes(self, days=90):
        """Get recent quotes from this supplier"""
        from datetime import timedelta
        from django.utils import timezone
        cutoff = timezone.now() - timedelta(days=days)
        return self.quotes.filter(created_at__gte=cutoff)
```

### RFQ Model

```python
class RFQ(BaseModel):
    """Request for Quote model"""

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

    organization = models.ForeignKey('core.Organization', on_delete=models.PROTECT)
    rfq_number = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=500)
    description = models.TextField()
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='draft')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')

    # Department Info
    department = models.CharField(max_length=100, blank=True)
    cost_center = models.CharField(max_length=50, blank=True)

    # Timeline
    deadline = models.DateTimeField()
    required_delivery_date = models.DateField(null=True, blank=True)

    # Terms
    payment_terms = models.CharField(max_length=100, blank=True)
    delivery_terms = models.CharField(max_length=100, blank=True)
    terms_and_conditions = models.TextField(blank=True)

    # Suppliers
    invited_suppliers = models.ManyToManyField(Supplier, related_name='rfqs_invited', blank=True)
    suppliers = models.ManyToManyField(Supplier, related_name='rfqs', blank=True)  # Alias for compatibility
    public_rfq = models.BooleanField(default=False)

    # Evaluation
    evaluation_criteria = models.JSONField(default=dict, blank=True)

    # Workflow
    published_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    awarded_quote = models.ForeignKey('Quote', on_delete=models.SET_NULL, null=True, blank=True, related_name='awarded_rfqs')

    # Attachments
    attachments = models.JSONField(default=list, blank=True)

    # Audit
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_rfqs')

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['status', 'deadline']),
            models.Index(fields=['created_by', '-created_at']),
            models.Index(fields=['priority', 'status']),
        ]
        verbose_name = 'RFQ'
        verbose_name_plural = 'RFQs'

    def __str__(self):
        return f"{self.rfq_number}: {self.title}"

    def get_absolute_url(self):
        return reverse('procurement:rfq_detail', kwargs={'pk': self.pk})

    @property
    def is_expired(self):
        from django.utils import timezone
        return timezone.now() > self.deadline

    @property
    def days_remaining(self):
        from django.utils import timezone
        if self.is_expired:
            return 0
        delta = self.deadline - timezone.now()
        return delta.days

    def publish(self, user):
        """Publish RFQ to suppliers"""
        from django.utils import timezone
        self.status = 'published'
        self.published_at = timezone.now()
        self.save()
        self.notify_suppliers()

    def close(self, user):
        """Close RFQ"""
        from django.utils import timezone
        self.status = 'closed'
        self.closed_at = timezone.now()
        self.save()

    def award_to_quote(self, quote, user):
        """Award RFQ to a specific quote"""
        self.status = 'awarded'
        self.awarded_quote = quote
        self.save()
        quote.status = 'accepted'
        quote.save()

    def notify_suppliers(self):
        """Send notifications to invited suppliers"""
        # Placeholder for email notification logic
        pass
```

---

## 4. Forms Implementation

### Supplier Form

```python
# django_app/apps/procurement/forms.py

from django import forms
from .models import Supplier, RFQ

class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = [
            'name', 'code', 'legal_name', 'tax_id', 'website',
            'primary_contact_name', 'primary_contact_email', 'primary_contact_phone',
            'address', 'country', 'region',
            'supplier_type', 'categories',
            'payment_terms', 'currency', 'credit_limit',
            'status'
        ]

        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-navy-500 focus:ring-navy-500 sm:text-sm',
                'placeholder': 'Enter supplier name'
            }),
            'code': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-navy-500 focus:ring-navy-500 sm:text-sm',
                'placeholder': 'Auto-generated if left blank'
            }),
            'legal_name': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-navy-500 focus:ring-navy-500 sm:text-sm',
                'placeholder': 'Legal business name'
            }),
            'tax_id': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-navy-500 focus:ring-navy-500 sm:text-sm',
                'placeholder': 'Tax identification number'
            }),
            'website': forms.URLInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-navy-500 focus:ring-navy-500 sm:text-sm',
                'placeholder': 'https://example.com'
            }),
            'primary_contact_name': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-navy-500 focus:ring-navy-500 sm:text-sm',
                'placeholder': 'Primary contact person'
            }),
            'primary_contact_email': forms.EmailInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-navy-500 focus:ring-navy-500 sm:text-sm',
                'placeholder': 'contact@example.com'
            }),
            'primary_contact_phone': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-navy-500 focus:ring-navy-500 sm:text-sm',
                'placeholder': '+1-555-123-4567'
            }),
            'address': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-navy-500 focus:ring-navy-500 sm:text-sm',
                'placeholder': 'Full address'
            }),
            'country': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-navy-500 focus:ring-navy-500 sm:text-sm',
                'placeholder': 'Country'
            }),
            'region': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-navy-500 focus:ring-navy-500 sm:text-sm',
                'placeholder': 'State/Region'
            }),
            'supplier_type': forms.Select(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-navy-500 focus:ring-navy-500 sm:text-sm'
            }),
            'categories': forms.SelectMultiple(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-navy-500 focus:ring-navy-500 sm:text-sm'
            }),
            'payment_terms': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-navy-500 focus:ring-navy-500 sm:text-sm',
                'placeholder': 'NET30, NET45, etc.'
            }),
            'currency': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-navy-500 focus:ring-navy-500 sm:text-sm',
                'placeholder': 'USD'
            }),
            'credit_limit': forms.NumberInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-navy-500 focus:ring-navy-500 sm:text-sm',
                'placeholder': '0.00'
            }),
            'status': forms.Select(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-navy-500 focus:ring-navy-500 sm:text-sm'
            })
        }
```

### RFQ Form

```python
class RFQForm(forms.ModelForm):
    class Meta:
        model = RFQ
        fields = [
            'title', 'rfq_number', 'description',
            'department', 'cost_center',
            'deadline', 'required_delivery_date',
            'payment_terms', 'delivery_terms', 'terms_and_conditions',
            'priority', 'public_rfq', 'evaluation_criteria',
            'status'
        ]

        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-navy-500 focus:ring-navy-500 sm:text-sm',
                'placeholder': 'Enter RFQ title',
                'required': True
            }),
            'rfq_number': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-navy-500 focus:ring-navy-500 sm:text-sm bg-gray-50',
                'placeholder': 'Auto-generated',
                'readonly': True
            }),
            'description': forms.Textarea(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-navy-500 focus:ring-navy-500 sm:text-sm',
                'rows': 4,
                'placeholder': 'Detailed description of requirements',
                'required': True
            }),
            'department': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-navy-500 focus:ring-navy-500 sm:text-sm',
                'placeholder': 'Requesting department'
            }),
            'cost_center': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-navy-500 focus:ring-navy-500 sm:text-sm',
                'placeholder': 'Cost center code'
            }),
            'deadline': forms.DateTimeInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-navy-500 focus:ring-navy-500 sm:text-sm',
                'type': 'datetime-local',
                'required': True
            }),
            'required_delivery_date': forms.DateInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-navy-500 focus:ring-navy-500 sm:text-sm',
                'type': 'date'
            }),
            'payment_terms': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-navy-500 focus:ring-navy-500 sm:text-sm',
                'placeholder': 'e.g., NET30, NET45'
            }),
            'delivery_terms': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-navy-500 focus:ring-navy-500 sm:text-sm',
                'placeholder': 'e.g., FOB, DDP'
            }),
            'terms_and_conditions': forms.Textarea(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-navy-500 focus:ring-navy-500 sm:text-sm',
                'rows': 3,
                'placeholder': 'Additional terms and conditions'
            }),
            'priority': forms.Select(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-navy-500 focus:ring-navy-500 sm:text-sm'
            }),
            'public_rfq': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-navy-600 focus:ring-navy-500 border-gray-300 rounded'
            }),
            'evaluation_criteria': forms.Textarea(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-navy-500 focus:ring-navy-500 sm:text-sm',
                'rows': 2,
                'placeholder': 'e.g., Price: 40%, Quality: 30%, Delivery: 20%, Service: 10%'
            }),
            'status': forms.Select(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-navy-500 focus:ring-navy-500 sm:text-sm'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            # Generate RFQ number for new instances
            from datetime import datetime
            import random
            self.fields['rfq_number'].initial = f"RFQ-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
```

---

## 5. Views Implementation

### Base Mixin

```python
# django_app/apps/procurement/views.py

from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, redirect
from django.http import JsonResponse
from django.db.models import Q, Count, Sum, Avg
from datetime import datetime, timedelta
import random

class OrganizationRequiredMixin(LoginRequiredMixin):
    """Mixin to ensure user has organization"""

    def dispatch(self, request, *args, **kwargs):
        if not hasattr(request.user, 'profile') or not request.user.profile.organization:
            messages.error(request, 'You must belong to an organization to access this page.')
            return redirect('accounts:profile')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(organization=self.request.user.profile.organization)

    def form_valid(self, form):
        form.instance.organization = self.request.user.profile.organization
        if hasattr(form.instance, 'created_by'):
            form.instance.created_by = self.request.user
        return super().form_valid(form)
```

### Supplier Views

```python
class SupplierListView(OrganizationRequiredMixin, ListView):
    model = Supplier
    template_name = 'procurement/supplier_list.html'
    context_object_name = 'suppliers'
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = queryset.filter(status='active')

        # Search functionality
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(code__icontains=search) |
                Q(primary_contact_email__icontains=search)
            )

        # Filter by type
        supplier_type = self.request.GET.get('type')
        if supplier_type:
            queryset = queryset.filter(supplier_type=supplier_type)

        # Filter by status
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)

        return queryset.order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_suppliers'] = self.get_queryset().count()
        context['active_suppliers'] = self.get_queryset().filter(status='active').count()
        context['avg_rating'] = self.get_queryset().aggregate(avg=Avg('rating'))['avg'] or 0
        return context


class SupplierDetailView(OrganizationRequiredMixin, DetailView):
    model = Supplier
    template_name = 'procurement/supplier_detail.html'
    context_object_name = 'supplier'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        supplier = self.object

        # Recent RFQs
        context['recent_rfqs'] = supplier.rfqs_invited.order_by('-created_at')[:10]

        # Performance metrics
        from datetime import timedelta
        from django.utils import timezone
        cutoff = timezone.now() - timedelta(days=90)

        quotes = supplier.quotes.filter(created_at__gte=cutoff)
        context['performance_metrics'] = {
            'total_quotes': quotes.count(),
            'approved_quotes': quotes.filter(status='accepted').count(),
            'quote_acceptance_rate': (quotes.filter(status='accepted').count() / quotes.count() * 100) if quotes.count() > 0 else 0,
            'avg_response_time': 'N/A'  # Placeholder
        }

        return context


class SupplierCreateView(OrganizationRequiredMixin, CreateView):
    model = Supplier
    form_class = SupplierForm
    template_name = 'procurement/supplier_form.html'

    def form_valid(self, form):
        # Auto-generate supplier code if not provided
        if not form.instance.code:
            form.instance.code = f"SUP-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"

        form.instance.organization = self.request.user.profile.organization
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Supplier created successfully!')
        return super().form_valid(form)


class SupplierUpdateView(OrganizationRequiredMixin, UpdateView):
    model = Supplier
    form_class = SupplierForm
    template_name = 'procurement/supplier_form.html'

    def form_valid(self, form):
        messages.success(self.request, 'Supplier updated successfully!')
        return super().form_valid(form)


class SupplierIndividualPerformanceView(OrganizationRequiredMixin, DetailView):
    model = Supplier
    template_name = 'procurement/supplier_individual_performance.html'
    context_object_name = 'supplier'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        supplier = self.object

        # Calculate metrics
        context['total_rfqs'] = supplier.rfqs_invited.count()
        context['total_quotes'] = supplier.quotes.count()
        context['approved_quotes'] = supplier.quotes.filter(status='accepted').count()
        context['pending_quotes'] = supplier.quotes.filter(status='submitted').count()
        context['rejected_quotes'] = supplier.quotes.filter(status='rejected').count()

        # Calculate average quote value
        avg_value = supplier.quotes.aggregate(avg=Avg('total_amount'))['avg']
        context['average_quote_value'] = avg_value or 0

        # Calculate total business
        total_business = supplier.quotes.filter(status='accepted').aggregate(
            total=Sum('total_amount')
        )['total']
        context['total_business'] = total_business or 0

        # Calculate win rate
        if context['total_quotes'] > 0:
            context['win_rate'] = (context['approved_quotes'] / context['total_quotes']) * 100
        else:
            context['win_rate'] = 0

        # Recent activity
        context['recent_quotes'] = supplier.quotes.order_by('-created_at')[:10]
        context['recent_rfqs'] = supplier.rfqs_invited.order_by('-created_at')[:10]

        return context
```

### RFQ Views

```python
class RFQListView(OrganizationRequiredMixin, ListView):
    model = RFQ
    template_name = 'procurement/rfq_list.html'
    context_object_name = 'rfqs'
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset()

        # Search
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(rfq_number__icontains=search) |
                Q(title__icontains=search) |
                Q(description__icontains=search)
            )

        # Filter by status
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)

        # Filter by priority
        priority = self.request.GET.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)

        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_rfqs'] = self.get_queryset().count()
        context['open_rfqs'] = self.get_queryset().filter(status='published').count()
        context['pending_quotes'] = Quote.objects.filter(
            rfq__organization=self.request.user.profile.organization,
            status='submitted'
        ).count()
        return context


class RFQDetailView(OrganizationRequiredMixin, DetailView):
    model = RFQ
    template_name = 'procurement/rfq_detail.html'
    context_object_name = 'rfq'

    def get_object(self):
        return get_object_or_404(
            RFQ.objects.prefetch_related('items', 'invited_suppliers', 'quotes'),
            pk=self.kwargs['pk'],
            organization=self.request.user.profile.organization
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['rfq_items'] = self.object.items.all()
        context['quotes'] = self.object.quotes.order_by('created_at')
        context['response_rate'] = (
            self.object.quotes.count() / self.object.invited_suppliers.count() * 100
        ) if self.object.invited_suppliers.count() > 0 else 0
        return context


class RFQCreateView(OrganizationRequiredMixin, CreateView):
    model = RFQ
    form_class = RFQForm
    template_name = 'procurement/rfq_form.html'

    def get_initial(self):
        initial = super().get_initial()

        # Auto-generate RFQ number
        initial['rfq_number'] = f"RFQ-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"

        # Pre-populate supplier if provided
        supplier_id = self.request.GET.get('supplier')
        if supplier_id:
            initial['invited_suppliers'] = [supplier_id]

        return initial

    def form_valid(self, form):
        form.instance.organization = self.request.user.profile.organization
        form.instance.created_by = self.request.user
        messages.success(self.request, 'RFQ created successfully!')
        return super().form_valid(form)


class RFQUpdateView(OrganizationRequiredMixin, UpdateView):
    model = RFQ
    form_class = RFQForm
    template_name = 'procurement/rfq_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_edit'] = True
        return context

    def form_valid(self, form):
        messages.success(self.request, 'RFQ updated successfully!')
        return super().form_valid(form)


class RFQDuplicateView(OrganizationRequiredMixin, DetailView):
    model = RFQ

    def get(self, request, *args, **kwargs):
        original_rfq = self.get_object()

        # Create duplicate
        new_rfq = RFQ.objects.create(
            organization=original_rfq.organization,
            rfq_number=f"RFQ-{uuid.uuid4().hex[:8]}",
            title=f"Copy of {original_rfq.title}",
            description=original_rfq.description,
            status='draft',
            priority=original_rfq.priority,
            department=original_rfq.department,
            cost_center=original_rfq.cost_center,
            deadline=timezone.now() + timedelta(days=30),
            required_delivery_date=original_rfq.required_delivery_date,
            payment_terms=original_rfq.payment_terms,
            delivery_terms=original_rfq.delivery_terms,
            terms_and_conditions=original_rfq.terms_and_conditions,
            public_rfq=original_rfq.public_rfq,
            evaluation_criteria=original_rfq.evaluation_criteria,
            created_by=request.user
        )

        # Copy suppliers
        for supplier in original_rfq.invited_suppliers.all():
            new_rfq.invited_suppliers.add(supplier)
            new_rfq.suppliers.add(supplier)

        # Copy items
        for item in original_rfq.items.all():
            RFQItem.objects.create(
                rfq=new_rfq,
                material=item.material,
                quantity=item.quantity,
                unit_of_measure=item.unit_of_measure,
                specifications=item.specifications,
                notes=item.notes,
                required_delivery_date=item.required_delivery_date,
                delivery_location=item.delivery_location,
                budget_estimate=item.budget_estimate,
                last_purchase_price=item.last_purchase_price
            )

        messages.success(request, 'RFQ duplicated successfully!')
        return redirect('procurement:rfq_edit', pk=new_rfq.pk)
```

### Quote Views

```python
class QuoteComparisonView(OrganizationRequiredMixin, TemplateView):
    template_name = 'procurement/quote_comparison.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        rfq_id = self.request.GET.get('rfq')

        if not rfq_id:
            # Show RFQ selection list
            context['rfqs'] = RFQ.objects.filter(
                organization=self.request.user.profile.organization,
                status__in=['published', 'closed']
            ).annotate(
                quotes_count=Count('quotes')
            ).filter(quotes_count__gt=0).order_by('-created_at')
            context['mode'] = 'selection'
        else:
            # Show comparison
            rfq = get_object_or_404(
                RFQ,
                pk=rfq_id,
                organization=self.request.user.profile.organization
            )

            quotes = rfq.quotes.select_related('supplier').prefetch_related('items')

            # Build comparison data
            comparison_data = []
            for quote in quotes:
                data = {
                    'quote': quote,
                    'supplier': quote.supplier,
                    'total_amount': quote.total_amount,
                    'payment_terms': quote.payment_terms,
                    'delivery_terms': quote.delivery_terms,
                    'lead_time': quote.lead_time_days,
                    'validity': quote.validity_period,
                    'items': {}
                }

                for item in quote.items.all():
                    if item.rfq_item_id:
                        data['items'][item.rfq_item_id] = {
                            'unit_price': item.unit_price,
                            'price': item.price
                        }

                comparison_data.append(data)

            # Sort by total amount
            comparison_data.sort(key=lambda x: x['total_amount'])

            # Calculate best prices per item
            best_prices = {}
            for rfq_item in rfq.items.all():
                best_price = float('inf')
                for data in comparison_data:
                    if rfq_item.id in data['items']:
                        price = data['items'][rfq_item.id]['unit_price']
                        if price < best_price:
                            best_price = price
                if best_price != float('inf'):
                    best_prices[rfq_item.id] = best_price

            context['rfq'] = rfq
            context['comparison_data'] = comparison_data
            context['quotes'] = quotes
            context['best_prices'] = best_prices
            context['rfq_items'] = rfq.items.all()
            context['mode'] = 'comparison'

        return context
```

---

## 6. URL Configuration

```python
# django_app/apps/procurement/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'procurement'

# API router
router = DefaultRouter()
router.register(r'suppliers', views.SupplierViewSet, basename='supplier')
router.register(r'rfqs', views.RFQViewSet, basename='rfq')
router.register(r'quotes', views.QuoteViewSet, basename='quote')

urlpatterns = [
    # API endpoints
    path('api/', include(router.urls)),

    # Supplier URLs
    path('suppliers/', views.SupplierListView.as_view(), name='supplier_list'),
    path('suppliers/export/', views.SupplierExportView.as_view(), name='supplier_export_all'),
    path('suppliers/create/', views.SupplierCreateView.as_view(), name='supplier_create'),
    path('suppliers/<uuid:pk>/', views.SupplierDetailView.as_view(), name='supplier_detail'),
    path('suppliers/<uuid:pk>/edit/', views.SupplierUpdateView.as_view(), name='supplier_update'),
    path('suppliers/<uuid:pk>/export/', views.SupplierExportView.as_view(), name='supplier_export'),
    path('suppliers/<uuid:pk>/performance/', views.SupplierIndividualPerformanceView.as_view(), name='supplier_individual_performance'),
    path('suppliers/<uuid:pk>/performance/export/', views.SupplierPerformanceExportView.as_view(), name='supplier_performance_export'),

    # RFQ URLs
    path('rfqs/', views.RFQListView.as_view(), name='rfq_list'),
    path('rfqs/export/', views.RFQExportView.as_view(), name='rfq_export_all'),
    path('rfqs/search/', views.RFQListView.as_view(), name='rfq_search'),
    path('rfqs/create/', views.RFQCreateView.as_view(), name='rfq_create'),
    path('rfqs/<uuid:pk>/', views.RFQDetailView.as_view(), name='rfq_detail'),
    path('rfqs/<uuid:pk>/edit/', views.RFQUpdateView.as_view(), name='rfq_edit'),
    path('rfqs/<uuid:pk>/delete/', views.RFQDeleteView.as_view(), name='rfq_delete'),
    path('rfqs/<uuid:pk>/duplicate/', views.RFQDuplicateView.as_view(), name='rfq_duplicate'),
    path('rfqs/<uuid:pk>/send/', views.RFQSendView.as_view(), name='rfq_send'),
    path('rfqs/<uuid:pk>/export/', views.RFQExportView.as_view(), name='rfq_export'),

    # Quote URLs
    path('quotes/', views.QuoteListView.as_view(), name='quote_list'),
    path('quotes/export/', views.QuoteExportView.as_view(), name='quote_export_all'),
    path('quotes/<uuid:pk>/', views.QuoteDetailView.as_view(), name='quote_detail'),
    path('quotes/<uuid:pk>/approve/', views.QuoteApproveView.as_view(), name='quote_approve'),
    path('quotes/<uuid:pk>/reject/', views.QuoteRejectView.as_view(), name='quote_reject'),

    # Analytics
    path('analytics/supplier-performance/', views.SupplierPerformanceView.as_view(), name='supplier_performance'),
    path('analytics/quote-comparison/', views.QuoteComparisonView.as_view(), name='quote_comparison'),

    # Dashboard
    path('dashboard/', views.ProcurementDashboardView.as_view(), name='dashboard'),
    path('', views.ProcurementDashboardView.as_view(), name='index'),
]
```

---

## 7. Templates Implementation

### Base Template Structure

```html
<!-- django_app/templates/procurement/base_procurement.html -->
{% extends "base_modern.html" %}
{% load static %}

{% block extra_css %}
<!-- Flatpickr CSS -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css">
<!-- Font Awesome -->
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
{% endblock %}

{% block content %}
<div class="min-h-screen bg-gradient-to-br from-gray-50 to-white">
    {% block procurement_content %}{% endblock %}
</div>
{% endblock %}

{% block extra_js %}
<!-- Flatpickr JS -->
<script src="https://cdn.jsdelivr.net/npm/flatpickr"></script>
<!-- Alpine.js -->
<script defer src="https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js"></script>
{% block page_scripts %}{% endblock %}
{% endblock %}
```

### Supplier List Template (Key Sections)

```html
<!-- django_app/templates/procurement/supplier_list.html -->
{% extends "procurement/base_procurement.html" %}

{% block procurement_content %}
<div class="container mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <!-- Header -->
    <div class="mb-8 flex justify-between items-center">
        <h1 class="text-3xl font-bold text-gray-900">Suppliers</h1>
        <a href="{% url 'procurement:supplier_create' %}" class="btn btn-primary">
            <i class="fas fa-plus mr-2"></i> Add Supplier
        </a>
    </div>

    <!-- Statistics Cards -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        <div class="bg-white rounded-lg shadow p-6">
            <div class="flex items-center">
                <div class="flex-shrink-0 bg-blue-500 rounded-md p-3">
                    <i class="fas fa-building text-white text-2xl"></i>
                </div>
                <div class="ml-5 w-0 flex-1">
                    <dl>
                        <dt class="text-sm font-medium text-gray-500 truncate">Total Suppliers</dt>
                        <dd class="text-lg font-semibold text-gray-900">{{ total_suppliers }}</dd>
                    </dl>
                </div>
            </div>
        </div>
        <!-- More stat cards... -->
    </div>

    <!-- Filters -->
    <div class="bg-white shadow rounded-lg mb-6">
        <div class="p-6">
            <form method="get" class="grid grid-cols-1 md:grid-cols-4 gap-4">
                <input type="text" name="search" placeholder="Search suppliers..."
                       class="form-input" value="{{ request.GET.search }}">
                <select name="type" class="form-select">
                    <option value="">All Types</option>
                    <option value="manufacturer">Manufacturer</option>
                    <option value="distributor">Distributor</option>
                    <option value="reseller">Reseller</option>
                </select>
                <select name="status" class="form-select">
                    <option value="">All Status</option>
                    <option value="active">Active</option>
                    <option value="inactive">Inactive</option>
                    <option value="pending_approval">Pending Approval</option>
                </select>
                <button type="submit" class="btn btn-primary">Filter</button>
            </form>
        </div>
    </div>

    <!-- Suppliers Table -->
    <div class="bg-white shadow rounded-lg overflow-hidden">
        <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
                <tr>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        <input type="checkbox" id="selectAll" class="form-checkbox">
                    </th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Name
                    </th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Type
                    </th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Contact
                    </th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Rating
                    </th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Status
                    </th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Actions
                    </th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
                {% for supplier in suppliers %}
                <tr class="hover:bg-gray-50">
                    <td class="px-6 py-4 whitespace-nowrap">
                        <input type="checkbox" class="form-checkbox supplier-checkbox" value="{{ supplier.id }}">
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap">
                        <div>
                            <div class="text-sm font-medium text-gray-900">{{ supplier.name }}</div>
                            <div class="text-sm text-gray-500">{{ supplier.code }}</div>
                        </div>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap">
                        <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-blue-100 text-blue-800">
                            {{ supplier.get_supplier_type_display }}
                        </span>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap">
                        <div class="text-sm text-gray-900">{{ supplier.primary_contact_name }}</div>
                        <div class="text-sm text-gray-500">{{ supplier.primary_contact_email }}</div>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap">
                        <div class="flex items-center">
                            {% for i in "12345"|make_list %}
                                {% if supplier.rating >= i|add:0 %}
                                    <i class="fas fa-star text-yellow-400"></i>
                                {% else %}
                                    <i class="far fa-star text-gray-300"></i>
                                {% endif %}
                            {% endfor %}
                            <span class="ml-2 text-sm text-gray-600">{{ supplier.rating|floatformat:1 }}</span>
                        </div>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap">
                        <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full
                            {% if supplier.status == 'active' %}bg-green-100 text-green-800
                            {% elif supplier.status == 'inactive' %}bg-gray-100 text-gray-800
                            {% elif supplier.status == 'pending_approval' %}bg-yellow-100 text-yellow-800
                            {% else %}bg-red-100 text-red-800{% endif %}">
                            {{ supplier.get_status_display }}
                        </span>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
                        <a href="{% url 'procurement:supplier_detail' supplier.pk %}" class="text-navy-600 hover:text-navy-900 mr-3">
                            <i class="fas fa-eye"></i>
                        </a>
                        <a href="{% url 'procurement:supplier_update' supplier.pk %}" class="text-blue-600 hover:text-blue-900 mr-3">
                            <i class="fas fa-edit"></i>
                        </a>
                        <button onclick="createRFQ('{{ supplier.pk }}')" class="text-green-600 hover:text-green-900 mr-3">
                            <i class="fas fa-file-alt"></i>
                        </button>
                        <a href="{% url 'procurement:supplier_individual_performance' supplier.pk %}" class="text-purple-600 hover:text-purple-900">
                            <i class="fas fa-chart-line"></i>
                        </a>
                    </td>
                </tr>
                {% empty %}
                <tr>
                    <td colspan="7" class="px-6 py-12 text-center text-gray-500">
                        No suppliers found. <a href="{% url 'procurement:supplier_create' %}" class="text-navy-600 hover:text-navy-900">Add your first supplier</a>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>

    <!-- Pagination -->
    {% if is_paginated %}
    <div class="bg-white px-4 py-3 flex items-center justify-between border-t border-gray-200 sm:px-6 mt-4">
        <!-- Pagination controls -->
    </div>
    {% endif %}
</div>
{% endblock %}

{% block page_scripts %}
<script>
// Select all checkbox
document.getElementById('selectAll').addEventListener('change', function(e) {
    const checkboxes = document.querySelectorAll('.supplier-checkbox');
    checkboxes.forEach(cb => cb.checked = e.target.checked);
});

// Create RFQ for supplier
function createRFQ(supplierId) {
    window.location.href = "{% url 'procurement:rfq_create' %}" + "?supplier=" + supplierId;
}

// View supplier performance
function viewPerformance(supplierId) {
    window.location.href = "{% url 'procurement:supplier_individual_performance' pk='00000000-0000-0000-0000-000000000000' %}".replace('00000000-0000-0000-0000-000000000000', supplierId);
}

// Export suppliers
function exportSuppliers() {
    window.location.href = "{% url 'procurement:supplier_export_all' %}";
}
</script>
{% endblock %}
```

---

## 8. JavaScript Functions

### Common JavaScript Utilities

```javascript
// django_app/static/js/procurement.js

// Date formatting
function formatDate(date) {
    const options = { year: 'numeric', month: 'short', day: 'numeric' };
    return new Date(date).toLocaleDateString('en-US', options);
}

// Format currency
function formatCurrency(amount, currency = 'USD') {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: currency
    }).format(amount);
}

// Debounce function for search
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Real-time search
function initializeSearch(inputId, searchUrl) {
    const searchInput = document.getElementById(inputId);
    const debouncedSearch = debounce((query) => {
        window.location.href = `${searchUrl}?search=${encodeURIComponent(query)}`;
    }, 500);

    searchInput.addEventListener('input', (e) => {
        debouncedSearch(e.target.value);
    });
}

// Status badge colors
const statusColors = {
    'draft': 'bg-gray-100 text-gray-800',
    'published': 'bg-blue-100 text-blue-800',
    'closed': 'bg-purple-100 text-purple-800',
    'awarded': 'bg-green-100 text-green-800',
    'cancelled': 'bg-red-100 text-red-800'
};

// Priority badge colors
const priorityColors = {
    'low': 'bg-gray-100 text-gray-800',
    'medium': 'bg-yellow-100 text-yellow-800',
    'high': 'bg-orange-100 text-orange-800',
    'urgent': 'bg-red-100 text-red-800'
};

// Initialize Flatpickr date pickers
function initializeDatePickers() {
    // Datetime picker
    flatpickr('.datetime-picker', {
        enableTime: true,
        dateFormat: 'Y-m-d H:i',
        altInput: true,
        altFormat: 'F j, Y at h:i K',
        minDate: 'today'
    });

    // Date picker
    flatpickr('.date-picker', {
        dateFormat: 'Y-m-d',
        altInput: true,
        altFormat: 'F j, Y',
        minDate: 'today'
    });
}

// Firefox compatibility fixes
const isFirefox = navigator.userAgent.toLowerCase().indexOf('firefox') > -1;

function applyFirefoxFixes() {
    if (isFirefox) {
        console.log('Applying Firefox compatibility fixes...');

        // Fix :has() selector issues
        document.querySelectorAll('.form-group').forEach(el => {
            if (el.querySelector('input[required]')) {
                el.classList.add('has-required');
            }
        });

        // Fix grid layouts
        document.querySelectorAll('.grid').forEach(el => {
            el.style.display = 'grid';
        });
    }
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', function() {
    initializeDatePickers();
    applyFirefoxFixes();
});
```

---

## 9. API Implementation

### Serializers

```python
# django_app/apps/procurement/api/serializers.py

from rest_framework import serializers
from ..models import Supplier, RFQ, Quote

class SupplierSerializer(serializers.ModelSerializer):
    performance_score = serializers.SerializerMethodField()
    recent_quotes_count = serializers.SerializerMethodField()

    class Meta:
        model = Supplier
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_performance_score(self, obj):
        return obj.calculate_performance_score()

    def get_recent_quotes_count(self, obj):
        return obj.get_recent_quotes().count()


class RFQSerializer(serializers.ModelSerializer):
    quotes_count = serializers.SerializerMethodField()
    days_remaining = serializers.ReadOnlyField()
    invited_supplier_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False
    )

    class Meta:
        model = RFQ
        fields = '__all__'
        read_only_fields = ['id', 'rfq_number', 'created_at', 'updated_at']

    def get_quotes_count(self, obj):
        return obj.quotes.count()

    def create(self, validated_data):
        supplier_ids = validated_data.pop('invited_supplier_ids', [])
        rfq = super().create(validated_data)

        if supplier_ids:
            suppliers = Supplier.objects.filter(id__in=supplier_ids)
            rfq.invited_suppliers.set(suppliers)
            rfq.suppliers.set(suppliers)

        return rfq
```

### ViewSets

```python
# django_app/apps/procurement/api/viewsets.py

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

class SupplierViewSet(viewsets.ModelViewSet):
    serializer_class = SupplierSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ['name', 'code', 'primary_contact_email']
    filterset_fields = ['status', 'supplier_type', 'risk_level']
    ordering_fields = ['name', 'created_at', 'rating']

    def get_queryset(self):
        return Supplier.objects.filter(
            organization=self.request.user.profile.organization
        )

    def perform_create(self, serializer):
        serializer.save(
            organization=self.request.user.profile.organization,
            created_by=self.request.user
        )


class RFQViewSet(viewsets.ModelViewSet):
    serializer_class = RFQSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return RFQ.objects.filter(
            organization=self.request.user.profile.organization
        ).prefetch_related('items', 'invited_suppliers')

    def perform_create(self, serializer):
        serializer.save(
            organization=self.request.user.profile.organization,
            created_by=self.request.user
        )

    @action(detail=True, methods=['post'])
    def send_to_suppliers(self, request, pk=None):
        rfq = self.get_object()
        supplier_ids = request.data.get('supplier_ids', [])

        if supplier_ids:
            suppliers = Supplier.objects.filter(id__in=supplier_ids)
            rfq.invited_suppliers.set(suppliers)

        rfq.publish(request.user)

        return Response({
            'status': 'success',
            'message': f'RFQ sent to {len(supplier_ids)} suppliers'
        })
```

---

## 10. Test Data Setup

### Management Command

```python
# django_app/apps/procurement/management/commands/load_test_data.py

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.procurement.models import RFQ, Supplier, Quote, QuoteItem
from apps.core.models import Organization
from datetime import datetime, timedelta
from decimal import Decimal
from django.utils import timezone

User = get_user_model()

class Command(BaseCommand):
    help = 'Load test data for procurement module'

    def handle(self, *args, **options):
        self.stdout.write("Loading test data for procurement module...")

        # Get or create user
        user, _ = User.objects.get_or_create(
            username='admin',
            defaults={'email': 'admin@example.com', 'is_staff': True, 'is_superuser': True}
        )

        # Get or create organization
        org, _ = Organization.objects.get_or_create(
            code='ORG001',
            defaults={'name': 'Test Organization'}
        )

        # Create suppliers
        suppliers_data = [
            {
                'name': 'ArcelorMittal Steel Solutions',
                'code': 'AMST001',
                'supplier_type': 'manufacturer',
                'address': '1 S Dearborn St, Chicago, IL 60603',
                'tax_id': '52-2142789',
                'payment_terms': 'NET30',
                'rating': Decimal('4.5'),
                'notes': 'Primary steel supplier'
            },
            {
                'name': 'Nucor Corporation',
                'code': 'NUC002',
                'supplier_type': 'manufacturer',
                'address': '1915 Rexford Rd, Charlotte, NC 28211',
                'tax_id': '13-1860817',
                'payment_terms': 'NET45',
                'rating': Decimal('4.7'),
                'notes': 'Specialized in rebar and sheet metal'
            },
            {
                'name': 'Fastenal Company',
                'code': 'FAST003',
                'supplier_type': 'distributor',
                'address': '2001 Theurer Blvd, Winona, MN 55987',
                'tax_id': '41-0948415',
                'payment_terms': 'NET15',
                'rating': Decimal('4.3'),
                'notes': 'Industrial supplies and fasteners'
            }
        ]

        created_suppliers = []
        for data in suppliers_data:
            supplier, created = Supplier.objects.get_or_create(
                organization=org,
                code=data['code'],
                defaults={**data, 'created_by': user}
            )
            created_suppliers.append(supplier)
            self.stdout.write(f"{'Created' if created else 'Exists'}: {supplier.name}")

        # Create RFQs
        rfqs_data = [
            {
                'title': 'Q1 2025 Steel Beam Procurement',
                'rfq_number': 'RFQ-2025-001',
                'description': 'Request for quotation for structural steel beams for Q1 2025.',
                'department': 'Procurement',
                'cost_center': 'CC-CONST-001',
                'deadline': timezone.now() + timedelta(days=14),
                'required_delivery_date': (timezone.now() + timedelta(days=60)).date(),
                'payment_terms': 'NET30',
                'delivery_terms': 'FOB Destination',
                'priority': 'high',
                'status': 'published',
                'evaluation_criteria': {'price': 40, 'quality': 30, 'delivery': 20, 'service': 10}
            },
            {
                'title': 'Industrial Fasteners Annual Contract',
                'rfq_number': 'RFQ-2025-002',
                'description': 'Annual contract for industrial fasteners.',
                'department': 'Operations',
                'cost_center': 'CC-OPS-002',
                'deadline': timezone.now() + timedelta(days=21),
                'required_delivery_date': (timezone.now() + timedelta(days=30)).date(),
                'payment_terms': 'NET45',
                'delivery_terms': 'DDP',
                'priority': 'medium',
                'status': 'published',
                'evaluation_criteria': {'price': 35, 'availability': 25, 'quality': 25, 'service': 15}
            }
        ]

        for data in rfqs_data:
            rfq, created = RFQ.objects.get_or_create(
                organization=org,
                rfq_number=data['rfq_number'],
                defaults={**data, 'created_by': user}
            )

            if created:
                # Add suppliers to RFQ
                rfq.invited_suppliers.set(created_suppliers[:2])
                rfq.suppliers.set(created_suppliers[:2])

            self.stdout.write(f"{'Created' if created else 'Exists'}: {rfq.title}")

        self.stdout.write(self.style.SUCCESS("Test data loaded successfully!"))
```

---

## 11. Integration Points

### Cross-Module Integration

```python
# Integration utilities

def create_rfq_from_supplier(supplier, user):
    """Create RFQ with pre-selected supplier"""
    rfq = RFQ.objects.create(
        organization=supplier.organization,
        rfq_number=generate_rfq_number(),
        title=f"RFQ for {supplier.name}",
        status='draft',
        deadline=timezone.now() + timedelta(days=30),
        created_by=user
    )
    rfq.invited_suppliers.add(supplier)
    return rfq


def calculate_supplier_metrics(supplier, period_days=90):
    """Calculate supplier performance metrics"""
    cutoff = timezone.now() - timedelta(days=period_days)

    quotes = supplier.quotes.filter(created_at__gte=cutoff)
    rfqs_invited = supplier.rfqs_invited.filter(created_at__gte=cutoff)

    metrics = {
        'response_rate': (quotes.count() / rfqs_invited.count() * 100) if rfqs_invited.count() > 0 else 0,
        'win_rate': (quotes.filter(status='accepted').count() / quotes.count() * 100) if quotes.count() > 0 else 0,
        'avg_quote_value': quotes.aggregate(Avg('total_amount'))['total_amount__avg'] or 0,
        'total_business': quotes.filter(status='accepted').aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    }

    return metrics


def compare_quotes(rfq):
    """Compare all quotes for an RFQ"""
    quotes = rfq.quotes.select_related('supplier').prefetch_related('items')

    comparison = []
    for quote in quotes:
        comparison.append({
            'supplier': quote.supplier,
            'total_amount': quote.total_amount,
            'lead_time': quote.lead_time_days,
            'payment_terms': quote.payment_terms,
            'items': list(quote.items.values('rfq_item_id', 'unit_price', 'price'))
        })

    # Sort by total amount
    comparison.sort(key=lambda x: x['total_amount'])

    return comparison
```

---

## 12. Security Considerations

### Security Implementation

```python
# Security decorators and mixins

from django.contrib.auth.decorators import login_required, permission_required
from django.views.decorators.csrf import csrf_protect
from django.utils.decorators import method_decorator

@method_decorator(csrf_protect, name='dispatch')
class SecureFormView(FormView):
    """Base view with CSRF protection"""
    pass


class OrganizationDataMixin:
    """Ensure data isolation by organization"""

    def get_queryset(self):
        qs = super().get_queryset()
        if hasattr(self.request.user, 'profile') and self.request.user.profile.organization:
            return qs.filter(organization=self.request.user.profile.organization)
        return qs.none()


class OwnershipRequiredMixin:
    """Ensure user owns the object"""

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if obj.created_by != self.request.user and not self.request.user.is_superuser:
            raise PermissionDenied
        return obj


# Input validation
def validate_supplier_code(code):
    """Validate supplier code format"""
    import re
    pattern = r'^[A-Z]{3,10}[0-9]{3,6}$'
    if not re.match(pattern, code):
        raise ValidationError('Invalid supplier code format')
    return code


def validate_rfq_number(number):
    """Validate RFQ number format"""
    import re
    pattern = r'^RFQ-[0-9]{8}-[0-9]{4}$'
    if not re.match(pattern, number):
        raise ValidationError('Invalid RFQ number format')
    return number
```

---

## Implementation Checklist

### Phase 1: Foundation
- [ ] Set up Django project structure
- [ ] Create procurement app
- [ ] Define models
- [ ] Run migrations
- [ ] Create base templates

### Phase 2: Suppliers Module
- [ ] Implement Supplier model
- [ ] Create supplier forms
- [ ] Build supplier views
- [ ] Design supplier templates
- [ ] Add supplier URLs
- [ ] Test supplier CRUD operations

### Phase 3: RFQs Module
- [ ] Implement RFQ model
- [ ] Create RFQ forms
- [ ] Build RFQ views
- [ ] Design RFQ templates
- [ ] Add RFQ URLs
- [ ] Implement RFQ duplication
- [ ] Test RFQ workflow

### Phase 4: Quote Management
- [ ] Implement Quote models
- [ ] Create quote submission forms
- [ ] Build quote comparison view
- [ ] Design quote templates
- [ ] Test quote workflow

### Phase 5: Integration
- [ ] Connect suppliers to RFQs
- [ ] Implement performance metrics
- [ ] Add cross-module navigation
- [ ] Test integration points

### Phase 6: API
- [ ] Create serializers
- [ ] Implement viewsets
- [ ] Configure API URLs
- [ ] Test API endpoints

### Phase 7: Testing & Deployment
- [ ] Load test data
- [ ] Perform end-to-end testing
- [ ] Fix browser compatibility issues
- [ ] Deploy to production

---

## Conclusion

This comprehensive implementation guide provides all the necessary components to replicate the Suppliers and RFQs modules. The modules are production-ready with:

- Complete CRUD operations
- Multi-tenant support
- Performance tracking
- Quote management
- Cross-browser compatibility
- RESTful APIs
- Comprehensive UI with CTAs

Follow the implementation checklist to systematically build these modules, ensuring all features are properly integrated and tested.