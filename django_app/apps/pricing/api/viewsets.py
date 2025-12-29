"""
ViewSets for pricing API endpoints
"""
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, List

from django.utils import timezone
from django.db.models import Q, Avg, Min, Max, Count
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from apps.pricing.models import (
    Material,
    Price,
    PriceBenchmark,
    PriceAlert,
    CostModel,
)
from apps.core.models import Category
from apps.core.authentication import MLServiceClient
from apps.core.exceptions import (
    MaterialNotFound,
    MLServiceError,
    MLServiceUnavailable,
    InvalidPredictionRequest,
)
from apps.core.pagination import StandardResultsSetPagination, LargeResultsSetPagination
from apps.pricing.api.serializers import (
    MaterialListSerializer,
    MaterialDetailSerializer,
    MaterialHTMXSerializer,
    PriceHistorySerializer,
    PriceCreateSerializer,
    PriceBenchmarkSerializer,
    PriceAlertSerializer,
    CostModelSerializer,
    PricePredictionRequestSerializer,
    BatchPredictionRequestSerializer,
    AnomalyDetectionRequestSerializer,
    TrendAnalysisRequestSerializer,
    PriceChartDataSerializer,
    CategorySerializer,
)
from apps.pricing.filters import MaterialFilter, PriceFilter


