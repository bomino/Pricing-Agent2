"""
Analytics views for business intelligence and reporting
"""
from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from apps.core.mixins import OrganizationRequiredMixin, get_user_organization
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, TemplateView
)
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Avg, Count, Sum, F
from django.utils import timezone
from datetime import timedelta
import csv
import json
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Report, AnalyticsDashboard as Dashboard, DashboardMetric as MetricDefinition
from .serializers import (
    ReportSerializer, AnalyticsDashboardSerializer as DashboardSerializer,
    ReportSummarySerializer, AnalyticsDashboardSummarySerializer as DashboardSummarySerializer
)
from .services import AnalyticsService


class AnalyticsDashboardView(OrganizationRequiredMixin, TemplateView):
    """Analytics and insights center - legacy view
    
    Note: This view has been replaced by AnalyticsCenterView which provides
    a better tabbed interface with HTMX for dynamic content loading.
    Kept for backward compatibility.
    """
    template_name = 'analytics/analytics_center.html'  # Use original template for testing
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get organization - handle users without profiles
        organization = self.get_user_organization()
        if not organization:
            # For superusers or users without profile, get first organization
            from apps.core.models import Organization
            organization = Organization.objects.first()
            if not organization:
                # Create a default organization if none exists
                organization = Organization.objects.create(
                    name='Default Organization',
                    code='DEFAULT'
                )
        
        # Use the analytics service to get insights and analytics data
        analytics_service = AnalyticsService(organization)
        
        # Get savings opportunities with more detail
        savings_data = analytics_service._get_savings_opportunities()
        opportunities = []
        for opp in savings_data.get('opportunities', [])[:5]:
            opportunities.append({
                'material': opp.get('material', 'Unknown'),
                'recommendation': self._get_recommendation_text(opp),
                'potential_saving_pct': opp.get('potential_saving_pct', 0),
                'data_points': opp.get('order_count', 0)
            })
        
        # Detect price anomalies
        anomalies = self._detect_price_anomalies(organization)
        
        # Get predictions (placeholder for now - will integrate ML later)
        predictions = self._get_price_predictions(organization)
        
        # Performance metrics for insights
        metrics = {
            'supplier_consolidation': self._calculate_supplier_consolidation(organization),
            'contract_compliance': 85,  # Placeholder
            'maverick_spend': 12,  # Placeholder
        }
        
        # Get benchmarking data (placeholder)
        benchmarks = [
            {'metric': 'Cost per Order', 'your_value': '$125', 'industry_avg': '$150', 'best_in_class': '$95', 'gap': -17},
            {'metric': 'Supplier Lead Time', 'your_value': '7 days', 'industry_avg': '10 days', 'best_in_class': '5 days', 'gap': 30},
            {'metric': 'First-Time Quality', 'your_value': '92%', 'industry_avg': '88%', 'best_in_class': '95%', 'gap': 5},
        ]
        
        # Get recent reports
        recent_reports = Report.objects.filter(
            organization=organization
        ).order_by('-created_at')[:5]
        
        context.update({
            'organization': organization,
            'opportunities': opportunities,
            'anomalies': anomalies,
            'predictions': predictions,
            'metrics': metrics,
            'benchmarks': benchmarks,
            'recent_reports': recent_reports,
        })
        
        return context
    
    def _get_recommendation_text(self, opportunity):
        """Generate recommendation text based on opportunity type"""
        opp_type = opportunity.get('type', '')
        if opp_type == 'price_variance':
            return f"Switch to {opportunity.get('recommended_supplier', 'alternative supplier')} for {opportunity.get('potential_saving_pct', 0)}% savings"
        elif opp_type == 'volume_consolidation':
            return f"Consolidate {opportunity.get('small_orders', 0)} small orders into bulk purchases"
        elif opp_type == 'contract_negotiation':
            return "Renegotiate contract based on increased volume"
        else:
            return "Review procurement strategy for cost optimization"
    
    def _detect_price_anomalies(self, organization):
        """Detect price anomalies in recent purchases"""
        from apps.procurement.models import PurchaseOrder
        from apps.pricing.models import Material
        from django.db.models import Avg, StdDev
        
        anomalies = []
        
        # Get materials with significant price variations
        materials = Material.objects.filter(
            organization=organization,
            purchaseorderline__isnull=False
        ).distinct()[:10]
        
        for material in materials:
            # Calculate average and standard deviation
            price_stats = PurchaseOrder.objects.filter(
                organization=organization,
                lines__material=material
            ).aggregate(
                avg_price=Avg('lines__unit_price'),
                std_price=StdDev('lines__unit_price')
            )
            
            if price_stats['avg_price'] and price_stats['std_price']:
                # Find orders with prices > 2 standard deviations from mean
                threshold = float(price_stats['avg_price']) + (2 * float(price_stats['std_price'] or 0))
                
                anomalous_orders = PurchaseOrder.objects.filter(
                    organization=organization,
                    lines__material=material,
                    lines__unit_price__gt=threshold
                ).select_related('supplier')[:3]
                
                for order in anomalous_orders:
                    if order.supplier:
                        deviation = ((float(order.lines.first().unit_price) - float(price_stats['avg_price'])) / float(price_stats['avg_price'])) * 100
                        anomalies.append({
                            'material': material.name,
                            'supplier': order.supplier.name,
                            'deviation': round(deviation, 1)
                        })
        
        return anomalies[:5]  # Return top 5 anomalies
    
    def _get_price_predictions(self, organization):
        """Get price predictions for key materials"""
        from apps.pricing.models import Material, Price
        from decimal import Decimal
        import random  # Placeholder for ML predictions
        
        predictions = []
        
        # Get top materials by spend
        top_materials = Material.objects.filter(
            organization=organization,
            purchaseorderline__isnull=False
        ).distinct()[:5]
        
        for material in top_materials:
            # Get current price
            current_price = Price.objects.filter(
                material=material,
                organization=organization
            ).order_by('-time').first()
            
            if current_price:
                # Placeholder prediction logic (will be replaced with ML)
                change = random.uniform(-10, 15)  # Random change for demo
                predicted = float(current_price.price) * (1 + change/100)
                
                predictions.append({
                    'material': material.name,
                    'current_price': float(current_price.price),
                    'predicted_price': round(predicted, 2),
                    'change': round(change, 1)
                })
        
        return predictions
    
    def _calculate_supplier_consolidation(self, organization):
        """Calculate supplier consolidation opportunity percentage"""
        from apps.procurement.models import Supplier, PurchaseOrder
        from django.db.models import Count, Sum
        
        # Get supplier distribution
        supplier_stats = PurchaseOrder.objects.filter(
            organization=organization
        ).values('supplier').annotate(
            order_count=Count('id'),
            total_spend=Sum('total_amount')
        ).filter(supplier__isnull=False)
        
        if not supplier_stats:
            return 0
        
        # Calculate if too many suppliers for small orders
        total_suppliers = len(supplier_stats)
        small_suppliers = len([s for s in supplier_stats if s['order_count'] < 3])
        
        if total_suppliers > 0:
            consolidation_opportunity = (small_suppliers / total_suppliers) * 100
            return round(consolidation_opportunity, 1)
        
        return 0


