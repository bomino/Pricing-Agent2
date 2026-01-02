"""
Procurement views for supplier management and RFQ processes
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView, View
)
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Avg, Count, Sum, F
from django.utils import timezone
from django.contrib import messages
from django.urls import reverse_lazy
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Supplier, RFQ, Quote, RFQItem, QuoteItem, Contract
from .api.serializers import SupplierSerializer, RFQSerializer, QuoteSerializer
from .forms import ContractForm, RFQForm, SupplierForm, QuoteForm
from apps.pricing.models import Category
from apps.core.rbac import RoleRequiredMixin, Role
from apps.accounts.models import UserProfile
from apps.core.mixins import OrganizationRequiredMixin, get_user_organization
from datetime import datetime, timedelta
import json


class SupplierListView(OrganizationRequiredMixin, ListView):
    """List suppliers"""
    model = Supplier
    template_name = 'procurement/supplier_list.html'
    context_object_name = 'suppliers'
    paginate_by = 20

    def get_queryset(self):
        # Get organization from user profile if it exists
        organization = self.get_user_organization()
        if not organization:
            return Supplier.objects.none()

        # Start with all suppliers for this organization
        queryset = Supplier.objects.filter(
            organization=organization
        ).order_by('name')

        # Filter by status if provided
        status_filter = self.request.GET.get('status')
        if status_filter and status_filter != 'all':
            queryset = queryset.filter(status=status_filter)

        # Filter by supplier type if provided
        type_filter = self.request.GET.get('type')
        if type_filter and type_filter != 'all':
            queryset = queryset.filter(supplier_type=type_filter)

        # Filter by risk level if provided
        risk_filter = self.request.GET.get('risk')
        if risk_filter and risk_filter != 'all':
            queryset = queryset.filter(risk_level=risk_filter)

        # Add search functionality
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(primary_contact_email__icontains=search) |
                Q(code__icontains=search)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = self.get_user_organization()

        # Get counts for all suppliers (not just filtered)
        all_suppliers = Supplier.objects.filter(organization=organization)
        context['total_suppliers'] = all_suppliers.count()
        context['active_suppliers'] = all_suppliers.filter(status='active').count()
        context['avg_rating'] = all_suppliers.filter(rating__gt=0).aggregate(avg=Avg('rating'))['avg'] or 0
        context['categories_count'] = Category.objects.filter(organization=organization, is_active=True).count()

        # Pass current filter values to template
        context['current_status'] = self.request.GET.get('status', 'all')
        context['current_type'] = self.request.GET.get('type', 'all')
        context['current_risk'] = self.request.GET.get('risk', 'all')
        context['current_search'] = self.request.GET.get('search', '')

        return context


class SupplierDetailView(OrganizationRequiredMixin, DetailView):
    """Supplier detail view with performance metrics"""
    model = Supplier
    template_name = 'procurement/supplier_detail.html'
    context_object_name = 'supplier'
    
    def get_queryset(self):
        return Supplier.objects.filter(
            organization=self.get_user_organization()
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get recent RFQs sent to this supplier
        context['recent_rfqs'] = RFQ.objects.filter(
            invited_suppliers=self.object
        ).order_by('-created_at')[:10]
        
        # Get supplier performance metrics
        quotes = Quote.objects.filter(
            supplier=self.object,
            created_at__gte=timezone.now() - timezone.timedelta(days=90)
        )
        
        performance_metrics = {
            'total_quotes': quotes.count(),
            'approved_quotes': quotes.filter(status='approved').count(),
            'avg_response_time': 'N/A',  # Calculate based on RFQ to Quote timing
            'quote_acceptance_rate': 0
        }
        
        if performance_metrics['total_quotes'] > 0:
            performance_metrics['quote_acceptance_rate'] = round(
                (performance_metrics['approved_quotes'] / performance_metrics['total_quotes']) * 100, 2
            )
        
        context['performance_metrics'] = performance_metrics
        
        return context


class SupplierCreateView(OrganizationRequiredMixin, CreateView):
    """Create new supplier"""
    model = Supplier
    form_class = SupplierForm
    template_name = 'procurement/supplier_form.html'
    
    def form_valid(self, form):
        form.instance.organization = self.get_user_organization()
        form.instance.created_by = self.request.user
        # Generate supplier code if not provided
        if not form.instance.code:
            import random
            form.instance.code = f'SUP-{timezone.now().strftime("%Y%m%d")}-{random.randint(1000, 9999)}'
        messages.success(self.request, f'Supplier "{form.instance.name}" created successfully.')
        return super().form_valid(form)


class SupplierUpdateView(OrganizationRequiredMixin, UpdateView):
    """Update supplier"""
    model = Supplier
    form_class = SupplierForm
    template_name = 'procurement/supplier_form.html'
    
    def get_queryset(self):
        return Supplier.objects.filter(
            organization=self.get_user_organization()
        )
    
    def form_valid(self, form):
        messages.success(self.request, f'Supplier "{form.instance.name}" updated successfully.')
        return super().form_valid(form)


class RFQListView(OrganizationRequiredMixin, ListView):
    """List RFQs"""
    model = RFQ
    template_name = 'procurement/rfq_list.html'
    context_object_name = 'rfqs'
    paginate_by = 20

    def get_queryset(self):
        organization = self.get_user_organization()
        if not organization:
            return RFQ.objects.none()

        queryset = RFQ.objects.filter(
            organization=organization
        ).order_by('-created_at')

        # Apply filters
        status_filter = self.request.GET.get('status')
        if status_filter and status_filter != 'all':
            queryset = queryset.filter(status=status_filter)

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(rfq_number__icontains=search) |
                Q(title__icontains=search) |
                Q(description__icontains=search)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = self.get_user_organization()

        # Get all RFQs for stats (not filtered)
        all_rfqs = RFQ.objects.filter(organization=organization)

        # Stats
        context['total_rfqs'] = all_rfqs.count()
        context['open_rfqs'] = all_rfqs.filter(status__in=['open', 'published']).count()
        context['draft_rfqs'] = all_rfqs.filter(status='draft').count()
        context['awarded_rfqs'] = all_rfqs.filter(status='awarded').count()

        # Count pending quotes (quotes in under_review status for this org's RFQs)
        context['pending_quotes'] = Quote.objects.filter(
            organization=organization,
            status='under_review'
        ).count()

        # Count unique suppliers invited across all RFQs
        context['total_suppliers'] = Supplier.objects.filter(
            organization=organization,
            invited_rfqs__isnull=False
        ).distinct().count()

        # Pass filter values
        context['current_status'] = self.request.GET.get('status', 'all')
        context['current_search'] = self.request.GET.get('search', '')

        return context


class RFQDetailView(OrganizationRequiredMixin, DetailView):
    """RFQ detail view with items and quotes"""
    model = RFQ
    template_name = 'procurement/rfq_detail.html'
    context_object_name = 'rfq'
    
    def get_queryset(self):
        return RFQ.objects.filter(
            organization=self.get_user_organization()
        ).prefetch_related('items', 'invited_suppliers', 'quotes')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get RFQ items
        context['rfq_items'] = self.object.items.all()
        
        # Get quotes for this RFQ
        context['quotes'] = Quote.objects.filter(
            rfq=self.object
        ).select_related('supplier').order_by('-created_at')
        
        return context


class RFQCreateView(OrganizationRequiredMixin, CreateView):
    """Create new RFQ"""
    model = RFQ
    form_class = RFQForm
    template_name = 'procurement/rfq_form.html'  # Using standard template

    def get_initial(self):
        """Pre-populate supplier if provided in query params"""
        initial = super().get_initial()
        supplier_id = self.request.GET.get('supplier')
        if supplier_id:
            try:
                # Get supplier from the same organization
                supplier = Supplier.objects.get(
                    id=supplier_id,
                    organization=self.get_user_organization()
                )
                # Pre-select suppliers in the form
                initial['suppliers'] = [supplier]
            except (Supplier.DoesNotExist, ValueError):
                pass
        return initial

    def form_valid(self, form):
        form.instance.organization = self.get_user_organization()
        form.instance.created_by = self.request.user
        # Generate RFQ number if not set
        if not form.instance.rfq_number:
            import random
            form.instance.rfq_number = f'RFQ-{timezone.now().strftime("%Y%m%d")}-{random.randint(1000, 9999)}'
        messages.success(self.request, f'RFQ "{form.instance.title}" created successfully.')
        return super().form_valid(form)


class RFQUpdateView(OrganizationRequiredMixin, UpdateView):
    """Update RFQ"""
    model = RFQ
    form_class = RFQForm
    template_name = 'procurement/rfq_form.html'  # Using standard template
    
    def get_queryset(self):
        return RFQ.objects.filter(
            organization=self.get_user_organization()
        )
    
    def form_valid(self, form):
        messages.success(self.request, f'RFQ "{form.instance.title}" updated successfully.')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_edit'] = True
        context['rfq'] = self.object
        return context


class RFQDeleteView(OrganizationRequiredMixin, DeleteView):
    """Delete RFQ"""
    model = RFQ
    template_name = 'procurement/rfq_confirm_delete.html'
    success_url = reverse_lazy('procurement:rfq_list')
    
    def get_queryset(self):
        return RFQ.objects.filter(
            organization=self.get_user_organization(),
            status='draft'  # Only allow deletion of draft RFQs
        )
    
    def delete(self, request, *args, **kwargs):
        rfq = self.get_object()
        messages.success(request, f'RFQ "{rfq.title}" has been deleted.')
        return super().delete(request, *args, **kwargs)


class RFQDuplicateView(OrganizationRequiredMixin, DetailView):
    """Duplicate RFQ view"""
    model = RFQ

    def get_queryset(self):
        return RFQ.objects.filter(
            organization=self.get_user_organization()
        )

    def get(self, request, *args, **kwargs):
        """Handle RFQ duplication"""
        original_rfq = self.get_object()

        # Create a duplicate RFQ
        duplicated_rfq = RFQ.objects.create(
            organization=self.get_user_organization(),
            title=f"Copy of {original_rfq.title}",
            description=original_rfq.description,
            department=original_rfq.department,
            cost_center=original_rfq.cost_center,
            payment_terms=original_rfq.payment_terms,
            delivery_terms=original_rfq.delivery_terms,
            terms_and_conditions=original_rfq.terms_and_conditions,
            priority=original_rfq.priority,
            public_rfq=original_rfq.public_rfq,
            evaluation_criteria=original_rfq.evaluation_criteria,
            attachments=original_rfq.attachments,
            status='draft',  # Set as draft for editing
            deadline=timezone.now() + timezone.timedelta(days=30),  # Set new deadline 30 days from now
            required_delivery_date=original_rfq.required_delivery_date if original_rfq.required_delivery_date and original_rfq.required_delivery_date > timezone.now().date() else None,
            created_by=request.user
        )

        # Generate new RFQ number
        duplicated_rfq.rfq_number = f"RFQ-{duplicated_rfq.id.hex[:8].upper()}"
        duplicated_rfq.save()

        # Copy RFQ items
        for item in original_rfq.items.all():
            RFQItem.objects.create(
                rfq=duplicated_rfq,
                material=item.material,
                quantity=item.quantity,
                unit_of_measure=item.unit_of_measure,
                specifications=item.specifications,
                notes=item.notes,
                required_delivery_date=item.required_delivery_date if item.required_delivery_date and item.required_delivery_date > timezone.now().date() else None,
                delivery_location=item.delivery_location,
                budget_estimate=item.budget_estimate,
                last_purchase_price=item.last_purchase_price
            )

        # Copy invited suppliers
        duplicated_rfq.invited_suppliers.set(original_rfq.invited_suppliers.all())

        messages.success(request, f'RFQ "{original_rfq.title}" has been duplicated successfully!')

        # Redirect to edit the duplicated RFQ
        return redirect('procurement:rfq_edit', pk=duplicated_rfq.pk)


class RFQSendView(OrganizationRequiredMixin, TemplateView):
    """Send RFQ to suppliers"""
    template_name = 'procurement/rfq_send.html'
    
    def post(self, request, pk):
        rfq = get_object_or_404(
            RFQ,
            pk=pk,
            organization=get_user_organization(request.user)
        )
        
        # This would typically send emails to suppliers
        # For now, just update the status
        rfq.status = 'published'
        rfq.save()
        
        messages.success(request, f'RFQ "{rfq.title}" sent to suppliers successfully.')
        return JsonResponse({'status': 'success'})


class QuoteListView(OrganizationRequiredMixin, ListView):
    """List quotes"""
    model = Quote
    template_name = 'procurement/quote_list.html'
    context_object_name = 'quotes'
    paginate_by = 20

    def get_queryset(self):
        organization = self.get_user_organization()
        if not organization:
            return Quote.objects.none()

        queryset = Quote.objects.filter(
            organization=organization
        ).select_related('rfq', 'supplier').order_by('-created_at')

        # Apply filters
        status_filter = self.request.GET.get('status')
        if status_filter and status_filter != 'all':
            queryset = queryset.filter(status=status_filter)

        rfq_filter = self.request.GET.get('rfq')
        if rfq_filter and rfq_filter != 'all':
            queryset = queryset.filter(rfq_id=rfq_filter)

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(quote_number__icontains=search) |
                Q(supplier__name__icontains=search) |
                Q(rfq__rfq_number__icontains=search)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = self.get_user_organization()

        # Get all quotes for stats (not filtered)
        all_quotes = Quote.objects.filter(organization=organization)

        # Stats
        context['total_quotes'] = all_quotes.count()
        context['under_review'] = all_quotes.filter(status='under_review').count()
        context['approved_quotes'] = all_quotes.filter(status__in=['accepted', 'approved']).count()
        context['total_value'] = all_quotes.aggregate(total=Sum('total_amount'))['total'] or 0

        # Calculate avg savings (comparing to RFQ estimated amounts if available)
        # For now, calculate based on quotes with scores
        scored_quotes = all_quotes.filter(commercial_score__isnull=False)
        if scored_quotes.exists():
            context['avg_savings'] = scored_quotes.aggregate(avg=Avg('commercial_score'))['avg'] or 0
        else:
            context['avg_savings'] = 0

        # Pass filter values
        context['current_status'] = self.request.GET.get('status', 'all')
        context['current_rfq'] = self.request.GET.get('rfq', 'all')
        context['current_search'] = self.request.GET.get('search', '')

        # Get RFQs for filter dropdown
        context['rfqs'] = RFQ.objects.filter(organization=organization).order_by('-created_at')[:50]

        return context


class QuoteDetailView(OrganizationRequiredMixin, DetailView):
    """Quote detail view with items"""
    model = Quote
    template_name = 'procurement/quote_detail.html'
    context_object_name = 'quote'
    
    def get_queryset(self):
        return Quote.objects.filter(
            organization=self.get_user_organization()
        ).select_related('rfq', 'supplier').prefetch_related('items')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get quote items
        context['quote_items'] = self.object.items.all()
        
        # Calculate total quote value
        context['total_value'] = sum(
            item.unit_price * item.quantity for item in context['quote_items']
        )
        
        return context


class QuoteApproveView(OrganizationRequiredMixin, TemplateView):
    """Approve quote"""
    
    def post(self, request, pk):
        quote = get_object_or_404(
            Quote,
            pk=pk,
            organization=get_user_organization(request.user)
        )
        
        quote.status = 'approved'
        quote.approved_by = request.user
        quote.approved_at = timezone.now()
        quote.save()
        
        messages.success(request, f'Quote from {quote.supplier.name} approved successfully.')
        return JsonResponse({'status': 'success'})


class QuoteRejectView(OrganizationRequiredMixin, TemplateView):
    """Reject quote"""
    
    def post(self, request, pk):
        quote = get_object_or_404(
            Quote,
            pk=pk,
            organization=get_user_organization(request.user)
        )
        
        rejection_reason = request.POST.get('rejection_reason', '')
        
        quote.status = 'rejected'
        quote.rejection_reason = rejection_reason
        quote.rejected_by = request.user
        quote.rejected_at = timezone.now()
        quote.save()
        
        messages.info(request, f'Quote from {quote.supplier.name} rejected.')
        return JsonResponse({'status': 'success'})


class ContractListView(OrganizationRequiredMixin, ListView):
    """List all contracts"""
    model = Contract
    template_name = 'procurement/contract_list.html'
    context_object_name = 'contracts'
    paginate_by = 20
    
    def get_queryset(self):
        organization = self.get_user_organization()
        if not organization:
            return Contract.objects.none()
        return Contract.objects.filter(
            organization=organization
        ).select_related('supplier', 'quote', 'quote__rfq').order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get contract statistics
        contracts = self.get_queryset()
        context['stats'] = {
            'total_contracts': contracts.count(),
            'active_contracts': contracts.filter(status='active').count(),
            'expiring_soon': contracts.filter(
                status='active',
                end_date__lte=timezone.now() + timedelta(days=30),
                end_date__gte=timezone.now()
            ).count(),
            'total_value': contracts.aggregate(
                total=Sum('total_value')
            )['total'] or 0,
        }

        # Calculate average duration in months
        contracts_with_dates = contracts.filter(
            start_date__isnull=False,
            end_date__isnull=False
        )
        if contracts_with_dates.exists():
            total_months = 0
            count = 0
            for c in contracts_with_dates:
                if c.start_date and c.end_date:
                    duration_days = (c.end_date - c.start_date).days
                    total_months += duration_days / 30
                    count += 1
            context['avg_duration'] = round(total_months / count) if count > 0 else 0
        else:
            context['avg_duration'] = 0

        return context


class ContractDetailView(OrganizationRequiredMixin, DetailView):
    """Contract detail view"""
    model = Contract
    template_name = 'procurement/contract_detail.html'
    context_object_name = 'contract'
    
    def get_queryset(self):
        organization = self.get_user_organization()
        if not organization:
            return Contract.objects.none()
        return Contract.objects.filter(
            organization=organization
        ).select_related('supplier', 'quote', 'quote__rfq')


class ContractCreateView(OrganizationRequiredMixin, CreateView):
    """Create contract from approved quote"""
    model = Contract
    form_class = ContractForm
    template_name = 'procurement/contract_form.html'
    
    def get_initial(self):
        initial = super().get_initial()
        
        # If creating from a quote
        quote_id = self.request.GET.get('quote_id')
        if quote_id:
            organization = self.get_user_organization()
            if organization:
                try:
                    quote = Quote.objects.get(
                        id=quote_id,
                        organization=organization,
                        status='approved'
                    )
                    initial.update({
                        'supplier': quote.supplier,
                        'quote': quote,
                        'title': f"Contract for {quote.rfq.title}",
                        'total_value': quote.total_value,
                        'payment_terms': quote.payment_terms,
                        'delivery_terms': quote.delivery_terms,
                    })
                except Quote.DoesNotExist:
                    pass
        
        # Generate contract number
        import random
        initial['contract_number'] = f'CNT-{timezone.now().strftime("%Y%m%d")}-{random.randint(1000, 9999)}'
        
        return initial
    
    def form_valid(self, form):
        form.instance.organization = self.get_user_organization()
        form.instance.created_by = self.request.user
        
        # Link to quote if provided
        quote_id = self.request.GET.get('quote_id')
        if quote_id:
            try:
                quote = Quote.objects.get(
                    id=quote_id,
                    organization=self.get_user_organization()
                )
                form.instance.quote = quote
            except Quote.DoesNotExist:
                pass
        
        messages.success(self.request, f'Contract "{form.instance.title}" created successfully.')
        return super().form_valid(form)


class ContractUpdateView(OrganizationRequiredMixin, UpdateView):
    """Update contract"""
    model = Contract
    form_class = ContractForm
    template_name = 'procurement/contract_form.html'
    
    def get_queryset(self):
        organization = self.get_user_organization()
        if not organization:
            return Contract.objects.none()
        return Contract.objects.filter(
            organization=organization
        )
    
    def form_valid(self, form):
        messages.success(self.request, f'Contract "{form.instance.title}" updated successfully.')
        return super().form_valid(form)


class SupplierPerformanceView(OrganizationRequiredMixin, TemplateView):
    """Supplier performance analytics"""
    template_name = 'procurement/supplier_performance.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get top performing suppliers
        suppliers_performance = Supplier.objects.filter(
            organization=self.get_user_organization(),
            status='active'
        ).annotate(
            total_quotes=Count('quote'),
            approved_quotes=Count('quote', filter=Q(quote__status='approved')),
            avg_quote_value=Avg('quote__total_amount')
        ).filter(total_quotes__gt=0).order_by('-approved_quotes')[:10]
        
        context['top_suppliers'] = suppliers_performance
        
        return context


class SupplierIndividualPerformanceView(OrganizationRequiredMixin, DetailView):
    """Individual supplier performance view"""
    model = Supplier
    template_name = 'procurement/supplier_individual_performance.html'
    context_object_name = 'supplier'

    def get_queryset(self):
        """Filter suppliers by organization"""
        organization = self.get_user_organization()
        if not organization:
            return Supplier.objects.none()
        return Supplier.objects.filter(organization=organization)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        supplier = self.object

        # Calculate performance metrics
        quotes = Quote.objects.filter(
            supplier=supplier,
            rfq__organization=self.get_user_organization()
        )

        # Get RFQs related to this supplier
        rfqs = RFQ.objects.filter(
            invited_suppliers=supplier,
            organization=self.get_user_organization()
        ).order_by('-created_at')[:10]

        # Calculate metrics
        context['total_rfqs'] = rfqs.count()
        context['total_quotes'] = quotes.count()
        context['approved_quotes'] = quotes.filter(status='approved').count()
        context['pending_quotes'] = quotes.filter(status='pending').count()
        context['rejected_quotes'] = quotes.filter(status='rejected').count()
        context['average_quote_value'] = quotes.aggregate(avg=Avg('total_amount'))['avg'] or 0
        context['total_business'] = quotes.filter(status='approved').aggregate(sum=Sum('total_amount'))['sum'] or 0

        # Quote history
        context['recent_quotes'] = quotes.order_by('-created_at')[:10]
        context['recent_rfqs'] = rfqs

        # Win rate
        if context['total_quotes'] > 0:
            context['win_rate'] = (context['approved_quotes'] / context['total_quotes']) * 100
        else:
            context['win_rate'] = 0

        return context


class QuoteComparisonView(OrganizationRequiredMixin, TemplateView):
    """Quote comparison view"""
    template_name = 'procurement/quote_comparison.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        rfq_id = self.request.GET.get('rfq_id')
        if rfq_id:
            try:
                rfq = RFQ.objects.get(
                    id=rfq_id,
                    organization=self.get_user_organization()
                )
                quotes = Quote.objects.filter(
                    rfq=rfq,
                    status__in=['submitted', 'under_review', 'accepted', 'approved']
                ).select_related('supplier').prefetch_related('items__rfq_item__material')
                
                # Prepare comparison data
                comparison_data = []
                for quote in quotes:
                    quote_data = {
                        'quote': quote,
                        'supplier': quote.supplier,
                        'total_amount': quote.total_amount,
                        'validity_period': quote.validity_period,
                        'delivery_terms': quote.delivery_terms,
                        'payment_terms': quote.payment_terms,
                        'lead_time': quote.lead_time,
                        'items': {}
                    }
                    
                    # Add item-level pricing
                    for item in quote.items.all():
                        quote_data['items'][item.rfq_item.id] = {
                            'price': item.price,
                            'unit_price': item.price / item.quantity if item.quantity > 0 else 0,
                            'quantity': item.quantity,
                            'delivery_date': item.delivery_date
                        }
                    
                    comparison_data.append(quote_data)
                
                # Sort by total amount
                comparison_data.sort(key=lambda x: x['total_amount'])
                
                context['rfq'] = rfq
                context['comparison_data'] = comparison_data
                context['quotes'] = quotes
                
                # Calculate best prices for each item
                best_prices = {}
                for item in rfq.items.all():
                    prices = []
                    for data in comparison_data:
                        if item.id in data['items']:
                            prices.append({
                                'supplier': data['supplier'].name,
                                'unit_price': data['items'][item.id]['unit_price']
                            })
                    if prices:
                        prices.sort(key=lambda x: x['unit_price'])
                        best_prices[item.id] = prices[0]
                
                context['best_prices'] = best_prices
                context['rfq_items'] = rfq.items.select_related('material')
                
            except RFQ.DoesNotExist:
                context['error'] = 'RFQ not found'
        else:
            # Show list of RFQs to compare
            context['rfqs'] = RFQ.objects.filter(
                organization=self.get_user_organization(),
                status__in=['published', 'closed']
            ).annotate(quote_count=models.Count('quotes')).filter(quote_count__gt=0)
        
        return context


class ProcurementDashboardView(OrganizationRequiredMixin, TemplateView):
    """Procurement dashboard with key metrics"""
    template_name = 'procurement/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = self.get_user_organization()
        now = timezone.now()
        thirty_days_ago = now - timedelta(days=30)
        sixty_days_ago = now - timedelta(days=60)

        # Calculate total spend from accepted quotes
        current_spend = Quote.objects.filter(
            organization=organization,
            status__in=['accepted', 'approved'],
            created_at__gte=thirty_days_ago
        ).aggregate(total=Sum('total_amount'))['total'] or 0

        previous_spend = Quote.objects.filter(
            organization=organization,
            status__in=['accepted', 'approved'],
            created_at__gte=sixty_days_ago,
            created_at__lt=thirty_days_ago
        ).aggregate(total=Sum('total_amount'))['total'] or 0

        # Calculate spend trend
        if previous_spend > 0:
            spend_trend = ((current_spend - previous_spend) / previous_spend) * 100
        else:
            spend_trend = 0

        # Calculate avg supplier rating
        avg_rating = Supplier.objects.filter(
            organization=organization,
            status='active',
            rating__gt=0
        ).aggregate(avg=Avg('rating'))['avg'] or 0

        # Get key metrics
        context['metrics'] = {
            'total_suppliers': Supplier.objects.filter(
                organization=organization, status='active'
            ).count(),
            'active_rfqs': RFQ.objects.filter(
                organization=organization,
                status__in=['draft', 'published', 'open']
            ).count(),
            'pending_quotes': Quote.objects.filter(
                organization=organization,
                status__in=['submitted', 'under_review']
            ).count(),
            'total_spend': current_spend,
            'spend_trend': round(spend_trend, 1),
            'previous_spend': previous_spend,
            'avg_supplier_rating': round(avg_rating, 1) if avg_rating else 0,
            'cost_savings': 0,  # Would need actual calculation from quote vs budget comparisons
        }
        
        # Get recent RFQs
        context['recent_rfqs'] = RFQ.objects.filter(
            organization=organization
        ).order_by('-created_at')[:5]
        
        # Get top suppliers by value
        context['top_suppliers'] = Supplier.objects.filter(
            organization=organization,
            status='active'
        ).annotate(
            total_value=Sum('quote__total_value', filter=Q(quote__status='approved'))
        ).order_by('-total_value')[:5]
        
        # Recent activities (placeholder - would come from an activity log)
        context['recent_activities'] = [
            {'description': 'New quote received from ABC Suppliers', 'timestamp': now - timedelta(hours=2)},
            {'description': 'RFQ-2024-001 approved', 'timestamp': now - timedelta(hours=5)},
            {'description': 'Supplier XYZ Corp added', 'timestamp': now - timedelta(days=1)},
        ]
        
        # Pending actions count
        context['pending_actions'] = {
            'quotes_to_review': Quote.objects.filter(
                organization=organization,
                status='submitted'
            ).count(),
            'expiring_rfqs': RFQ.objects.filter(
                organization=organization,
                status='open',
                deadline__lte=now + timedelta(days=2),
                deadline__gte=now
            ).count(),
            'new_suppliers': Supplier.objects.filter(
                organization=organization,
                status='pending_approval'
            ).count(),
        }
        
        return context


# API ViewSets
class SupplierViewSet(viewsets.ModelViewSet):
    """Supplier API ViewSet"""
    serializer_class = SupplierSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ['name', 'contact_email', 'category']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']
    
    def get_queryset(self):
        return Supplier.objects.filter(
            organization=self.get_user_organization(),
            status='active'
        )
    
    def perform_create(self, serializer):
        serializer.save(
            organization=self.get_user_organization(),
            created_by=self.request.user
        )


class RFQViewSet(viewsets.ModelViewSet):
    """RFQ API ViewSet"""
    serializer_class = RFQSerializer
    permission_classes = [IsAuthenticated]
    ordering = ['-created_at']
    
    def get_queryset(self):
        return RFQ.objects.filter(
            organization=self.get_user_organization()
        ).prefetch_related('items', 'invited_suppliers')
    
    def perform_create(self, serializer):
        serializer.save(
            organization=self.get_user_organization(),
            created_by=self.request.user
        )
    
    @action(detail=True, methods=['post'])
    def send_to_suppliers(self, request, pk=None):
        """Send RFQ to selected suppliers"""
        rfq = self.get_object()
        supplier_ids = request.data.get('supplier_ids', [])
        
        if not supplier_ids:
            return Response(
                {'error': 'No suppliers specified'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # This would typically send emails
        rfq.status = 'published'
        rfq.save()
        
        return Response({'message': 'RFQ sent to suppliers successfully'})


class QuoteViewSet(viewsets.ModelViewSet):
    """Quote API ViewSet"""
    serializer_class = QuoteSerializer
    permission_classes = [IsAuthenticated]
    ordering = ['-created_at']
    
    def get_queryset(self):
        return Quote.objects.filter(
            organization=self.get_user_organization()
        ).select_related('rfq', 'supplier').prefetch_related('items')
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve quote"""
        quote = self.get_object()
        quote.status = 'approved'
        quote.approved_by = request.user
        quote.approved_at = timezone.now()
        quote.save()
        
        return Response({'message': 'Quote approved successfully'})
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject quote"""
        quote = self.get_object()
        rejection_reason = request.data.get('rejection_reason', '')
        
        quote.status = 'rejected'
        quote.rejection_reason = rejection_reason
        quote.rejected_by = request.user
        quote.rejected_at = timezone.now()
        quote.save()
        
        return Response({'message': 'Quote rejected successfully'})


# Export Views (Placeholder implementations)
class RFQExportView(OrganizationRequiredMixin, View):
    """Export RFQ to Excel/PDF"""

    def get(self, request, pk=None):
        """Handle RFQ export"""
        # Placeholder implementation
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Export Coming Soon</title>
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
            <style>
                body { font-family: Arial, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background: #f3f4f6; }
                .container { text-align: center; background: white; padding: 40px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                h1 { color: #1e3a8a; margin-bottom: 10px; }
                .icon { font-size: 48px; color: #1e3a8a; margin-bottom: 20px; }
                p { color: #6b7280; margin: 10px 0; }
                button { background: #1e3a8a; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; margin-top: 20px; }
                button:hover { background: #1e40af; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="icon">
                    <i class="fas fa-file-export"></i>
                </div>
                <h1>Export Feature Coming Soon!</h1>
                <p>The RFQ export functionality is currently under development.</p>
                <p>You'll soon be able to export RFQs to Excel and PDF formats.</p>
                <button onclick="window.history.back()">Go Back</button>
            </div>
        </body>
        </html>
        """
        return HttpResponse(html_content, content_type='text/html')