class MaterialViewSet(viewsets.ModelViewSet):
    """ViewSet for Material CRUD operations"""
    
    serializer_class = MaterialListSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = MaterialFilter
    search_fields = ['code', 'name', 'description', 'search_keywords']
    ordering_fields = ['code', 'name', 'created_at', 'updated_at', 'list_price']
    ordering = ['code']
    
    def get_queryset(self):
        """Filter by organization"""
        return Material.objects.filter(
            organization=self.request.organization
        ).select_related('category', 'organization')
    
    def get_serializer_class(self):
        """Use different serializers for different actions"""
        if self.action == 'retrieve':
            return MaterialDetailSerializer
        elif self.action in ['list_htmx', 'search_htmx']:
            return MaterialHTMXSerializer
        return MaterialListSerializer
    
    def perform_create(self, serializer):
        """Set organization when creating"""
        serializer.save(organization=self.request.organization)
    
    @action(detail=True, methods=['get'])
    def price_history(self, request, pk=None):
        """Get price history for a material"""
        material = self.get_object()
        days = int(request.query_params.get('days', 90))
        price_type = request.query_params.get('price_type')
        
        prices = material.get_price_history(days=days, price_type=price_type)
        serializer = PriceHistorySerializer(prices, many=True)
        
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def price_chart_data(self, request, pk=None):
        """Get price chart data for visualization"""
        material = self.get_object()
        days = int(request.query_params.get('days', 90))
        
        prices = material.prices.filter(
            time__gte=timezone.now() - timedelta(days=days)
        ).order_by('time')
        
        chart_data = []
        for price in prices:
            chart_data.append({
                'date': price.time,
                'price': price.price,
                'supplier': price.supplier.name if price.supplier else '',
                'price_type': price.price_type,
            })
        
        serializer = PriceChartDataSerializer(chart_data, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def predict_price(self, request, pk=None):
        """Get ML price prediction for a material"""
        material = self.get_object()
        
        serializer = PricePredictionRequestSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        
        try:
            # Call ML service for prediction
            ml_client = MLServiceClient()
            prediction = asyncio.run(ml_client.predict_price(
                material_id=str(material.id),
                quantity=float(serializer.validated_data['quantity']),
                user=request.user,
                **{k: v for k, v in serializer.validated_data.items() 
                   if k not in ['material_id', 'quantity']}
            ))
            
            return Response(prediction)
            
        except Exception as e:
            if "unavailable" in str(e).lower():
                raise MLServiceUnavailable()
            else:
                raise MLServiceError(str(e))
    
    @action(detail=True, methods=['get'])
    def should_cost(self, request, pk=None):
        """Calculate should-cost for a material"""
        material = self.get_object()
        
        try:
            should_cost = material.calculate_should_cost()
            
            # Get cost breakdown if available
            cost_models = material.cost_models.filter(is_active=True)
            cost_breakdown = {}
            
            for model in cost_models:
                cost_breakdown[model.name] = {
                    'type': model.model_type,
                    'version': model.version,
                    'cost_drivers': model.cost_drivers,
                    'accuracy_score': float(model.accuracy_score) if model.accuracy_score else None,
                }
            
            return Response({
                'material_id': str(material.id),
                'should_cost': should_cost,
                'currency': material.currency,
                'cost_breakdown': cost_breakdown,
                'calculated_at': timezone.now(),
            })
            
        except Exception as e:
            return Response(
                {'error': f'Failed to calculate should-cost: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def benchmarks(self, request, pk=None):
        """Get price benchmarks for a material"""
        material = self.get_object()
        benchmarks = material.benchmarks.all().order_by('-period_end')
        
        serializer = PriceBenchmarkSerializer(benchmarks, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def search_htmx(self, request):
        """HTMX-compatible search endpoint"""
        queryset = self.filter_queryset(self.get_queryset())
        
        # Limit results for HTMX
        queryset = queryset[:20]
        
        serializer = MaterialHTMXSerializer(queryset, many=True)
        
        if request.htmx:
            # Return HTMX template name for rendering
            return Response({
                'results': serializer.data,
                'template_name': 'partials/pricing/material_search_results.html'
            })
        
        return Response(serializer.data)


class CategoryViewSet(viewsets.ModelViewSet):
    """ViewSet for Category CRUD operations"""
    
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['name', 'code', 'level']
    ordering = ['level', 'name']
    
    @action(detail=False, methods=['get'])
    def tree(self, request):
        """Get category tree structure"""
        categories = Category.objects.filter(is_active=True).order_by('level', 'name')
        
        # Build tree structure
        tree = {}
        category_dict = {}
        
        for category in categories:
            category_data = CategorySerializer(category).data
            category_dict[category.id] = category_data
            
            if category.parent_id:
                parent = category_dict.get(category.parent_id)
                if parent:
                    if 'children' not in parent:
                        parent['children'] = []
                    parent['children'].append(category_data)
            else:
                tree[category.id] = category_data
        
        return Response(list(tree.values()))


class PriceViewSet(viewsets.ModelViewSet):
    """ViewSet for Price CRUD operations"""
    
    serializer_class = PriceHistorySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = LargeResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = PriceFilter
    ordering_fields = ['time', 'price', 'material__code']
    ordering = ['-time']
    
    def get_queryset(self):
        """Filter by organization"""
        return Price.objects.filter(
            organization=self.request.organization
        ).select_related('material', 'supplier')
    
    def get_serializer_class(self):
        """Use create serializer for create action"""
        if self.action == 'create':
            return PriceCreateSerializer
        return PriceHistorySerializer
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get price statistics"""
        queryset = self.filter_queryset(self.get_queryset())
        
        stats = queryset.aggregate(
            total_prices=Count('id'),
            avg_price=Avg('price'),
            min_price=Min('price'),
            max_price=Max('price'),
        )
        
        # Price type distribution
        price_type_dist = {}
        for price_type, count in queryset.values_list('price_type').annotate(count=Count('id')):
            price_type_dist[price_type] = count
        
        stats['price_type_distribution'] = price_type_dist
        
        return Response(stats)
    
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """Create multiple price records"""
        if not isinstance(request.data, list):
            return Response(
                {'error': 'Expected a list of price records'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(request.data) > 1000:
            return Response(
                {'error': 'Maximum 1000 price records per request'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = PriceCreateSerializer(
            data=request.data,
            many=True,
            context={'request': request}
        )
        
        if serializer.is_valid():
            prices = serializer.save()
            return Response(
                {
                    'created_count': len(prices),
                    'prices': PriceHistorySerializer(prices, many=True).data
                },
                status=status.HTTP_201_CREATED
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BenchmarkViewSet(viewsets.ModelViewSet):
    """ViewSet for PriceBenchmark CRUD operations"""
    
    serializer_class = PriceBenchmarkSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = ['period_end', 'benchmark_price', 'benchmark_type']
    ordering = ['-period_end']
    
    def get_queryset(self):
        """Filter by organization"""
        return PriceBenchmark.objects.filter(
            organization=self.request.organization
        ).select_related('material')
    
    @action(detail=False, methods=['post'])
    def calculate(self, request):
        """Calculate benchmarks for materials"""
        material_ids = request.data.get('material_ids', [])
        benchmark_types = request.data.get('benchmark_types', ['market_average'])
        period_days = request.data.get('period_days', 90)
        
        if not material_ids:
            return Response(
                {'error': 'material_ids required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        results = []
        errors = []
        
        for material_id in material_ids:
            try:
                material = Material.objects.get(
                    id=material_id,
                    organization=request.organization
                )
                
                # Calculate benchmarks for each type
                for benchmark_type in benchmark_types:
                    try:
                        benchmark = self._calculate_benchmark(
                            material, benchmark_type, period_days
                        )
                        results.append(benchmark)
                    except Exception as e:
                        errors.append({
                            'material_id': material_id,
                            'benchmark_type': benchmark_type,
                            'error': str(e)
                        })
                        
            except Material.DoesNotExist:
                errors.append({
                    'material_id': material_id,
                    'error': 'Material not found'
                })
        
        return Response({
            'benchmarks': results,
            'errors': errors,
            'created_count': len(results),
        })
    
    def _calculate_benchmark(self, material, benchmark_type, period_days):
        """Calculate benchmark for a material"""
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=period_days)
        
        prices = Price.objects.filter(
            material=material,
            time__date__range=[start_date, end_date],
            organization=material.organization,
        )
        
        if not prices.exists():
            raise ValueError("No price data available for benchmark calculation")
        
        if benchmark_type == 'market_average':
            benchmark_price = prices.aggregate(avg_price=Avg('price'))['avg_price']
        elif benchmark_type == 'lowest_quote':
            benchmark_price = prices.filter(price_type='quote').aggregate(
                min_price=Min('price')
            )['min_price']
        elif benchmark_type == 'historical_average':
            benchmark_price = prices.aggregate(avg_price=Avg('price'))['avg_price']
        else:
            raise ValueError(f"Unknown benchmark type: {benchmark_type}")
        
        if not benchmark_price:
            raise ValueError(f"Could not calculate {benchmark_type} benchmark")
        
        # Create benchmark record
        benchmark = PriceBenchmark.objects.create(
            material=material,
            organization=material.organization,
            benchmark_type=benchmark_type,
            benchmark_price=benchmark_price,
            currency=material.currency,
            quantity=Decimal('1.0'),
            period_start=start_date,
            period_end=end_date,
            sample_size=prices.count(),
            min_price=prices.aggregate(min_price=Min('price'))['min_price'],
            max_price=prices.aggregate(max_price=Max('price'))['max_price'],
        )
        
        return PriceBenchmarkSerializer(benchmark).data


class PriceAlertViewSet(viewsets.ModelViewSet):
    """ViewSet for PriceAlert CRUD operations"""
    
    serializer_class = PriceAlertSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = ['created_at', 'last_triggered', 'status']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter by organization and user"""
        return PriceAlert.objects.filter(
            organization=self.request.organization,
            user=self.request.user
        ).select_related('material')
    
    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """Test a price alert"""
        alert = self.get_object()
        
        # Get current price for testing
        current_price = alert.material.current_price
        if not current_price:
            return Response(
                {'error': 'No current price available for testing'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check condition
        condition_met = alert.check_condition(current_price)
        
        return Response({
            'alert_id': str(alert.id),
            'current_price': current_price,
            'threshold_value': alert.threshold_value,
            'condition_type': alert.condition_type,
            'condition_met': condition_met,
            'would_trigger': condition_met and alert.status == 'active',
        })


# ML Integration ViewSets
class MLAnalyticsViewSet(viewsets.ViewSet):
    """ViewSet for ML analytics endpoints"""
    
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def detect_anomalies(self, request):
        """Detect price anomalies using ML"""
        serializer = AnomalyDetectionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            ml_client = MLServiceClient()
            result = asyncio.run(ml_client.detect_anomalies(
                prices=serializer.validated_data['prices'],
                user=request.user
            ))
            
            return Response(result)
            
        except Exception as e:
            if "unavailable" in str(e).lower():
                raise MLServiceUnavailable()
            else:
                raise MLServiceError(str(e))
    
    @action(detail=False, methods=['post'])
    def analyze_trends(self, request):
        """Analyze price trends using ML"""
        serializer = TrendAnalysisRequestSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        
        try:
            ml_client = MLServiceClient()
            result = asyncio.run(ml_client.analyze_trends(
                material_id=serializer.validated_data['material_id'],
                period_days=serializer.validated_data['period_days'],
                include_forecast=serializer.validated_data['include_forecast'],
                forecast_days=serializer.validated_data['forecast_days'],
                user=request.user
            ))
            
            return Response(result)
            
        except Exception as e:
            if "unavailable" in str(e).lower():
                raise MLServiceUnavailable()
            else:
                raise MLServiceError(str(e))
    
    @action(detail=False, methods=['post'])
    def batch_predict(self, request):
        """Batch price predictions using ML"""
        serializer = BatchPredictionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            ml_client = MLServiceClient()
            result = asyncio.run(ml_client.batch_predict(
                predictions=serializer.validated_data['predictions'],
                user=request.user
            ))
            
            return Response(result)
            
        except Exception as e:
            if "unavailable" in str(e).lower():
                raise MLServiceUnavailable()
            else:
                raise MLServiceError(str(e))