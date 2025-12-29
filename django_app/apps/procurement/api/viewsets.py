"""
Procurement API viewsets
"""
from django.db.models import Q, Count, Avg, Sum, F
from django.utils import timezone
from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from decimal import Decimal

from apps.procurement.models import (
    Supplier, RFQ, Quote, RFQItem, QuoteItem, Contract,
    SupplierContact, SupplierDocument
)
from apps.pricing.models import Material
from .serializers import (
    SupplierSerializer, SupplierListSerializer, SupplierDetailSerializer,
    RFQSerializer, RFQListSerializer, QuoteSerializer, QuoteListSerializer,
    QuoteCreateSerializer, ContractSerializer, ContractListSerializer,
    SupplierContactSerializer, SupplierDocumentSerializer,
    ProcurementStatsSerializer, SupplierPerformanceSerializer,
    RFQAnalyticsSerializer, QuoteComparisonSerializer,
    SupplierOnboardingSerializer, RFQItemSerializer
)
from apps.core.security import SecurityMixin, AuditMixin
from apps.core.pagination import StandardResultsSetPagination


class SupplierViewSet(SecurityMixin, AuditMixin, viewsets.ModelViewSet):
    """
    ViewSet for managing suppliers.
    
    Provides CRUD operations for suppliers with proper access control,
    filtering, searching, and performance analytics.
    """
    
    serializer_class = SupplierSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['supplier_type', 'status', 'country', 'region', 'risk_level']
    search_fields = ['name', 'code', 'primary_contact_name', 'primary_contact_email']
    ordering_fields = ['name', 'code', 'rating', 'created_at', 'updated_at']
    ordering = ['name']
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Filter suppliers based on user organization"""
        user = self.request.user
        
        try:
            user_profile = user.profile
            return Supplier.objects.filter(
                organization=user_profile.organization
            ).select_related('organization')
        except:
            return Supplier.objects.none()
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return SupplierListSerializer
        elif self.action == 'retrieve':
            return SupplierDetailSerializer
        return SupplierSerializer
    
    def perform_create(self, serializer):
        """Create supplier with organization"""
        user_profile = self.request.user.profile
        supplier = serializer.save(organization=user_profile.organization)
        self.log_action('create', supplier)
    
    def perform_update(self, serializer):
        """Update supplier with audit logging"""
        original_data = self.get_object().__dict__.copy()
        supplier = serializer.save()
        self.log_action('update', supplier, changes={
            'original': original_data,
            'updated': serializer.validated_data
        })
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        """Approve supplier"""
        supplier = self.get_object()
        supplier.status = 'active'
        supplier.approved_by = request.user
        supplier.approved_at = timezone.now()
        supplier.save()
        
        self.log_action('approve', supplier)
        return Response({'status': 'Supplier approved'})
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def suspend(self, request, pk=None):
        """Suspend supplier"""
        supplier = self.get_object()
        supplier.status = 'suspended'
        supplier.save()
        
        self.log_action('suspend', supplier)
        return Response({'status': 'Supplier suspended'})
    
    @action(detail=True, methods=['get'])
    def performance(self, request, pk=None):
        """Get supplier performance metrics"""
        supplier = self.get_object()
        
        # Calculate performance metrics
        quotes = supplier.quotes.all()
        contracts = supplier.contracts.all()
        
        total_quotes = quotes.count()
        accepted_quotes = quotes.filter(status='accepted').count()
        total_contract_value = contracts.aggregate(
            total=Sum('total_value')
        )['total'] or Decimal('0')
        
        performance_data = {
            'supplier': SupplierListSerializer(supplier).data,
            'performance_score': supplier.calculate_performance_score(),
            'total_quotes': total_quotes,
            'accepted_quotes': accepted_quotes,
            'quote_acceptance_rate': (accepted_quotes / total_quotes * 100) if total_quotes > 0 else 0,
            'total_contract_value': total_contract_value,
            'on_time_delivery_rate': supplier.on_time_delivery_rate or 0,
            'quality_score': supplier.quality_score or 0,
        }
        
        serializer = SupplierPerformanceSerializer(performance_data)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def quotes(self, request, pk=None):
        """Get supplier quotes"""
        supplier = self.get_object()
        quotes = supplier.quotes.all().order_by('-created_at')
        
        page = self.paginate_queryset(quotes)
        if page is not None:
            serializer = QuoteListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = QuoteListSerializer(quotes, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def contracts(self, request, pk=None):
        """Get supplier contracts"""
        supplier = self.get_object()
        contracts = supplier.contracts.all().order_by('-created_at')
        
        page = self.paginate_queryset(contracts)
        if page is not None:
            serializer = ContractListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = ContractListSerializer(contracts, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def add_contact(self, request, pk=None):
        """Add supplier contact"""
        supplier = self.get_object()
        serializer = SupplierContactSerializer(data=request.data)
        
        if serializer.is_valid():
            contact = serializer.save(supplier=supplier)
            self.log_action('add_contact', contact)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def performance_ranking(self, request):
        """Get supplier performance ranking"""
        suppliers = self.get_queryset().filter(status='active')
        
        # Calculate performance scores for all suppliers
        performance_data = []
        for supplier in suppliers:
            score = supplier.calculate_performance_score()
            if score is not None:
                performance_data.append({
                    'supplier': SupplierListSerializer(supplier).data,
                    'performance_score': score,
                })
        
        # Sort by performance score descending
        performance_data.sort(key=lambda x: x['performance_score'], reverse=True)
        
        # Add ranking
        for i, data in enumerate(performance_data):
            data['rank'] = i + 1
        
        return Response(performance_data)


class RFQViewSet(SecurityMixin, AuditMixin, viewsets.ModelViewSet):
    """
    ViewSet for managing RFQs (Request for Quotes).
    
    Provides CRUD operations for RFQs with workflow management,
    supplier invitation, and quote collection.
    """
    
    serializer_class = RFQSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'priority', 'created_by', 'department']
    search_fields = ['rfq_number', 'title', 'description']
    ordering_fields = ['rfq_number', 'title', 'deadline', 'created_at', 'priority']
    ordering = ['-created_at']
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Filter RFQs based on user organization"""
        user = self.request.user
        
        try:
            user_profile = user.profile
            return RFQ.objects.filter(
                organization=user_profile.organization
            ).select_related('created_by', 'organization')
        except:
            return RFQ.objects.none()
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return RFQListSerializer
        return RFQSerializer
    
    def perform_create(self, serializer):
        """Create RFQ with organization"""
        user_profile = self.request.user.profile
        rfq = serializer.save(organization=user_profile.organization)
        self.log_action('create', rfq)
    
    def perform_update(self, serializer):
        """Update RFQ with audit logging"""
        original_data = self.get_object().__dict__.copy()
        rfq = serializer.save()
        self.log_action('update', rfq, changes={
            'original': original_data,
            'updated': serializer.validated_data
        })
    
    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        """Publish RFQ to invited suppliers"""
        rfq = self.get_object()
        
        if rfq.status != 'draft':
            return Response(
                {'error': 'Only draft RFQs can be published'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        rfq.publish(request.user)
        self.log_action('publish', rfq)
        
        return Response({'status': 'RFQ published successfully'})
    
    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """Close RFQ"""
        rfq = self.get_object()
        
        if rfq.status not in ['published']:
            return Response(
                {'error': 'Only published RFQs can be closed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        rfq.close(request.user)
        self.log_action('close', rfq)
        
        return Response({'status': 'RFQ closed successfully'})
    
    @action(detail=True, methods=['post'])
    def award(self, request, pk=None):
        """Award RFQ to a quote"""
        rfq = self.get_object()
        quote_id = request.data.get('quote_id')
        
        if not quote_id:
            return Response(
                {'error': 'Quote ID is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            quote = Quote.objects.get(id=quote_id, rfq=rfq)
        except Quote.DoesNotExist:
            return Response(
                {'error': 'Quote not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        rfq.award_to_quote(quote, request.user)
        self.log_action('award', rfq, changes={'awarded_quote_id': str(quote.id)})
        
        return Response({'status': 'RFQ awarded successfully'})
    
    @action(detail=True, methods=['get'])
    def quotes(self, request, pk=None):
        """Get quotes for RFQ"""
        rfq = self.get_object()
        quotes = rfq.quotes.all().order_by('-submitted_at')
        
        page = self.paginate_queryset(quotes)
        if page is not None:
            serializer = QuoteListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = QuoteListSerializer(quotes, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def analytics(self, request, pk=None):
        """Get RFQ analytics"""
        rfq = self.get_object()
        quotes = rfq.quotes.filter(status='submitted')
        
        if not quotes.exists():
            return Response({
                'rfq': RFQListSerializer(rfq).data,
                'quotes_received': 0,
                'message': 'No quotes received yet'
            })
        
        quote_values = [float(q.total_amount) for q in quotes]
        
        analytics_data = {
            'rfq': RFQListSerializer(rfq).data,
            'quotes_received': quotes.count(),
            'average_quote_value': sum(quote_values) / len(quote_values),
            'lowest_quote_value': min(quote_values),
            'highest_quote_value': max(quote_values),
            'value_spread': max(quote_values) - min(quote_values),
            'savings_potential': (max(quote_values) - min(quote_values)) if len(quote_values) > 1 else 0,
        }
        
        serializer = RFQAnalyticsSerializer(analytics_data)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def compare_quotes(self, request, pk=None):
        """Compare quotes for RFQ"""
        rfq = self.get_object()
        quotes = rfq.quotes.filter(status='submitted')
        
        if quotes.count() < 2:
            return Response(
                {'error': 'At least 2 quotes are required for comparison'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Build comparison matrix
        comparison_data = {
            'rfq': RFQListSerializer(rfq).data,
            'quotes': QuoteListSerializer(quotes, many=True).data,
            'comparison_matrix': self._build_comparison_matrix(quotes),
            'recommendations': self._generate_recommendations(quotes),
            'scoring_criteria': self._get_scoring_criteria(),
        }
        
        serializer = QuoteComparisonSerializer(comparison_data)
        return Response(serializer.data)
    
    def _build_comparison_matrix(self, quotes):
        """Build quote comparison matrix"""
        matrix = []
        for quote in quotes:
            matrix.append({
                'quote_id': str(quote.id),
                'supplier': quote.supplier.name,
                'total_amount': float(quote.total_amount),
                'lead_time_days': quote.lead_time_days,
                'technical_score': float(quote.technical_score) if quote.technical_score else None,
                'commercial_score': float(quote.commercial_score) if quote.commercial_score else None,
                'overall_score': float(quote.overall_score) if quote.overall_score else None,
            })
        return matrix
    
    def _generate_recommendations(self, quotes):
        """Generate recommendations based on quote analysis"""
        best_price = min(quotes, key=lambda q: q.total_amount)
        best_score = max(quotes, key=lambda q: q.overall_score or 0)
        
        return {
            'best_price': {
                'quote_id': str(best_price.id),
                'supplier': best_price.supplier.name,
                'total_amount': float(best_price.total_amount),
            },
            'best_score': {
                'quote_id': str(best_score.id),
                'supplier': best_score.supplier.name,
                'overall_score': float(best_score.overall_score) if best_score.overall_score else None,
            }
        }
    
    def _get_scoring_criteria(self):
        """Get scoring criteria configuration"""
        return {
            'technical_weight': 0.4,
            'commercial_weight': 0.6,
            'criteria': [
                'price_competitiveness',
                'supplier_reputation',
                'delivery_time',
                'quality_standards',
                'payment_terms',
            ]
        }
    
    @action(detail=True, methods=['post'])
    def add_item(self, request, pk=None):
        """Add item to RFQ"""
        rfq = self.get_object()
        
        if rfq.status != 'draft':
            return Response(
                {'error': 'Items can only be added to draft RFQs'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = RFQItemSerializer(data=request.data)
        if serializer.is_valid():
            item = serializer.save(rfq=rfq)
            self.log_action('add_item', item)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class QuoteViewSet(SecurityMixin, AuditMixin, viewsets.ModelViewSet):
    """
    ViewSet for managing quotes.
    
    Provides CRUD operations for quotes with evaluation,
    comparison, and award functionality.
    """
    
    serializer_class = QuoteSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'supplier', 'rfq', 'currency']
    search_fields = ['quote_number', 'reference_number', 'supplier__name']
    ordering_fields = ['quote_number', 'total_amount', 'submitted_at', 'overall_score']
    ordering = ['-submitted_at']
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Filter quotes based on user organization"""
        user = self.request.user
        
        try:
            user_profile = user.profile
            return Quote.objects.filter(
                organization=user_profile.organization
            ).select_related('supplier', 'rfq', 'evaluated_by')
        except:
            return Quote.objects.none()
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return QuoteListSerializer
        elif self.action == 'create':
            return QuoteCreateSerializer
        return QuoteSerializer
    
    def perform_create(self, serializer):
        """Create quote with organization"""
        user_profile = self.request.user.profile
        
        # Get RFQ and supplier from request data
        rfq_id = self.request.data.get('rfq_id')
        supplier_id = self.request.data.get('supplier_id')
        
        try:
            rfq = RFQ.objects.get(id=rfq_id, organization=user_profile.organization)
            supplier = Supplier.objects.get(id=supplier_id, organization=user_profile.organization)
        except (RFQ.DoesNotExist, Supplier.DoesNotExist):
            return Response(
                {'error': 'RFQ or Supplier not found'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        quote = serializer.save(
            organization=user_profile.organization,
            context={'rfq': rfq, 'supplier': supplier}
        )
        self.log_action('create', quote)
    
    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """Submit quote"""
        quote = self.get_object()
        
        if quote.status != 'draft':
            return Response(
                {'error': 'Only draft quotes can be submitted'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        quote.submit()
        self.log_action('submit', quote)
        
        return Response({'status': 'Quote submitted successfully'})
    
    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        """Accept quote"""
        quote = self.get_object()
        
        if quote.status not in ['submitted', 'under_review']:
            return Response(
                {'error': 'Only submitted or under review quotes can be accepted'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        quote.accept(request.user)
        self.log_action('accept', quote)
        
        return Response({'status': 'Quote accepted successfully'})
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject quote"""
        quote = self.get_object()
        reason = request.data.get('reason', '')
        
        if quote.status not in ['submitted', 'under_review']:
            return Response(
                {'error': 'Only submitted or under review quotes can be rejected'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        quote.reject(reason, request.user)
        self.log_action('reject', quote, changes={'reason': reason})
        
        return Response({'status': 'Quote rejected successfully'})
    
    @action(detail=True, methods=['post'])
    def evaluate(self, request, pk=None):
        """Evaluate quote with scores"""
        quote = self.get_object()
        
        technical_score = request.data.get('technical_score')
        commercial_score = request.data.get('commercial_score')
        notes = request.data.get('notes', '')
        
        if technical_score is not None:
            quote.technical_score = Decimal(str(technical_score))
        if commercial_score is not None:
            quote.commercial_score = Decimal(str(commercial_score))
        
        # Calculate overall score (weighted average)
        if quote.technical_score and quote.commercial_score:
            technical_weight = Decimal('0.4')
            commercial_weight = Decimal('0.6')
            quote.overall_score = (
                quote.technical_score * technical_weight + 
                quote.commercial_score * commercial_weight
            )
        
        quote.internal_notes = notes
        quote.evaluated_by = request.user
        quote.evaluated_at = timezone.now()
        quote.status = 'under_review'
        quote.save()
        
        self.log_action('evaluate', quote, changes={
            'technical_score': float(technical_score) if technical_score else None,
            'commercial_score': float(commercial_score) if commercial_score else None,
        })
        
        return Response({'status': 'Quote evaluated successfully'})


class ContractViewSet(SecurityMixin, AuditMixin, viewsets.ModelViewSet):
    """
    ViewSet for managing contracts.
    
    Provides CRUD operations for contracts with approval workflow,
    document management, and lifecycle tracking.
    """
    
    serializer_class = ContractSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['contract_type', 'status', 'supplier']
    search_fields = ['contract_number', 'title', 'supplier__name']
    ordering_fields = ['contract_number', 'title', 'total_value', 'start_date', 'end_date']
    ordering = ['-created_at']
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Filter contracts based on user organization"""
        user = self.request.user
        
        try:
            user_profile = user.profile
            return Contract.objects.filter(
                organization=user_profile.organization
            ).select_related('supplier', 'quote', 'created_by', 'approved_by')
        except:
            return Contract.objects.none()
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return ContractListSerializer
        return ContractSerializer
    
    def perform_create(self, serializer):
        """Create contract with organization"""
        user_profile = self.request.user.profile
        
        # Auto-generate contract number
        from datetime import datetime
        contract_number = f"CNT-{datetime.now().strftime('%Y%m%d')}-{timezone.now().microsecond}"
        
        contract = serializer.save(
            organization=user_profile.organization,
            created_by=self.request.user,
            contract_number=contract_number
        )
        self.log_action('create', contract)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        """Approve contract"""
        contract = self.get_object()
        
        if contract.status != 'pending_approval':
            return Response(
                {'error': 'Only pending contracts can be approved'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        contract.approve(request.user)
        self.log_action('approve', contract)
        
        return Response({'status': 'Contract approved successfully'})
    
    @action(detail=True, methods=['post'])
    def terminate(self, request, pk=None):
        """Terminate contract"""
        contract = self.get_object()
        reason = request.data.get('reason', '')
        
        if contract.status not in ['active']:
            return Response(
                {'error': 'Only active contracts can be terminated'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        contract.terminate(reason)
        self.log_action('terminate', contract, changes={'reason': reason})
        
        return Response({'status': 'Contract terminated successfully'})
    
    @action(detail=False, methods=['get'])
    def expiring_soon(self, request):
        """Get contracts expiring within 30 days"""
        from datetime import timedelta
        
        expiry_date = timezone.now().date() + timedelta(days=30)
        contracts = self.get_queryset().filter(
            status='active',
            end_date__lte=expiry_date
        ).order_by('end_date')
        
        page = self.paginate_queryset(contracts)
        if page is not None:
            serializer = ContractListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = ContractListSerializer(contracts, many=True)
        return Response(serializer.data)


class ProcurementAnalyticsViewSet(viewsets.ViewSet):
    """
    ViewSet for procurement analytics and reporting.
    
    Provides various analytics endpoints for procurement data.
    """
    
    permission_classes = [IsAuthenticated]
    
    def get_organization(self):
        """Get user's organization"""
        return self.request.user.profile.organization
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get overall procurement statistics"""
        org = self.get_organization()
        
        # Basic counts
        total_suppliers = Supplier.objects.filter(organization=org).count()
        active_suppliers = Supplier.objects.filter(organization=org, status='active').count()
        
        total_rfqs = RFQ.objects.filter(organization=org).count()
        open_rfqs = RFQ.objects.filter(organization=org, status='published').count()
        
        total_quotes = Quote.objects.filter(organization=org).count()
        pending_quotes = Quote.objects.filter(organization=org, status='submitted').count()
        
        total_contracts = Contract.objects.filter(organization=org).count()
        active_contracts = Contract.objects.filter(organization=org, status='active').count()
        
        # Value statistics
        total_contract_value = Contract.objects.filter(
            organization=org, status='active'
        ).aggregate(total=Sum('total_value'))['total'] or Decimal('0')
        
        average_quote_value = Quote.objects.filter(
            organization=org, status='submitted'
        ).aggregate(avg=Avg('total_amount'))['avg'] or Decimal('0')
        
        # Performance metrics
        average_supplier_rating = Supplier.objects.filter(
            organization=org, rating__isnull=False
        ).aggregate(avg=Avg('rating'))['avg'] or Decimal('0')
        
        stats_data = {
            'total_suppliers': total_suppliers,
            'active_suppliers': active_suppliers,
            'total_rfqs': total_rfqs,
            'open_rfqs': open_rfqs,
            'total_quotes': total_quotes,
            'pending_quotes': pending_quotes,
            'total_contracts': total_contracts,
            'active_contracts': active_contracts,
            'total_contract_value': total_contract_value,
            'average_quote_value': average_quote_value,
            'average_supplier_rating': average_supplier_rating,
            'average_response_time': 3.5,  # Placeholder - implement actual calculation
            'suppliers_by_country': {},  # Placeholder - implement actual aggregation
            'rfqs_by_status': {},  # Placeholder - implement actual aggregation
            'quotes_by_status': {},  # Placeholder - implement actual aggregation
            'contracts_by_type': {},  # Placeholder - implement actual aggregation
        }
        
        serializer = ProcurementStatsSerializer(stats_data)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def supplier_performance(self, request):
        """Get supplier performance analytics"""
        org = self.get_organization()
        suppliers = Supplier.objects.filter(organization=org, status='active')
        
        performance_data = []
        for supplier in suppliers:
            quotes = supplier.quotes.all()
            contracts = supplier.contracts.all()
            
            total_quotes = quotes.count()
            accepted_quotes = quotes.filter(status='accepted').count()
            total_contract_value = contracts.aggregate(
                total=Sum('total_value')
            )['total'] or Decimal('0')
            
            performance_data.append({
                'supplier': SupplierListSerializer(supplier).data,
                'performance_score': supplier.calculate_performance_score() or 0,
                'total_quotes': total_quotes,
                'accepted_quotes': accepted_quotes,
                'quote_acceptance_rate': (accepted_quotes / total_quotes * 100) if total_quotes > 0 else 0,
                'average_response_time': 2.5,  # Placeholder
                'total_contract_value': total_contract_value,
                'on_time_deliveries': 0,  # Placeholder
                'total_deliveries': 0,  # Placeholder
                'on_time_delivery_rate': supplier.on_time_delivery_rate or 0,
            })
        
        # Sort by performance score
        performance_data.sort(key=lambda x: x['performance_score'], reverse=True)
        
        return Response(performance_data)
    
    @action(detail=False, methods=['get'])
    def spending_analysis(self, request):
        """Get spending analysis"""
        org = self.get_organization()
        
        # Spending by supplier
        supplier_spending = Contract.objects.filter(
            organization=org, status='active'
        ).values('supplier__name').annotate(
            total_spend=Sum('total_value')
        ).order_by('-total_spend')[:10]
        
        # Spending by category (placeholder - would need category mapping)
        category_spending = {}
        
        # Monthly spending trend (placeholder)
        monthly_spending = {}
        
        return Response({
            'supplier_spending': list(supplier_spending),
            'category_spending': category_spending,
            'monthly_spending': monthly_spending,
            'total_spend': sum(item['total_spend'] for item in supplier_spending),
            'period': 'Current Year',
        })
    
    @action(detail=False, methods=['get'])
    def savings_analysis(self, request):
        """Get cost savings analysis"""
        org = self.get_organization()
        
        # Calculate savings from competitive bidding
        awarded_rfqs = RFQ.objects.filter(organization=org, status='awarded')
        total_savings = Decimal('0')
        
        for rfq in awarded_rfqs:
            quotes = rfq.quotes.filter(status='submitted')
            if quotes.count() > 1:
                lowest_quote = min(quotes, key=lambda q: q.total_amount)
                highest_quote = max(quotes, key=lambda q: q.total_amount)
                savings = highest_quote.total_amount - lowest_quote.total_amount
                total_savings += savings
        
        return Response({
            'total_savings': total_savings,
            'savings_percentage': 15.2,  # Placeholder
            'average_savings_per_rfq': total_savings / max(awarded_rfqs.count(), 1),
            'competitive_bidding_impact': {
                'rfqs_with_multiple_quotes': awarded_rfqs.count(),
                'average_quotes_per_rfq': 3.2,  # Placeholder
            }
        })