class DashboardListView(OrganizationRequiredMixin, ListView):
    """List custom dashboards"""
    model = Dashboard
    template_name = 'analytics/dashboard_list.html'
    context_object_name = 'dashboards'
    
    def get_queryset(self):
        return Dashboard.objects.filter(
            organization=self.get_user_organization()
        ).order_by('name')


class DashboardDetailView(OrganizationRequiredMixin, DetailView):
    """Dashboard detail view"""
    model = Dashboard
    template_name = 'analytics/dashboard_detail.html'
    context_object_name = 'dashboard'
    
    def get_queryset(self):
        return Dashboard.objects.filter(
            organization=self.get_user_organization()
        )


class ReportListView(OrganizationRequiredMixin, ListView):
    """List reports"""
    model = Report
    template_name = 'analytics/report_list.html'
    context_object_name = 'reports'
    paginate_by = 20
    
    def get_queryset(self):
        return Report.objects.filter(
            organization=self.get_user_organization()
        ).order_by('-created_at')


class ReportDetailView(OrganizationRequiredMixin, DetailView):
    """Report detail view"""
    model = Report
    template_name = 'analytics/report_detail.html'
    context_object_name = 'report'
    
    def get_queryset(self):
        return Report.objects.filter(
            organization=self.get_user_organization()
        )


