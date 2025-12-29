"""
Procurement app admin interface
"""
from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Avg, Sum
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    Supplier, RFQ, Quote, RFQItem, QuoteItem,
    SupplierContact, SupplierDocument, Contract
)


class SupplierContactInline(admin.TabularInline):
    """Supplier contact inline"""
    model = SupplierContact
    extra = 1
    fields = ['name', 'email', 'phone', 'role', 'is_primary']


class SupplierDocumentInline(admin.TabularInline):
    """Supplier document inline"""
    model = SupplierDocument
    extra = 0
    fields = ['document_type', 'document', 'uploaded_at']
    readonly_fields = ['uploaded_at']


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    """Supplier admin interface"""
    list_display = [
        'name', 'category', 'status', 'country',
        'rfq_count', 'quote_count', 'success_rate', 'created_at'
    ]
    list_filter = [
        'organization', 'status', 'category', 'country',
        'payment_terms', 'created_at'
    ]
    search_fields = [
        'name', 'contact_email', 'contact_person',
        'tax_id', 'address', 'city'
    ]
    readonly_fields = [
        'created_at', 'updated_at', 'rfq_count',
        'quote_count', 'success_rate'
    ]
    
    inlines = [SupplierContactInline, SupplierDocumentInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'category', 'status', 'organization')
        }),
        ('Contact Information', {
            'fields': (
                'contact_person', 'contact_email', 'contact_phone',
                'website', 'address', 'city', 'postal_code', 'country'
            )
        }),
        ('Business Information', {
            'fields': ('tax_id', 'registration_number', 'industry')
        }),
        ('Terms & Conditions', {
            'fields': ('payment_terms', 'delivery_terms', 'minimum_order_value')
        }),
        ('Assessment', {
            'fields': ('quality_rating', 'delivery_rating', 'service_rating')
        }),
        ('Additional Information', {
            'fields': ('notes', 'tags'),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('rfq_count', 'quote_count', 'success_rate'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def rfq_count(self, obj):
        """Display count of RFQs sent to this supplier"""
        count = obj.rfqs.count()
        return format_html('<span style="color: #006eb8;">{}</span>', count)
    rfq_count.short_description = 'RFQs'
    
    def quote_count(self, obj):
        """Display count of quotes from this supplier"""
        count = obj.quotes.count()
        return format_html('<span style="color: #28a745;">{}</span>', count)
    quote_count.short_description = 'Quotes'
    
    def success_rate(self, obj):
        """Display quote success rate"""
        total_quotes = obj.quotes.count()
        approved_quotes = obj.quotes.filter(status='approved').count()
        
        if total_quotes > 0:
            rate = (approved_quotes / total_quotes) * 100
            color = '#28a745' if rate >= 50 else '#fd7e14' if rate >= 25 else '#dc3545'
            return format_html(
                '<span style="color: {};">{:.1f}%</span>',
                color, rate
            )
        return '-'
    success_rate.short_description = 'Success Rate'
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related(
            'organization', 'created_by'
        ).prefetch_related('rfqs', 'quotes')


class RFQItemInline(admin.TabularInline):
    """RFQ item inline"""
    model = RFQItem
    extra = 1
    fields = [
        'material', 'quantity', 'unit_of_measure',
        'estimated_price', 'delivery_date', 'specifications'
    ]


@admin.register(RFQ)
class RFQAdmin(admin.ModelAdmin):
    """RFQ admin interface"""
    list_display = [
        'title', 'status', 'supplier_count', 'quote_count',
        'response_deadline', 'created_by', 'created_at'
    ]
    list_filter = [
        'organization', 'status', 'response_deadline',
        'delivery_date', 'created_at'
    ]
    search_fields = [
        'title', 'description', 'created_by__username'
    ]
    readonly_fields = [
        'created_at', 'updated_at', 'supplier_count', 'quote_count'
    ]
    
    inlines = [RFQItemInline]
    
    fieldsets = (
        ('RFQ Information', {
            'fields': ('title', 'description', 'status', 'organization')
        }),
        ('Timeline', {
            'fields': ('response_deadline', 'delivery_date')
        }),
        ('Delivery', {
            'fields': ('delivery_location', 'delivery_terms')
        }),
        ('Terms & Conditions', {
            'fields': ('terms_conditions', 'payment_terms')
        }),
        ('Statistics', {
            'fields': ('supplier_count', 'quote_count'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def supplier_count(self, obj):
        """Display count of suppliers for this RFQ"""
        count = obj.suppliers.count()
        return format_html('<span style="color: #006eb8;">{}</span>', count)
    supplier_count.short_description = 'Suppliers'
    
    def quote_count(self, obj):
        """Display count of quotes for this RFQ"""
        count = obj.quotes.count()
        return format_html('<span style="color: #28a745;">{}</span>', count)
    quote_count.short_description = 'Quotes Received'
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related(
            'organization', 'created_by'
        ).prefetch_related('suppliers', 'quotes')


class QuoteItemInline(admin.TabularInline):
    """Quote item inline"""
    model = QuoteItem
    extra = 0
    fields = [
        'rfq_item', 'unit_price', 'quantity', 'total_price',
        'delivery_days', 'notes'
    ]
    readonly_fields = ['total_price']
    
    def total_price(self, obj):
        """Calculate total price for the item"""
        if obj.unit_price and obj.quantity:
            return obj.unit_price * obj.quantity
        return 0
    total_price.short_description = 'Total Price'


@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin):
    """Quote admin interface"""
    list_display = [
        'rfq_title', 'supplier', 'total_value', 'status',
        'submitted_at', 'response_time_days'
    ]
    list_filter = [
        'organization', 'status', 'submitted_at',
        'rfq__status', 'supplier__category'
    ]
    search_fields = [
        'rfq__title', 'supplier__name', 'reference_number'
    ]
    readonly_fields = [
        'submitted_at', 'approved_at', 'rejected_at',
        'response_time_days', 'total_value'
    ]
    
    inlines = [QuoteItemInline]
    
    fieldsets = (
        ('Quote Information', {
            'fields': ('rfq', 'supplier', 'reference_number', 'status')
        }),
        ('Pricing', {
            'fields': ('total_value', 'currency', 'validity_period')
        }),
        ('Terms', {
            'fields': ('payment_terms', 'delivery_terms', 'warranty_terms')
        }),
        ('Timeline', {
            'fields': (
                'submitted_at', 'response_time_days',
                'approved_at', 'rejected_at'
            ),
            'classes': ('collapse',)
        }),
        ('Approval', {
            'fields': (
                'approved_by', 'rejected_by', 'rejection_reason'
            ),
            'classes': ('collapse',)
        }),
        ('Additional Information', {
            'fields': ('notes', 'attachments'),
            'classes': ('collapse',)
        })
    )
    
    def rfq_title(self, obj):
        """Display RFQ title with link"""
        if obj.rfq:
            url = reverse('admin:procurement_rfq_change', args=[obj.rfq.pk])
            return format_html(
                '<a href="{}">{}</a>',
                url, obj.rfq.title[:50]
            )
        return '-'
    rfq_title.short_description = 'RFQ'
    
    def response_time_days(self, obj):
        """Calculate response time in days"""
        if obj.rfq and obj.submitted_at:
            delta = obj.submitted_at.date() - obj.rfq.created_at.date()
            return delta.days
        return '-'
    response_time_days.short_description = 'Response Time (Days)'
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related(
            'rfq', 'supplier', 'organization', 'approved_by', 'rejected_by'
        ).prefetch_related('items')


@admin.register(RFQItem)
class RFQItemAdmin(admin.ModelAdmin):
    """RFQ Item admin interface"""
    list_display = [
        'rfq', 'material', 'quantity', 'unit_of_measure',
        'estimated_price', 'delivery_date'
    ]
    list_filter = [
        'rfq__organization', 'unit_of_measure', 'delivery_date'
    ]
    search_fields = [
        'rfq__title', 'material__name', 'specifications'
    ]
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related(
            'rfq', 'material'
        )


@admin.register(QuoteItem)
class QuoteItemAdmin(admin.ModelAdmin):
    """Quote Item admin interface"""
    list_display = [
        'quote', 'rfq_item_material', 'unit_price', 'quantity',
        'total_price', 'delivery_days'
    ]
    list_filter = [
        'quote__organization', 'quote__status'
    ]
    search_fields = [
        'quote__rfq__title', 'rfq_item__material__name'
    ]
    readonly_fields = ['total_price']
    
    def rfq_item_material(self, obj):
        """Display material name from RFQ item"""
        if obj.rfq_item and obj.rfq_item.material:
            return obj.rfq_item.material.name
        return '-'
    rfq_item_material.short_description = 'Material'
    
    def total_price(self, obj):
        """Calculate total price for the item"""
        if obj.unit_price and obj.quantity:
            return obj.unit_price * obj.quantity
        return 0
    total_price.short_description = 'Total Price'
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related(
            'quote', 'rfq_item', 'rfq_item__material'
        )


@admin.register(SupplierContact)
class SupplierContactAdmin(admin.ModelAdmin):
    """Supplier Contact admin interface"""
    list_display = ['name', 'supplier', 'email', 'phone', 'role', 'is_primary']
    list_filter = ['supplier__organization', 'role', 'is_primary']
    search_fields = ['name', 'email', 'phone', 'supplier__name']
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related('supplier')


@admin.register(SupplierDocument)
class SupplierDocumentAdmin(admin.ModelAdmin):
    """Supplier Document admin interface"""
    list_display = [
        'supplier', 'document_type', 'document_name',
        'file_size', 'uploaded_at'
    ]
    list_filter = [
        'supplier__organization', 'document_type', 'uploaded_at'
    ]
    search_fields = ['supplier__name', 'document_type']
    readonly_fields = ['uploaded_at', 'file_size']
    
    def document_name(self, obj):
        """Display document file name"""
        if obj.document:
            return obj.document.name.split('/')[-1]
        return '-'
    document_name.short_description = 'File Name'
    
    def file_size(self, obj):
        """Display file size"""
        if obj.document:
            size = obj.document.size
            if size < 1024:
                return f'{size} bytes'
            elif size < 1024*1024:
                return f'{size/1024:.1f} KB'
            else:
                return f'{size/(1024*1024):.1f} MB'
        return '-'
    file_size.short_description = 'File Size'
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related('supplier')


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    """Contract admin interface"""
    list_display = [
        'title', 'supplier', 'contract_type', 'status',
        'start_date', 'end_date', 'total_value'
    ]
    list_filter = [
        'organization', 'contract_type', 'status',
        'start_date', 'end_date'
    ]
    search_fields = [
        'title', 'supplier__name', 'contract_number'
    ]
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Contract Information', {
            'fields': (
                'title', 'contract_number', 'supplier',
                'contract_type', 'status'
            )
        }),
        ('Timeline', {
            'fields': ('start_date', 'end_date', 'auto_renewal')
        }),
        ('Financial', {
            'fields': ('total_value', 'currency', 'payment_schedule')
        }),
        ('Terms', {
            'fields': ('terms_conditions', 'sla_terms')
        }),
        ('Documents', {
            'fields': ('contract_document', 'signed_document')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related(
            'supplier', 'organization'
        )