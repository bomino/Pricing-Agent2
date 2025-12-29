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
        
        queryset = Supplier.objects.filter(
            organization=organization,
            status='active'
        ).order_by('name')
        
        # Add search functionality
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(contact_email__icontains=search) |
                Q(category__icontains=search)
            )
        
        return queryset


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
        return RFQ.objects.filter(
            organization=self.get_user_organization()
        ).order_by('-created_at')


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
    template_name = 'procurement/rfq_form.html'
    
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
    template_name = 'procurement/rfq_form.html'
    
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
        return Quote.objects.filter(
            organization=self.get_user_organization()
        ).select_related('rfq', 'supplier').order_by('-created_at')


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
            'total_value': contracts.filter(status='active').aggregate(
                total=Sum('total_value')
            )['total'] or 0,
        }
        
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
            avg_quote_value=Avg('quote__total_value')
        ).filter(total_quotes__gt=0).order_by('-approved_quotes')[:10]
        
        context['top_suppliers'] = suppliers_performance
        
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
                status='submitted'
            ).count(),
            'total_quote_value': Quote.objects.filter(
                organization=organization,
                status='approved',
                created_at__gte=thirty_days_ago
            ).aggregate(total=Sum('total_value'))['total'] or 0,
            'total_spend': Quote.objects.filter(
                organization=organization,
                status='approved',
                created_at__gte=thirty_days_ago
            ).aggregate(total=Sum('total_value'))['total'] or 0,
            'cost_savings': 145000,  # Placeholder - would calculate from quote comparisons
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