class ReportGenerateView(OrganizationRequiredMixin, TemplateView):
    """Generate new report"""
    template_name = 'analytics/report_generate.html'
    
    def post(self, request, *args, **kwargs):
        report_type = request.POST.get('report_type')
        date_from = request.POST.get('date_from')
        date_to = request.POST.get('date_to')
        
        # Create new report
        report = Report.objects.create(
            name=f"{report_type.title()} Report",
            report_type=report_type,
            organization=get_user_organization(request.user),
            created_by=request.user,
            parameters={'date_from': date_from, 'date_to': date_to},
            status='generating'
        )
        
        # This would typically trigger async report generation
        # For now, just mark as completed
        report.status = 'completed'
        report.save()
        
        return JsonResponse({
            'status': 'success',
            'report_id': report.id,
            'message': 'Report generated successfully'
        })


# Data Export Views
class PricingDataExportView(OrganizationRequiredMixin, TemplateView):
    """Export pricing data"""
    
    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="pricing_data.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Material', 'Price', 'Date', 'Source', 'Currency'])
        
        from apps.pricing.models import Price
        prices = Price.objects.filter(
            organization=request.user.profile.organization
        ).select_related('material').order_by('-time')[:1000]
        
        for price in prices:
            writer.writerow([
                price.material.name,
                price.price,
                price.time.strftime('%Y-%m-%d %H:%M:%S'),
                price.source,
                price.currency
            ])
        
        return response


class ProcurementDataExportView(OrganizationRequiredMixin, TemplateView):
    """Export procurement data"""
    
    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="procurement_data.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['RFQ', 'Supplier', 'Quote Value', 'Status', 'Date'])
        
        from apps.procurement.models import Quote
        quotes = Quote.objects.filter(
            organization=request.user.profile.organization
        ).select_related('rfq', 'supplier').order_by('-created_at')[:1000]
        
        for quote in quotes:
            writer.writerow([
                quote.rfq.title,
                quote.supplier.name,
                quote.total_value or 0,
                quote.status,
                quote.created_at.strftime('%Y-%m-%d')
            ])
        
        return response


class SupplierDataExportView(OrganizationRequiredMixin, TemplateView):
    """Export supplier data"""
    
    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="supplier_data.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Name', 'Category', 'Contact Email', 'Status', 'Country'])
        
        from apps.procurement.models import Supplier
        suppliers = Supplier.objects.filter(
            organization=request.user.profile.organization
        ).order_by('name')
        
        for supplier in suppliers:
            writer.writerow([
                supplier.name,
                supplier.category,
                supplier.contact_email,
                supplier.status,
                supplier.country
            ])
        
        return response