class SupplierExportView(OrganizationRequiredMixin, View):
    """Export suppliers to Excel/CSV"""

    def get(self, request, pk=None):
        """Handle supplier export"""
        # Placeholder implementation
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Export Coming Soon</title>
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
            <style>
                body { font-family: Arial, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background: #f3f4f6; }
                .container { text-align: center; background: white; padding: 40px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                h1 { color: #1e3a8a; margin-bottom: 10px; }
                .icon { font-size: 48px; color: #1e3a8a; margin-bottom: 20px; }
                p { color: #6b7280; margin: 10px 0; }
                button { background: #1e3a8a; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; margin-top: 20px; }
                button:hover { background: #1e40af; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="icon">
                    <i class="fas fa-building"></i>
                </div>
                <h1>Export Feature Coming Soon!</h1>
                <p>The supplier export functionality is currently under development.</p>
                <p>You'll soon be able to export supplier data to Excel and CSV formats.</p>
                <button onclick="window.history.back()">Go Back</button>
            </div>
        </body>
        </html>
        """
        return HttpResponse(html_content, content_type='text/html')


class SupplierPerformanceExportView(OrganizationRequiredMixin, View):
    """Export supplier performance report"""

    def get(self, request, pk):
        """Handle supplier performance export"""
        # Placeholder implementation
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Export Coming Soon</title>
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
            <style>
                body { font-family: Arial, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background: #f3f4f6; }
                .container { text-align: center; background: white; padding: 40px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                h1 { color: #1e3a8a; margin-bottom: 10px; }
                .icon { font-size: 48px; color: #1e3a8a; margin-bottom: 20px; }
                p { color: #6b7280; margin: 10px 0; }
                button { background: #1e3a8a; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; margin-top: 20px; }
                button:hover { background: #1e40af; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="icon">
                    <i class="fas fa-chart-line"></i>
                </div>
                <h1>Export Feature Coming Soon!</h1>
                <p>The performance report export functionality is currently under development.</p>
                <p>You'll soon be able to export detailed performance analytics to PDF and Excel.</p>
                <button onclick="window.history.back()">Go Back</button>
            </div>
        </body>
        </html>
        """
        return HttpResponse(html_content, content_type='text/html')


class QuoteExportView(OrganizationRequiredMixin, View):
    """Export quotes to Excel/CSV"""

    def get(self, request):
        """Handle quote export"""
        # Placeholder implementation
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Export Coming Soon</title>
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
            <style>
                body { font-family: Arial, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background: #f3f4f6; }
                .container { text-align: center; background: white; padding: 40px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                h1 { color: #1e3a8a; margin-bottom: 10px; }
                .icon { font-size: 48px; color: #1e3a8a; margin-bottom: 20px; }
                p { color: #6b7280; margin: 10px 0; }
                button { background: #1e3a8a; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; margin-top: 20px; }
                button:hover { background: #1e40af; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="icon">
                    <i class="fas fa-file-invoice-dollar"></i>
                </div>
                <h1>Export Feature Coming Soon!</h1>
                <p>The quote export functionality is currently under development.</p>
                <p>You'll soon be able to export quotes to Excel and CSV formats.</p>
                <button onclick="window.history.back()">Go Back</button>
            </div>
        </body>
        </html>
        """
        return HttpResponse(html_content, content_type='text/html')


class ContractExportView(OrganizationRequiredMixin, View):
    """Export contracts to Excel/PDF"""

    def get(self, request):
        """Handle contract export"""
        # Placeholder implementation
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Export Coming Soon</title>
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
            <style>
                body { font-family: Arial, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background: #f3f4f6; }
                .container { text-align: center; background: white; padding: 40px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                h1 { color: #1e3a8a; margin-bottom: 10px; }
                .icon { font-size: 48px; color: #1e3a8a; margin-bottom: 20px; }
                p { color: #6b7280; margin: 10px 0; }
                button { background: #1e3a8a; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; margin-top: 20px; }
                button:hover { background: #1e40af; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="icon">
                    <i class="fas fa-file-contract"></i>
                </div>
                <h1>Export Feature Coming Soon!</h1>
                <p>The contract export functionality is currently under development.</p>
                <p>You'll soon be able to export contracts to PDF and Excel formats.</p>
                <button onclick="window.history.back()">Go Back</button>
            </div>
        </body>
        </html>
        """
        return HttpResponse(html_content, content_type='text/html')


class TestJavaScriptView(OrganizationRequiredMixin, TemplateView):
    """Test JavaScript modules loading"""
    template_name = 'procurement/test_js.html'


class TestFirefoxLoadingView(OrganizationRequiredMixin, TemplateView):
    """Test Firefox loading overlay issue"""
    template_name = 'procurement/test_firefox_loading.html'
