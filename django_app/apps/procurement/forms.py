from django import forms
from django.forms import ModelForm
from .models import Contract, Supplier, Quote, RFQ, Material, RFQItem


class ContractForm(ModelForm):
    """Contract form with Tailwind CSS styling"""
    
    class Meta:
        model = Contract
        fields = [
            'contract_number', 'title', 'contract_type', 'supplier', 'quote',
            'start_date', 'end_date', 'total_value', 'currency', 'payment_terms',
            'terms_and_conditions', 'status'
        ]
        
        widgets = {
            'contract_number': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors',
                'placeholder': 'Enter contract number'
            }),
            'title': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors',
                'placeholder': 'Enter contract title'
            }),
            'contract_type': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors bg-white'
            }),
            'supplier': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors bg-white'
            }),
            'quote': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors bg-white'
            }),
            'start_date': forms.DateInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors',
                'type': 'date'
            }),
            'end_date': forms.DateInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors',
                'type': 'date'
            }),
            'total_value': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors',
                'placeholder': '0.00',
                'step': '0.01'
            }),
            'currency': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors',
                'placeholder': 'USD'
            }),
            'payment_terms': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors',
                'placeholder': 'e.g., Net 30'
            }),
            'terms_and_conditions': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors resize-vertical',
                'rows': 5,
                'placeholder': 'Enter terms and conditions'
            }),
            'status': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors bg-white'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add 'required' attribute to required fields and handle error styling
        for field_name, field in self.fields.items():
            if field.required:
                field.widget.attrs['required'] = 'required'
            
            # Add error styling classes if field has errors
            if hasattr(self, 'errors') and field_name in self.errors:
                current_class = field.widget.attrs.get('class', '')
                # Replace border-gray-300 with border-red-300 for error state
                error_class = current_class.replace('border-gray-300', 'border-red-300 border-red-500')
                field.widget.attrs['class'] = error_class


class RFQForm(ModelForm):
    """RFQ form with Tailwind CSS styling"""

    class Meta:
        model = RFQ
        fields = [
            'title', 'rfq_number', 'description', 'department', 'cost_center',
            'deadline', 'required_delivery_date',
            'payment_terms', 'delivery_terms', 'terms_and_conditions',
            'priority', 'public_rfq', 'evaluation_criteria', 'status'
        ]

        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors',
                'placeholder': 'Enter RFQ title',
                'required': True
            }),
            'rfq_number': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors',
                'placeholder': 'RFQ number will be auto-generated',
                'readonly': True
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors resize-vertical',
                'rows': 5,
                'placeholder': 'Describe the requirements in detail',
                'required': True
            }),
            'department': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors',
                'placeholder': 'Enter department name'
            }),
            'cost_center': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors',
                'placeholder': 'Enter cost center'
            }),
            'deadline': forms.DateTimeInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors',
                'type': 'datetime-local',
                'required': True
            }),
            'required_delivery_date': forms.DateInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors',
                'type': 'date'
            }),
            'payment_terms': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors',
                'placeholder': 'e.g., Net 30, 2/10 Net 30'
            }),
            'delivery_terms': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors',
                'placeholder': 'e.g., FOB, CIF, DDP'
            }),
            'terms_and_conditions': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors resize-vertical',
                'rows': 4,
                'placeholder': 'Enter additional terms and conditions'
            }),
            'priority': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors bg-white'
            }),
            'public_rfq': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-navy-600 focus:ring-navy-500 border-gray-300 rounded'
            }),
            'evaluation_criteria': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors resize-vertical',
                'rows': 3,
                'placeholder': 'Enter evaluation criteria (optional)'
            }),
            'status': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors bg-white'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Auto-generate RFQ number if creating new RFQ
        if not self.instance.pk:
            from django.utils import timezone
            import random
            timestamp = timezone.now().strftime('%Y%m%d')
            random_suffix = str(random.randint(1000, 9999))
            self.fields['rfq_number'].initial = f'RFQ-{timestamp}-{random_suffix}'

        # Handle JSONField for evaluation_criteria
        if self.instance.pk and self.instance.evaluation_criteria:
            import json
            if isinstance(self.instance.evaluation_criteria, dict):
                self.fields['evaluation_criteria'].initial = json.dumps(self.instance.evaluation_criteria, indent=2)


class SupplierForm(ModelForm):
    """Supplier form with Tailwind CSS styling"""
    
    class Meta:
        model = Supplier
        fields = [
            'name', 'code', 'legal_name', 'tax_id', 'website',
            'primary_contact_name', 'primary_contact_email', 'primary_contact_phone',
            'address', 'country', 'region', 'supplier_type', 'categories',
            'payment_terms', 'currency', 'credit_limit', 'status'
        ]
        
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors',
                'placeholder': 'Enter supplier name'
            }),
            'code': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors',
                'placeholder': 'Enter supplier code'
            }),
            'legal_name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors',
                'placeholder': 'Enter legal business name'
            }),
            'tax_id': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors',
                'placeholder': 'Enter tax ID'
            }),
            'website': forms.URLInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors',
                'placeholder': 'https://example.com'
            }),
            'primary_contact_name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors',
                'placeholder': 'Contact person name'
            }),
            'primary_contact_email': forms.EmailInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors',
                'placeholder': 'contact@example.com'
            }),
            'primary_contact_phone': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors',
                'placeholder': '+1 234 567 8900'
            }),
            'address': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors resize-vertical',
                'rows': 3,
                'placeholder': 'Enter full address'
            }),
            'country': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors',
                'placeholder': 'Country'
            }),
            'region': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors',
                'placeholder': 'State/Province/Region'
            }),
            'supplier_type': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors bg-white'
            }),
            'categories': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors resize-vertical',
                'rows': 2,
                'placeholder': 'Enter categories (comma-separated)'
            }),
            'payment_terms': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors',
                'placeholder': 'e.g., Net 30'
            }),
            'currency': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors',
                'placeholder': 'USD'
            }),
            'credit_limit': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors',
                'placeholder': '0.00',
                'step': '0.01'
            }),
            'status': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors bg-white'
            })
        }


class QuoteForm(ModelForm):
    """Quote form with Tailwind CSS styling"""
    
    class Meta:
        model = Quote
        fields = [
            'rfq', 'supplier', 'quote_number', 'total_amount',
            'validity_period', 'delivery_terms', 'payment_terms',
            'supplier_notes', 'internal_notes', 'status'
        ]
        
        widgets = {
            'rfq': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors bg-white'
            }),
            'supplier': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors bg-white'
            }),
            'quote_number': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors',
                'placeholder': 'Quote number'
            }),
            'total_amount': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors',
                'placeholder': '0.00',
                'step': '0.01'
            }),
            'validity_period': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors',
                'placeholder': 'Days'
            }),
            'delivery_terms': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors',
                'placeholder': 'Enter delivery terms'
            }),
            'payment_terms': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors',
                'placeholder': 'Enter payment terms'
            }),
            'supplier_notes': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors resize-vertical',
                'rows': 3,
                'placeholder': 'Notes from supplier'
            }),
            'internal_notes': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors resize-vertical',
                'rows': 3,
                'placeholder': 'Internal notes'
            }),
            'status': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-navy-500 focus:ring-1 focus:ring-navy-500 transition-colors bg-white'
            })
        }