# Metrics Views
class PricingMetricsView(OrganizationRequiredMixin, TemplateView):
    """Pricing metrics API"""
    
    def get(self, request, *args, **kwargs):
        from apps.pricing.models import Material, Price
        organization = get_user_organization(request.user)
        
        # Calculate key pricing metrics
        metrics = {
            'total_materials': Material.objects.filter(
                organization=organization
            ).count(),
            'price_updates_today': Price.objects.filter(
                organization=organization,
                time__gte=timezone.now().replace(hour=0, minute=0, second=0)
            ).count(),
            'avg_price_by_category': list(
                Price.objects.filter(
                    organization=organization,
                    time__gte=timezone.now() - timedelta(days=30)
                ).values('material__category').annotate(
                    avg_price=Avg('price')
                ).order_by('material__category')
            ),
            'price_trend': self._get_price_trend(organization),
        }
        
        return JsonResponse(metrics)
    
    def _get_price_trend(self, organization):
        """Get price trend data for charts"""
        from apps.pricing.models import Price
        
        # Get daily average prices for the last 30 days
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
        
        trend_data = []
        current_date = start_date
        
        while current_date <= end_date:
            daily_avg = Price.objects.filter(
                organization=organization,
                time__date=current_date
            ).aggregate(avg_price=Avg('price'))['avg_price']
            
            trend_data.append({
                'date': current_date.strftime('%Y-%m-%d'),
                'avg_price': float(daily_avg) if daily_avg else 0
            })
            
            current_date += timedelta(days=1)
        
        return trend_data


class ProcurementMetricsView(OrganizationRequiredMixin, TemplateView):
    """Procurement metrics API"""
    
    def get(self, request, *args, **kwargs):
        from apps.procurement.models import RFQ, Quote, Supplier
        organization = get_user_organization(request.user)
        
        metrics = {
            'active_rfqs': RFQ.objects.filter(
                organization=organization,
                status__in=['published', 'open']
            ).count(),
            'quotes_this_month': Quote.objects.filter(
                organization=organization,
                created_at__gte=timezone.now().replace(day=1)
            ).count(),
            'supplier_response_rate': self._calculate_supplier_response_rate(organization),
            'avg_quote_value': Quote.objects.filter(
                organization=organization,
                total_value__isnull=False
            ).aggregate(avg=Avg('total_value'))['avg'] or 0,
        }
        
        return JsonResponse(metrics)
    
    def _calculate_supplier_response_rate(self, organization):
        """Calculate supplier response rate"""
        from apps.procurement.models import RFQ, Quote
        
        total_rfq_supplier_invitations = RFQ.objects.filter(
            organization=organization
        ).aggregate(
            total=Sum('suppliers__count')
        )['total'] or 0
        
        total_quotes = Quote.objects.filter(
            organization=organization
        ).count()
        
        if total_rfq_supplier_invitations > 0:
            return round((total_quotes / total_rfq_supplier_invitations) * 100, 2)
        return 0


class SupplierMetricsView(OrganizationRequiredMixin, TemplateView):
    """Supplier metrics API"""
    
    def get(self, request, *args, **kwargs):
        from apps.procurement.models import Supplier, Quote
        organization = get_user_organization(request.user)
        
        metrics = {
            'total_suppliers': Supplier.objects.filter(
                organization=organization
            ).count(),
            'active_suppliers': Supplier.objects.filter(
                organization=organization,
                status='active'
            ).count(),
            'top_suppliers_by_quotes': list(
                Supplier.objects.filter(
                    organization=organization
                ).annotate(
                    quote_count=Count('quote')
                ).order_by('-quote_count')[:10].values('name', 'quote_count')
            ),
            'supplier_performance': self._get_supplier_performance(organization),
        }
        
        return JsonResponse(metrics)
    
    def _get_supplier_performance(self, organization):
        """Get supplier performance metrics"""
        from apps.procurement.models import Supplier
        
        return list(
            Supplier.objects.filter(
                organization=organization,
                quote__isnull=False
            ).annotate(
                total_quotes=Count('quote'),
                approved_quotes=Count('quote', filter=Q(quote__status='approved')),
                avg_quote_value=Avg('quote__total_value')
            ).values(
                'name', 'total_quotes', 'approved_quotes', 'avg_quote_value'
            )[:20]
        )


