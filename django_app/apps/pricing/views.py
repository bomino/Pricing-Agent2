"""
Pricing views for material pricing and AI predictions
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from apps.core.mixins import OrganizationRequiredMixin, get_user_organization
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView, View
)
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Avg, Count, Max, Min, StdDev
from django.utils import timezone
from django.urls import reverse_lazy
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Material, Price, PricePrediction, Category, PriceAlert
from .api.serializers import (
    MaterialListSerializer as MaterialSerializer, 
    PriceHistorySerializer as PriceSerializer, 
    PricePredictionSerializer,
    CategorySerializer, 
    PriceAlertSerializer
)
from .filters import MaterialFilter, PriceFilter
import json
from datetime import timedelta


class MaterialListView(OrganizationRequiredMixin, ListView):
    """List materials"""
    model = Material
    template_name = 'pricing/materials.html'
    context_object_name = 'materials'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Material.objects.filter(
            organization=self.get_user_organization(),
            status='active'
        ).select_related('category').order_by('name')
        
        # Add search functionality
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search) |
                Q(code__icontains=search)
            )
        
        # Category filter
        category_id = self.request.GET.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        
        # Status filter
        status_filter = self.request.GET.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Add price annotations with different names to avoid conflict with model property
        thirty_days_ago = timezone.now() - timedelta(days=30)
        queryset = queryset.annotate(
            latest_price=Max('prices__price'),
            avg_price_30d=Avg('prices__price', filter=Q(prices__time__gte=thirty_days_ago)),
            price_count=Count('prices')  # Count of price records
        )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django.db.models import Avg
        
        organization = self.get_user_organization()
        
        context['categories'] = Category.objects.filter(
            organization=organization
        ).order_by('name')
        
        # Add statistics
        materials = Material.objects.filter(organization=organization)
        context['active_count'] = materials.filter(status='active').count()
        context['categories_count'] = Category.objects.filter(organization=organization).count()
        
        # Calculate average lead time
        avg_lead = materials.filter(lead_time_days__isnull=False).aggregate(
            avg=Avg('lead_time_days')
        )
        context['avg_lead_time'] = int(avg_lead['avg']) if avg_lead['avg'] else 0
        
        return context


class MaterialDetailView(OrganizationRequiredMixin, DetailView):
    """Material detail view with pricing history"""
    model = Material
    template_name = 'pricing/material_detail.html'
    context_object_name = 'material'
    
    def get_queryset(self):
        return Material.objects.filter(
            organization=self.get_user_organization()
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get recent prices for this material
        context['recent_prices'] = Price.objects.filter(
            material=self.object
        ).order_by('-time')[:10]
        
        # Get price statistics
        price_stats = Price.objects.filter(
            material=self.object,
            time__gte=timezone.now() - timezone.timedelta(days=30)
        ).aggregate(
            avg_price=Avg('price'),
            count=Count('id')
        )
        context['price_stats'] = price_stats
        
        return context


class MaterialCreateView(OrganizationRequiredMixin, CreateView):
    """Create new material"""
    model = Material
    template_name = 'pricing/material_form.html'
    fields = [
        'code', 'name', 'description', 'material_type', 'category', 
        'unit_of_measure', 'weight', 'weight_unit', 'status',
        'list_price', 'cost_price', 'currency', 
        'lead_time_days', 'minimum_order_quantity'
    ]
    success_url = reverse_lazy('pricing:material_list')
    
    def form_valid(self, form):
        form.instance.organization = self.get_user_organization()
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.filter(
            organization=self.get_user_organization()
        ).order_by('name')
        return context


class MaterialUpdateView(OrganizationRequiredMixin, UpdateView):
    """Update material"""
    model = Material
    template_name = 'pricing/material_form.html'
    fields = [
        'code', 'name', 'description', 'material_type', 'category', 
        'unit_of_measure', 'weight', 'weight_unit', 'status',
        'list_price', 'cost_price', 'currency', 
        'lead_time_days', 'minimum_order_quantity'
    ]
    success_url = reverse_lazy('pricing:material_list')
    
    def get_queryset(self):
        return Material.objects.filter(
            organization=self.get_user_organization()
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.filter(
            organization=self.get_user_organization()
        ).order_by('name')
        return context


class PriceListView(OrganizationRequiredMixin, ListView):
    """List prices"""
    model = Price
    template_name = 'pricing/price_history.html'
    context_object_name = 'price_history'
    paginate_by = 50
    
    def get_queryset(self):
        from .models import PriceHistory
        return PriceHistory.objects.filter(
            organization=self.get_user_organization()
        ).select_related('material').order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django.db.models import Count
        
        # Add statistics
        price_history = self.get_queryset()
        context['price_increases'] = price_history.filter(change_type='increase').count()
        context['price_decreases'] = price_history.filter(change_type='decrease').count()
        context['total_updates'] = price_history.count()
        
        # Add materials for filter dropdown
        context['materials'] = Material.objects.filter(
            organization=self.get_user_organization()
        ).order_by('name')
        
        return context


class PriceDetailView(OrganizationRequiredMixin, DetailView):
    """Price detail view"""
    model = Price
    template_name = 'pricing/price_detail.html'
    context_object_name = 'price'
    
    def get_queryset(self):
        return Price.objects.filter(
            organization=self.get_user_organization()
        ).select_related('material')


class BulkPriceUploadView(OrganizationRequiredMixin, TemplateView):
    """Bulk price upload view"""
    template_name = 'pricing/bulk_upload.html'
    
    def post(self, request, *args, **kwargs):
        # Handle CSV upload and processing
        # This is a placeholder for the actual implementation
        return JsonResponse({'status': 'success', 'message': 'Prices uploaded successfully'})


class PriceTrendView(OrganizationRequiredMixin, TemplateView):
    """Price trend analytics view"""
    template_name = 'pricing/price_trends.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get trending materials
        trending_materials = Material.objects.filter(
            organization=self.get_user_organization(),
            price__time__gte=timezone.now() - timezone.timedelta(days=30)
        ).annotate(
            price_count=Count('price'),
            avg_price=Avg('price__price')
        ).filter(price_count__gte=5).order_by('-price_count')[:10]
        
        context['trending_materials'] = trending_materials
        return context


class PricePredictionView(OrganizationRequiredMixin, TemplateView):
    """Price prediction view"""
    template_name = 'pricing/predictions.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get recent predictions
        recent_predictions = PricePrediction.objects.filter(
            organization=self.get_user_organization()
        ).select_related('material').order_by('-created_at')[:20]
        
        context['predictions'] = recent_predictions
        context['predictions_count'] = PricePrediction.objects.filter(
            organization=self.get_user_organization()
        ).count()
        
        return context


class PriceVolatilityView(OrganizationRequiredMixin, TemplateView):
    """Price volatility analysis view"""
    template_name = 'pricing/price_volatility.html'


class PricingDashboardView(OrganizationRequiredMixin, TemplateView):
    """Pricing dashboard with key metrics"""
    template_name = 'pricing/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = self.get_user_organization()
        
        # Get key metrics
        context['metrics'] = {
            'total_materials': Material.objects.filter(
                organization=organization, status='active'
            ).count(),
            'total_prices': Price.objects.filter(
                organization=organization,
                time__gte=timezone.now() - timezone.timedelta(days=30)
            ).count(),
            'active_predictions': PricePrediction.objects.filter(
                organization=organization,
                status='active'
            ).count(),
        }
        
        return context


# API ViewSets
class MaterialViewSet(viewsets.ModelViewSet):
    """Material API ViewSet"""
    serializer_class = MaterialSerializer
    permission_classes = [IsAuthenticated]
    filterset_class = MaterialFilter
    search_fields = ['name', 'description', 'category']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']
    
    def get_queryset(self):
        return Material.objects.filter(
            organization=self.get_user_organization(),
            status='active'
        )
    
    def perform_create(self, serializer):
        serializer.save(
            organization=self.get_user_organization(),
            created_by=self.request.user
        )
    
    @action(detail=True, methods=['get'])
    def prices(self, request, pk=None):
        """Get prices for a material"""
        material = self.get_object()
        prices = Price.objects.filter(material=material).order_by('-time')[:100]
        serializer = PriceSerializer(prices, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def predictions(self, request, pk=None):
        """Get predictions for a material"""
        material = self.get_object()
        predictions = PricePrediction.objects.filter(
            material=material, status='active'
        ).order_by('-created_at')
        serializer = PricePredictionSerializer(predictions, many=True)
        return Response(serializer.data)


class PriceViewSet(viewsets.ModelViewSet):
    """Price API ViewSet"""
    serializer_class = PriceSerializer
    permission_classes = [IsAuthenticated]
    filterset_class = PriceFilter
    ordering_fields = ['time', 'price']
    ordering = ['-time']
    
    def get_queryset(self):
        return Price.objects.filter(
            organization=self.get_user_organization()
        ).select_related('material')
    
    def perform_create(self, serializer):
        serializer.save(
            organization=self.get_user_organization()
        )


class PricePredictionViewSet(viewsets.ReadOnlyModelViewSet):
    """Price Prediction API ViewSet (read-only)"""
    serializer_class = PricePredictionSerializer
    permission_classes = [IsAuthenticated]
    ordering = ['-created_at']
    
    def get_queryset(self):
        return PricePrediction.objects.filter(
            organization=self.get_user_organization()
        ).select_related('material')
    
    @action(detail=False, methods=['post'])
    def request_prediction(self, request):
        """Request a new price prediction"""
        material_id = request.data.get('material_id')
        prediction_horizon = request.data.get('prediction_horizon', 30)  # days
        
        try:
            material = Material.objects.get(
                id=material_id,
                organization=get_user_organization(request.user)
            )
            
            # This would typically trigger ML service
            # For now, create a placeholder prediction
            prediction = PricePrediction.objects.create(
                material=material,
                organization=get_user_organization(request.user),
                prediction_horizon_days=prediction_horizon,
                status='pending'
            )
            
            serializer = PricePredictionSerializer(prediction)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Material.DoesNotExist:
            return Response(
                {'error': 'Material not found'},
                status=status.HTTP_404_NOT_FOUND
            )


# Additional Views for complete functionality
class MaterialDeleteView(OrganizationRequiredMixin, DeleteView):
    """Delete material"""
    model = Material
    success_url = reverse_lazy('pricing:material_list')
    
    def get_queryset(self):
        return Material.objects.filter(
            organization=self.get_user_organization()
        )


class MaterialPriceHistoryView(OrganizationRequiredMixin, View):
    """Get material price history for charts"""
    
    def get(self, request, pk):
        material = get_object_or_404(
            Material,
            pk=pk,
            organization=request.user.profile.organization
        )
        
        # Get price history for last 90 days
        ninety_days_ago = timezone.now() - timedelta(days=90)
        prices = Price.objects.filter(
            material=material,
            time__gte=ninety_days_ago
        ).order_by('time').values('time', 'price', 'supplier__name')
        
        # Calculate statistics
        price_stats = Price.objects.filter(
            material=material,
            time__gte=timezone.now() - timedelta(days=30)
        ).aggregate(
            current_price=Max('price'),
            avg_30d=Avg('price'),
            min_30d=Min('price'),
            max_30d=Max('price'),
            volatility=StdDev('price')
        )
        
        # Calculate price change
        recent_prices = list(prices)
        if len(recent_prices) >= 2:
            change = ((recent_prices[-1]['price'] - recent_prices[-2]['price']) / recent_prices[-2]['price']) * 100
        else:
            change = 0
        
        return JsonResponse({
            'material': {
                'id': material.id,
                'name': material.name,
                'code': material.code
            },
            'price_history': list(prices),
            'recent_prices': recent_prices[-10:],
            **price_stats,
            'change': change
        })


class CategoryListView(OrganizationRequiredMixin, ListView):
    """List categories"""
    model = Category
    template_name = 'pricing/category_list.html'
    context_object_name = 'categories'
    
    def get_queryset(self):
        return Category.objects.filter(
            organization=self.get_user_organization()
        ).annotate(material_count=Count('materials')).order_by('name')


class CategoryCreateView(OrganizationRequiredMixin, CreateView):
    """Create category"""
    model = Category
    template_name = 'pricing/category_form.html'
    fields = ['name', 'code', 'description', 'parent']
    success_url = reverse_lazy('pricing:category_list')
    
    def form_valid(self, form):
        form.instance.organization = self.get_user_organization()
        return super().form_valid(form)


class PriceBulkUpdateView(OrganizationRequiredMixin, View):
    """Bulk update prices"""
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            prices_updated = 0
            
            for price_data in data.get('prices', []):
                material = Material.objects.get(
                    id=price_data['material_id'],
                    organization=get_user_organization(request.user)
                )
                
                Price.objects.create(
                    material=material,
                    organization=get_user_organization(request.user),
                    price=price_data['price'],
                    supplier_id=price_data.get('supplier_id'),
                    time=timezone.now()
                )
                prices_updated += 1
            
            return JsonResponse({
                'status': 'success',
                'message': f'{prices_updated} prices updated successfully'
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)


class PredictionListView(OrganizationRequiredMixin, ListView):
    """List predictions"""
    model = PricePrediction
    template_name = 'pricing/prediction_list.html'
    context_object_name = 'predictions'
    paginate_by = 20
    
    def get_queryset(self):
        return PricePrediction.objects.filter(
            organization=self.get_user_organization()
        ).select_related('material').order_by('-created_at')


class GeneratePredictionsView(OrganizationRequiredMixin, View):
    """Generate AI predictions"""
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            material_ids = data.get('material_ids', [])
            horizon = data.get('horizon', 30)
            
            predictions_created = 0
            for material_id in material_ids:
                material = Material.objects.get(
                    id=material_id,
                    organization=get_user_organization(request.user)
                )
                
                # Here you would call your AI model
                # For now, create placeholder prediction
                PricePrediction.objects.create(
                    material=material,
                    organization=get_user_organization(request.user),
                    prediction_horizon_days=horizon,
                    status='pending'
                )
                predictions_created += 1
            
            return JsonResponse({
                'status': 'success',
                'message': f'{predictions_created} predictions requested'
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)


class AlertListView(OrganizationRequiredMixin, ListView):
    """List price alerts"""
    model = PriceAlert
    template_name = 'pricing/alerts.html'
    context_object_name = 'alerts'
    
    def get_queryset(self):
        return PriceAlert.objects.filter(
            organization=self.get_user_organization()
        ).select_related('material').order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django.utils import timezone
        from datetime import timedelta
        
        alerts = self.get_queryset()
        context['active_alerts'] = alerts.filter(status='active').count()
        context['triggered_today'] = alerts.filter(
            last_triggered__date=timezone.now().date()
        ).count()
        context['resolved_alerts'] = alerts.filter(status='resolved').count()
        context['total_alerts'] = alerts.count()
        
        # Add materials for create modal
        context['materials'] = Material.objects.filter(
            organization=self.get_user_organization()
        ).order_by('name')
        
        return context


class AlertCreateView(OrganizationRequiredMixin, CreateView):
    """Create price alert"""
    model = PriceAlert
    template_name = 'pricing/alert_form.html'
    fields = ['name', 'material', 'alert_type', 'condition_type', 'threshold_value', 'email_notification', 'push_notification']
    success_url = reverse_lazy('pricing:alert_list')
    
    def form_valid(self, form):
        form.instance.organization = self.get_user_organization()
        form.instance.user = self.request.user
        return super().form_valid(form)


class AlertUpdateView(OrganizationRequiredMixin, UpdateView):
    """Update price alert"""
    model = PriceAlert
    template_name = 'pricing/alert_form.html'
    fields = ['name', 'material', 'alert_type', 'condition_type', 'threshold_value', 'email_notification', 'push_notification', 'status']
    success_url = reverse_lazy('pricing:alert_list')
    
    def get_queryset(self):
        return PriceAlert.objects.filter(
            organization=self.get_user_organization()
        )


class MaterialRowView(OrganizationRequiredMixin, View):
    """HTMX partial for material row"""
    
    def get(self, request, pk):
        material = get_object_or_404(
            Material,
            pk=pk,
            organization=request.user.profile.organization
        )
        return render(request, 'pricing/partials/material_row.html', {'material': material})


class PriceChartView(OrganizationRequiredMixin, View):
    """HTMX partial for price chart"""
    
    def get(self, request, material_id):
        material = get_object_or_404(
            Material,
            pk=material_id,
            organization=request.user.profile.organization
        )
        
        # Get price data for chart
        thirty_days_ago = timezone.now() - timedelta(days=30)
        prices = Price.objects.filter(
            material=material,
            time__gte=thirty_days_ago
        ).order_by('time').values('time', 'price')
        
        return render(request, 'pricing/partials/price_chart.html', {
            'material': material,
            'price_data': list(prices)
        })


class MaterialSearchView(OrganizationRequiredMixin, View):
    """HTMX search for materials"""
    
    def get(self, request):
        query = request.GET.get('q', '')
        materials = Material.objects.filter(
            organization=request.user.profile.organization,
            status='active'
        ).filter(
            Q(name__icontains=query) |
            Q(code__icontains=query) |
            Q(description__icontains=query)
        ).select_related('category')[:20]
        
        return render(request, 'pricing/partials/material_search_results.html', {
            'materials': materials
        })


# Additional API ViewSets
class CategoryViewSet(viewsets.ModelViewSet):
    """Category API ViewSet"""
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Category.objects.filter(
            organization=self.get_user_organization()
        )
    
    def perform_create(self, serializer):
        serializer.save(organization=self.get_user_organization())


class PriceAlertViewSet(viewsets.ModelViewSet):
    """Price Alert API ViewSet"""
    serializer_class = PriceAlertSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return PriceAlert.objects.filter(
            organization=self.get_user_organization()
        ).select_related('material')
    
    def perform_create(self, serializer):
        serializer.save(
            organization=self.get_user_organization(),
            user=self.request.user
        )