# Chart Views
class PriceTrendChartView(OrganizationRequiredMixin, TemplateView):
    """Price trend chart data"""
    
    def get(self, request, *args, **kwargs):
        material_id = request.GET.get('material_id')
        days = int(request.GET.get('days', 30))
        
        from apps.pricing.models import Price, Material
        
        if material_id:
            try:
                material = Material.objects.get(
                    id=material_id,
                    organization=get_user_organization(request.user)
                )
                
                prices = Price.objects.filter(
                    material=material,
                    time__gte=timezone.now() - timedelta(days=days)
                ).order_by('time').values('time', 'price')
                
                chart_data = {
                    'material': material.name,
                    'data': [
                        {
                            'date': price['time'].strftime('%Y-%m-%d'),
                            'price': float(price['price'])
                        }
                        for price in prices
                    ]
                }
                
                return JsonResponse(chart_data)
                
            except Material.DoesNotExist:
                pass
        
        return JsonResponse({'error': 'Material not found'}, status=404)


class SupplierPerformanceChartView(OrganizationRequiredMixin, TemplateView):
    """Supplier performance chart data"""
    
    def get(self, request, *args, **kwargs):
        from apps.procurement.models import Supplier
        
        suppliers_data = list(
            Supplier.objects.filter(
                organization=get_user_organization(request.user),
                quote__isnull=False
            ).annotate(
                total_quotes=Count('quote'),
                approved_quotes=Count('quote', filter=Q(quote__status='approved'))
            ).values('name', 'total_quotes', 'approved_quotes')[:10]
        )
        
        # Calculate approval rates
        for supplier in suppliers_data:
            if supplier['total_quotes'] > 0:
                supplier['approval_rate'] = round(
                    (supplier['approved_quotes'] / supplier['total_quotes']) * 100, 2
                )
            else:
                supplier['approval_rate'] = 0
        
        return JsonResponse({'suppliers': suppliers_data})


class CostAnalysisChartView(OrganizationRequiredMixin, TemplateView):
    """Cost analysis chart data"""
    
    def get(self, request, *args, **kwargs):
        from apps.procurement.models import Quote
        from apps.pricing.models import Price
        
        # Get cost breakdown by category
        quote_costs = list(
            Quote.objects.filter(
                organization=get_user_organization(request.user),
                status='approved',
                total_value__isnull=False
            ).values('supplier__category').annotate(
                total_cost=Sum('total_value'),
                avg_cost=Avg('total_value'),
                count=Count('id')
            ).order_by('-total_cost')
        )
        
        return JsonResponse({'cost_breakdown': quote_costs})


# API ViewSets
class ReportViewSet(viewsets.ModelViewSet):
    """Report API ViewSet"""
    serializer_class = ReportSerializer
    permission_classes = [IsAuthenticated]
    ordering = ['-created_at']
    
    def get_queryset(self):
        return Report.objects.filter(
            organization=self.get_user_organization()
        )
    
    def perform_create(self, serializer):
        serializer.save(
            organization=self.get_user_organization(),
            created_by=self.request.user
        )


class DashboardViewSet(viewsets.ModelViewSet):
    """Dashboard API ViewSet"""
    serializer_class = DashboardSerializer
    permission_classes = [IsAuthenticated]
    ordering = ['name']
    
    def get_queryset(self):
        return Dashboard.objects.filter(
            organization=self.get_user_organization()
        )
    
    def perform_create(self, serializer):
        serializer.save(
            organization=self.get_user_organization(),
            created_by=self.request.user
        )


# Tab Views for HTMX
class InsightsTabView(OrganizationRequiredMixin, TemplateView):
    """Key insights tab showing savings opportunities and anomalies
    
    Displays:
    - Top 5 savings opportunities with recommendations
    - Price anomalies detected using statistical analysis (2 std dev threshold)
    - Supplier consolidation metrics
    
    Loaded via HTMX when user clicks the Insights tab in analytics center.
    Uses card-based UI with hover effects for consistent styling.
    """
    template_name = 'analytics/tabs/insights.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = self.get_user_organization()
        
        analytics_service = AnalyticsService(organization)
        
        # Get savings opportunities
        savings_data = analytics_service._get_savings_opportunities()
        opportunities = []
        for opp in savings_data.get('opportunities', [])[:5]:
            opportunities.append({
                'material': opp.get('material', 'Unknown'),
                'recommendation': self._get_recommendation_text(opp),
                'potential_saving_pct': opp.get('potential_saving_pct', 0),
                'data_points': opp.get('order_count', 0)
            })
        
        # Detect price anomalies
        anomalies = self._detect_price_anomalies(organization)
        
        # Performance metrics
        metrics = {
            'supplier_consolidation': self._calculate_supplier_consolidation(organization),
            'contract_compliance': 85,
            'maverick_spend': 12,
        }
        
        context.update({
            'opportunities': opportunities,
            'anomalies': anomalies,
            'metrics': metrics,
        })
        return context
    
    def _get_recommendation_text(self, opportunity):
        opp_type = opportunity.get('type', '')
        if opp_type == 'price_variance':
            return f"Switch to {opportunity.get('recommended_supplier', 'alternative supplier')} for {opportunity.get('potential_saving_pct', 0)}% savings"
        elif opp_type == 'volume_consolidation':
            return f"Consolidate {opportunity.get('small_orders', 0)} small orders into bulk purchases"
        elif opp_type == 'contract_negotiation':
            return "Renegotiate contract based on increased volume"
        else:
            return "Review procurement strategy for cost optimization"
    
    def _detect_price_anomalies(self, organization):
        from apps.procurement.models import PurchaseOrder
        from apps.pricing.models import Material
        from django.db.models import Avg, StdDev
        
        anomalies = []
        materials = Material.objects.filter(
            organization=organization,
            purchaseorderline__isnull=False
        ).distinct()[:10]
        
        for material in materials:
            price_stats = PurchaseOrder.objects.filter(
                organization=organization,
                lines__material=material
            ).aggregate(
                avg_price=Avg('lines__unit_price'),
                std_price=StdDev('lines__unit_price')
            )
            
            if price_stats['avg_price'] and price_stats['std_price']:
                threshold = float(price_stats['avg_price']) + (2 * float(price_stats['std_price'] or 0))
                anomalous_orders = PurchaseOrder.objects.filter(
                    organization=organization,
                    lines__material=material,
                    lines__unit_price__gt=threshold
                ).select_related('supplier')[:3]
                
                for order in anomalous_orders:
                    if order.supplier:
                        deviation = ((float(order.lines.first().unit_price) - float(price_stats['avg_price'])) / float(price_stats['avg_price'])) * 100
                        anomalies.append({
                            'material': material.name,
                            'supplier': order.supplier.name,
                            'deviation': round(deviation, 1)
                        })
        
        return anomalies[:5]
    
    def _calculate_supplier_consolidation(self, organization):
        from apps.procurement.models import Supplier, PurchaseOrder
        from django.db.models import Count, Sum
        
        supplier_stats = PurchaseOrder.objects.filter(
            organization=organization
        ).values('supplier').annotate(
            order_count=Count('id'),
            total_spend=Sum('total_amount')
        ).filter(supplier__isnull=False)
        
        if not supplier_stats:
            return 0
        
        total_suppliers = len(supplier_stats)
        small_suppliers = len([s for s in supplier_stats if s['order_count'] < 3])
        
        if total_suppliers > 0:
            consolidation_opportunity = (small_suppliers / total_suppliers) * 100
            return round(consolidation_opportunity, 1)
        return 0


class TrendsTabView(OrganizationRequiredMixin, TemplateView):
    """Trend analysis tab showing spending patterns over time
    
    Displays:
    - Category spending trends (last 180 days)
    - Order count and spend by category
    - Trend indicators (placeholder for chart integration)
    
    Loaded via HTMX for seamless tab switching.
    """
    template_name = 'analytics/tabs/trends.html'
    
    def get_template_names(self):
        """Return modern template if requested via modern URL"""
        if 'modern' in self.request.path:
            return ['analytics/tabs/trends_modern.html']
        return super().get_template_names()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = self.get_user_organization()
        
        # Get trend data
        from apps.procurement.models import PurchaseOrder
        from apps.pricing.models import Material
        from django.db.models import Sum, Count
        from datetime import datetime, timedelta
        
        # Monthly spend trend
        end_date = timezone.now()
        start_date = end_date - timedelta(days=180)
        
        # Category trends
        category_spend = PurchaseOrder.objects.filter(
            organization=organization,
            created_at__gte=start_date
        ).values('lines__material__category').annotate(
            total_spend=Sum('total_amount'),
            order_count=Count('id')
        ).order_by('-total_spend')[:5]
        
        context.update({
            'category_spend': category_spend,
            'period_days': 30,
        })
        return context


class PredictionsTabView(OrganizationRequiredMixin, TemplateView):
    """Price predictions tab with forecasted pricing
    
    Currently shows placeholder predictions with random variance.
    Will be integrated with ML models in Phase 2 for actual predictions.
    
    Displays:
    - Top 5 materials with price predictions
    - Current vs predicted prices
    - Percentage change indicators
    """
    template_name = 'analytics/tabs/predictions.html'
    
    def get_template_names(self):
        """Return modern template if requested via modern URL"""
        if 'modern' in self.request.path:
            return ['analytics/tabs/predictions_modern.html']
        return super().get_template_names()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = self.get_user_organization()
        
        # Get predictions
        predictions = self._get_price_predictions(organization)
        
        context.update({
            'predictions': predictions,
        })
        return context
    
    def _get_price_predictions(self, organization):
        from apps.pricing.models import Material, Price
        import random
        
        predictions = []
        top_materials = Material.objects.filter(
            organization=organization,
            purchaseorderline__isnull=False
        ).distinct()[:5]
        
        for material in top_materials:
            current_price = Price.objects.filter(
                material=material,
                organization=organization
            ).order_by('-time').first()
            
            if current_price:
                change = random.uniform(-10, 15)
                predicted = float(current_price.price) * (1 + change/100)
                
                predictions.append({
                    'material': material.name,
                    'current_price': float(current_price.price),
                    'predicted_price': round(predicted, 2),
                    'change': round(change, 1)
                })
        
        return predictions


class BenchmarksTabView(OrganizationRequiredMixin, TemplateView):
    """Industry benchmarking tab for performance comparison
    
    Shows organization metrics compared to:
    - Industry averages
    - Best-in-class performers
    - Gap analysis (percentage difference)
    
    Currently uses placeholder data. Will integrate with
    external benchmarking APIs in future phases.
    """
    template_name = 'analytics/tabs/benchmarks.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Benchmark data (placeholder for now)
        benchmarks = [
            {'metric': 'Cost per Order', 'your_value': '$125', 'industry_avg': '$150', 'best_in_class': '$95', 'gap': -17},
            {'metric': 'Supplier Lead Time', 'your_value': '7 days', 'industry_avg': '10 days', 'best_in_class': '5 days', 'gap': 30},
            {'metric': 'First-Time Quality', 'your_value': '92%', 'industry_avg': '88%', 'best_in_class': '95%', 'gap': 5},
            {'metric': 'Order Accuracy', 'your_value': '96%', 'industry_avg': '94%', 'best_in_class': '99%', 'gap': 2},
            {'metric': 'Supplier Diversity', 'your_value': '18%', 'industry_avg': '25%', 'best_in_class': '35%', 'gap': -28},
        ]
        
        context.update({
            'benchmarks': benchmarks,
        })
        return context


class ReportsTabView(OrganizationRequiredMixin, TemplateView):
    """Reports management tab with download capabilities
    
    Features:
    - List of recent generated reports
    - Download links for each report type
    - Report metadata (created date, type, status)
    
    Uses card-based layout matching other tabs' styling.
    """
    template_name = 'analytics/tabs/reports.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = self.get_user_organization()
        
        # Get recent reports
        recent_reports = Report.objects.filter(
            organization=organization
        ).order_by('-created_at')[:10]
        
        context.update({
            'recent_reports': recent_reports,
        })
        return context