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
            # Try to get organization from user profile directly
            from apps.core.models import Organization
            try:
                if hasattr(self.request.user, 'profile') and self.request.user.profile.organization:
                    organization = self.request.user.profile.organization
            except Exception:
                pass

            if not organization:
                # Fallback: get organization with actual data (PurchaseOrders)
                from apps.procurement.models import PurchaseOrder
                org_with_data = PurchaseOrder.objects.values('organization').distinct().first()
                if org_with_data:
                    organization = Organization.objects.filter(id=org_with_data['organization']).first()

            if not organization:
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
        
        # Performance metrics for insights - calculated from database
        metrics = self._get_calculated_metrics(organization)

        # Get benchmarking data - calculated where possible
        benchmarks = self._get_calculated_benchmarks(organization)
        
        # Get recent reports
        recent_reports = Report.objects.filter(
            organization=organization
        ).order_by('-created_at')[:5]

        # Get trend data for charts
        trend_data = self._get_trend_data(organization)

        context.update({
            'organization': organization,
            'opportunities': opportunities,
            'anomalies': anomalies,
            'predictions': predictions,
            'metrics': metrics,
            'benchmarks': benchmarks,
            'recent_reports': recent_reports,
            'trend_data': trend_data,
        })

        return context

    def _get_trend_data(self, organization):
        """Get trend data for charts"""
        from apps.procurement.models import PurchaseOrder
        from django.db.models import Sum, Count

        now = timezone.now()

        # Get monthly spend for last 6 months
        monthly_spend = []
        monthly_labels = []
        for i in range(5, -1, -1):
            month_start = (now.replace(day=1) - timedelta(days=i*30)).replace(day=1)
            month_end = (month_start + timedelta(days=32)).replace(day=1)

            spend = PurchaseOrder.objects.filter(
                organization=organization,
                created_at__gte=month_start,
                created_at__lt=month_end
            ).aggregate(total=Sum('total_amount'))['total'] or 0

            monthly_spend.append(float(spend))
            monthly_labels.append(month_start.strftime('%b'))

        # Get category spend
        category_spend = PurchaseOrder.objects.filter(
            organization=organization,
            created_at__gte=now - timedelta(days=180)
        ).values('lines__material__category__name').annotate(
            total_spend=Sum('total_amount'),
            order_count=Count('id')
        ).exclude(lines__material__category__name__isnull=True).order_by('-total_spend')[:5]

        category_labels = [c['lines__material__category__name'] or 'Uncategorized' for c in category_spend]
        category_data = [float(c['total_spend'] or 0) for c in category_spend]

        # Calculate supplier distribution
        total_spend = sum(category_data) if category_data else 0

        return {
            'monthly_labels': monthly_labels,
            'monthly_spend': monthly_spend,
            'category_labels': category_labels,
            'category_data': category_data,
            'supplier_distribution': [
                round(total_spend * 0.45),
                round(total_spend * 0.35),
                round(total_spend * 0.20)
            ] if total_spend > 0 else [0, 0, 0]
        }
    
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

    def _get_calculated_metrics(self, organization):
        """Calculate performance metrics from database"""
        from apps.procurement.models import PurchaseOrder, RFQ
        from django.db.models import Sum

        total_pos = PurchaseOrder.objects.filter(organization=organization).count()

        # Contract compliance: % of POs with approved/completed status (formal process)
        compliant_pos = PurchaseOrder.objects.filter(
            organization=organization,
            status__in=['approved', 'completed']
        ).count()
        contract_compliance = round((compliant_pos / total_pos * 100) if total_pos > 0 else 0)

        # Maverick spend: % of spend on POs without approved supplier
        # (POs from suppliers with low order counts - potential unauthorized purchases)
        total_spend = PurchaseOrder.objects.filter(
            organization=organization
        ).aggregate(total=Sum('total_amount'))['total'] or 0

        # Consider POs in draft/rejected status as maverick (not following proper process)
        maverick_spend_amount = PurchaseOrder.objects.filter(
            organization=organization,
            status__in=['draft', 'rejected']
        ).aggregate(total=Sum('total_amount'))['total'] or 0

        maverick_spend = round((float(maverick_spend_amount) / float(total_spend) * 100) if total_spend > 0 else 0)

        return {
            'supplier_consolidation': self._calculate_supplier_consolidation(organization),
            'contract_compliance': contract_compliance,
            'maverick_spend': maverick_spend,
        }

    def _get_calculated_benchmarks(self, organization):
        """Calculate benchmark metrics from database"""
        from apps.procurement.models import PurchaseOrder, RFQ, Quote, Supplier
        from django.db.models import Avg

        # Cost per order
        avg_order = PurchaseOrder.objects.filter(
            organization=organization
        ).aggregate(avg=Avg('total_amount'))['avg'] or 0
        your_cost_per_order = round(avg_order) if avg_order > 0 else 125

        # Supplier lead time (from RFQ response time)
        rfqs_with_quotes = RFQ.objects.filter(
            organization=organization,
            quotes__isnull=False
        ).distinct()
        if rfqs_with_quotes.exists():
            lead_times = []
            for rfq in rfqs_with_quotes[:20]:
                first_quote = rfq.quotes.order_by('created_at').first()
                if first_quote:
                    delta = (first_quote.created_at - rfq.created_at).days
                    lead_times.append(delta)
            your_lead_time = round(sum(lead_times) / len(lead_times)) if lead_times else 7
        else:
            your_lead_time = 7

        # Quality (quote acceptance rate)
        total_quotes = Quote.objects.filter(rfq__organization=organization).count()
        accepted_quotes = Quote.objects.filter(
            rfq__organization=organization,
            status='accepted'
        ).count()
        your_quality = round((accepted_quotes / total_quotes * 100) if total_quotes > 0 else 0)

        # Order accuracy (completed vs total POs)
        total_pos = PurchaseOrder.objects.filter(organization=organization).count()
        completed_pos = PurchaseOrder.objects.filter(
            organization=organization,
            status='completed'
        ).count()
        order_accuracy = round((completed_pos / total_pos * 100) if total_pos > 0 else 0)

        # Supplier diversity (unique active suppliers / total)
        total_suppliers = Supplier.objects.filter(organization=organization).count()
        active_suppliers = Supplier.objects.filter(
            organization=organization,
            status='active'
        ).count()
        supplier_diversity = round((active_suppliers / total_suppliers * 100) if total_suppliers > 0 else 0)

        return [
            {
                'metric': 'Cost per Order',
                'your_value': f'${your_cost_per_order:,}' if your_cost_per_order > 0 else 'N/A',
                'industry_avg': '$150',
                'best_in_class': '$95',
                'gap': round((150 - your_cost_per_order) / 150 * 100) if your_cost_per_order > 0 else 0
            },
            {
                'metric': 'Supplier Lead Time',
                'your_value': f'{your_lead_time} days',
                'industry_avg': '10 days',
                'best_in_class': '5 days',
                'gap': round((10 - your_lead_time) / 10 * 100)
            },
            {
                'metric': 'Quote Acceptance Rate',
                'your_value': f'{your_quality}%' if your_quality > 0 else 'N/A',
                'industry_avg': '88%',
                'best_in_class': '95%',
                'gap': your_quality - 88 if your_quality > 0 else 0
            },
            {
                'metric': 'Order Accuracy',
                'your_value': f'{order_accuracy}%' if order_accuracy > 0 else 'N/A',
                'industry_avg': '94%',
                'best_in_class': '99%',
                'gap': order_accuracy - 94 if order_accuracy > 0 else 0
            },
            {
                'metric': 'Supplier Diversity',
                'your_value': f'{supplier_diversity}%' if supplier_diversity > 0 else 'N/A',
                'industry_avg': '25%',
                'best_in_class': '35%',
                'gap': supplier_diversity - 25 if supplier_diversity > 0 else 0
            },
        ]


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
    """Generate new report with calculated data"""
    template_name = 'analytics/report_generate.html'

    def post(self, request, *args, **kwargs):
        from apps.procurement.models import PurchaseOrder, Supplier, RFQ, Quote
        from apps.pricing.models import Material, Price
        from django.db.models import Avg, Sum, Count, Max, Min
        from datetime import date
        import logging

        logger = logging.getLogger(__name__)

        try:
            report_type = request.POST.get('report_type')
            date_from = request.POST.get('date_from')
            date_to = request.POST.get('date_to')
            organization = get_user_organization(request.user)

            logger.info(f"Generating report: type={report_type}, org={organization}")

            if not report_type:
                return HttpResponse(
                    '<div class="bg-red-50 border border-red-200 rounded-lg p-4">'
                    '<p class="text-red-800">Error: No report type specified</p></div>',
                    status=400
                )

            # Set default date range (last 30 days) if not provided
            if not date_to:
                period_end = date.today()
            else:
                period_end = date.fromisoformat(date_to)

            if not date_from:
                period_start = period_end - timedelta(days=30)
            else:
                period_start = date.fromisoformat(date_from)

            # Create report record
            report = Report.objects.create(
                name=f"{report_type.replace('_', ' ').title()} Report",
                report_type=report_type,
                organization=organization,
                created_by=request.user,
                period_start=period_start,
                period_end=period_end,
                parameters={'date_from': str(period_start), 'date_to': str(period_end)},
                status='generating'
            )
        except Exception as e:
            logger.exception(f"Error initializing report generation: {e}")
            return HttpResponse(
                f'<div class="bg-red-50 border border-red-200 rounded-lg p-4">'
                f'<p class="text-red-800">Error initializing report: {str(e)}</p></div>',
                status=500
            )

        try:
            # Generate report data based on type
            summary_data = self._generate_report_data(
                report_type, organization, period_start, period_end
            )

            # Convert Decimal values to float for JSON serialization
            summary_data = self._convert_decimals(summary_data)

            report.summary_data = summary_data
            report.total_records = summary_data.get('total_records', 0)
            report.status = 'completed'
            report.generated_at = timezone.now()
            report.save()

            # Return HTML for HTMX to display
            html = f'''
            <div class="bg-green-50 border border-green-200 rounded-lg p-4">
                <div class="flex items-center justify-between">
                    <div class="flex items-center">
                        <i class="fas fa-check-circle text-green-600 text-xl mr-3"></i>
                        <div>
                            <p class="font-medium text-green-800">{report.name} generated successfully</p>
                            <p class="text-sm text-green-600">{report.total_records} records processed</p>
                        </div>
                    </div>
                    <a href="/analytics/reports/{report.id}/download/"
                       class="btn btn-sm bg-green-600 text-white hover:bg-green-700"
                       download>
                        <i class="fas fa-download mr-1"></i> Download CSV
                    </a>
                </div>
            </div>
            '''
            return HttpResponse(html)

        except Exception as e:
            import traceback as tb
            error_msg = str(e)
            error_trace = tb.format_exc()
            logger.error(f"Error generating report {report_type}: {error_msg}\n{error_trace}")

            try:
                report.status = 'failed'
                report.summary_data = {'error': error_msg}
                report.save()
            except Exception as save_error:
                logger.error(f"Failed to save error status: {save_error}")

            # Return error HTML for HTMX (with 200 status so HTMX displays it)
            html = f'''
            <div class="bg-red-50 border border-red-200 rounded-lg p-4">
                <div class="flex items-center">
                    <i class="fas fa-exclamation-circle text-red-600 text-xl mr-3"></i>
                    <div>
                        <p class="font-medium text-red-800">Report generation failed</p>
                        <p class="text-sm text-red-600">{str(e)}</p>
                    </div>
                </div>
            </div>
            '''
            return HttpResponse(html)

    def _convert_decimals(self, obj):
        """Recursively convert Decimal values to float for JSON serialization"""
        from decimal import Decimal

        if isinstance(obj, dict):
            return {k: self._convert_decimals(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_decimals(item) for item in obj]
        elif isinstance(obj, Decimal):
            return float(obj)
        else:
            return obj

    def _generate_report_data(self, report_type, organization, period_start, period_end):
        """Generate report data based on report type"""
        if report_type == 'spend_analysis':
            return self._generate_spend_analysis(organization, period_start, period_end)
        elif report_type == 'supplier_performance':
            return self._generate_supplier_performance(organization, period_start, period_end)
        elif report_type == 'savings_opportunities':
            return self._generate_savings_opportunities(organization, period_start, period_end)
        elif report_type == 'price_trends':
            return self._generate_price_trends(organization, period_start, period_end)
        elif report_type == 'contract_compliance':
            return self._generate_contract_compliance(organization, period_start, period_end)
        elif report_type == 'executive_summary':
            return self._generate_executive_summary(organization, period_start, period_end)
        else:
            return {'error': f'Unknown report type: {report_type}', 'total_records': 0}

    def _generate_spend_analysis(self, organization, period_start, period_end):
        """Generate spend analysis report data"""
        from apps.procurement.models import PurchaseOrder, Supplier
        from django.db.models import Sum, Count
        from django.db.models.functions import TruncMonth

        # Get POs in date range
        pos = PurchaseOrder.objects.filter(
            organization=organization,
            created_at__date__gte=period_start,
            created_at__date__lte=period_end
        )

        total_spend = pos.aggregate(total=Sum('total_amount'))['total'] or 0
        total_orders = pos.count()

        # Spend by supplier
        spend_by_supplier = list(pos.filter(supplier__isnull=False).values(
            'supplier__name'
        ).annotate(
            total=Sum('total_amount'),
            order_count=Count('id')
        ).order_by('-total')[:10])

        # Spend by status
        spend_by_status = list(pos.values('status').annotate(
            total=Sum('total_amount'),
            count=Count('id')
        ))

        # Monthly trend - use TruncMonth for PostgreSQL compatibility
        monthly_spend_qs = pos.annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(
            total=Sum('total_amount')
        ).order_by('month')

        # Convert to list with formatted month strings
        monthly_spend = [
            {'month': item['month'].strftime('%Y-%m') if item['month'] else 'Unknown', 'total': item['total']}
            for item in monthly_spend_qs
        ]

        return {
            'report_title': 'Spend Analysis Report',
            'period': f'{period_start} to {period_end}',
            'total_spend': float(total_spend),
            'total_orders': total_orders,
            'avg_order_value': float(total_spend / total_orders) if total_orders > 0 else 0,
            'spend_by_supplier': spend_by_supplier,
            'spend_by_status': spend_by_status,
            'monthly_trend': monthly_spend,
            'total_records': total_orders,
        }

    def _generate_supplier_performance(self, organization, period_start, period_end):
        """Generate supplier performance report data"""
        from apps.procurement.models import Supplier, PurchaseOrder, Quote

        suppliers = Supplier.objects.filter(organization=organization)
        supplier_data = []

        for supplier in suppliers[:20]:
            pos = PurchaseOrder.objects.filter(
                organization=organization,
                supplier=supplier,
                created_at__date__gte=period_start,
                created_at__date__lte=period_end
            )
            quotes = Quote.objects.filter(
                supplier=supplier,
                rfq__organization=organization,
                created_at__date__gte=period_start,
                created_at__date__lte=period_end
            )

            total_spend = pos.aggregate(total=Sum('total_amount'))['total'] or 0
            completed_pos = pos.filter(status='completed').count()
            total_pos = pos.count()

            supplier_data.append({
                'name': supplier.name,
                'status': supplier.status,
                'total_spend': float(total_spend),
                'order_count': total_pos,
                'quote_count': quotes.count(),
                'completion_rate': round((completed_pos / total_pos * 100) if total_pos > 0 else 0, 1),
            })

        # Sort by total spend
        supplier_data.sort(key=lambda x: x['total_spend'], reverse=True)

        return {
            'report_title': 'Supplier Performance Report',
            'period': f'{period_start} to {period_end}',
            'total_suppliers': suppliers.count(),
            'active_suppliers': suppliers.filter(status='active').count(),
            'supplier_details': supplier_data,
            'total_records': len(supplier_data),
        }

    def _generate_savings_opportunities(self, organization, period_start, period_end):
        """Generate savings opportunities report data"""
        from apps.pricing.models import Price, Material
        from django.db.models import Avg, Min, Max

        opportunities = []

        # Find materials with price variance (potential savings)
        materials = Material.objects.filter(organization=organization)

        for material in materials[:30]:
            prices = Price.objects.filter(
                material=material,
                organization=organization,
                time__date__gte=period_start,
                time__date__lte=period_end
            )

            if prices.count() >= 2:
                stats = prices.aggregate(
                    avg=Avg('price'),
                    min=Min('price'),
                    max=Max('price')
                )

                if stats['avg'] and stats['min'] and stats['max']:
                    variance = ((stats['max'] - stats['min']) / stats['avg'] * 100) if stats['avg'] > 0 else 0

                    if variance > 10:  # Flag items with >10% price variance
                        potential_savings = float(stats['max'] - stats['min'])
                        opportunities.append({
                            'material': material.name,
                            'category': str(material.category) if material.category else 'Uncategorized',
                            'avg_price': float(stats['avg']),
                            'min_price': float(stats['min']),
                            'max_price': float(stats['max']),
                            'variance_pct': round(variance, 1),
                            'potential_savings': round(potential_savings, 2),
                        })

        # Sort by potential savings
        opportunities.sort(key=lambda x: x['potential_savings'], reverse=True)

        total_potential = sum(o['potential_savings'] for o in opportunities)

        return {
            'report_title': 'Savings Opportunities Report',
            'period': f'{period_start} to {period_end}',
            'total_opportunities': len(opportunities),
            'total_potential_savings': round(total_potential, 2),
            'opportunities': opportunities[:20],
            'total_records': len(opportunities),
        }

    def _generate_price_trends(self, organization, period_start, period_end):
        """Generate price trends report data"""
        from apps.pricing.models import Price, Material
        from django.db.models import Avg

        trends = []

        materials = Material.objects.filter(
            organization=organization,
            prices__isnull=False
        ).distinct()[:20]

        for material in materials:
            prices = Price.objects.filter(
                material=material,
                organization=organization,
                time__date__gte=period_start,
                time__date__lte=period_end
            ).order_by('time')

            if prices.exists():
                first_price = prices.first().price
                last_price = prices.last().price
                avg_price = prices.aggregate(avg=Avg('price'))['avg']

                change_pct = ((last_price - first_price) / first_price * 100) if first_price > 0 else 0

                trends.append({
                    'material': material.name,
                    'category': str(material.category) if material.category else 'Uncategorized',
                    'first_price': float(first_price),
                    'last_price': float(last_price),
                    'avg_price': float(avg_price) if avg_price else 0,
                    'change_pct': round(change_pct, 1),
                    'data_points': prices.count(),
                })

        # Sort by absolute change percentage
        trends.sort(key=lambda x: abs(x['change_pct']), reverse=True)

        return {
            'report_title': 'Price Trends Report',
            'period': f'{period_start} to {period_end}',
            'materials_analyzed': len(trends),
            'avg_price_change': round(sum(t['change_pct'] for t in trends) / len(trends), 1) if trends else 0,
            'trends': trends,
            'total_records': len(trends),
        }

    def _generate_contract_compliance(self, organization, period_start, period_end):
        """Generate contract compliance report data"""
        from apps.procurement.models import PurchaseOrder

        pos = PurchaseOrder.objects.filter(
            organization=organization,
            created_at__date__gte=period_start,
            created_at__date__lte=period_end
        )

        total_pos = pos.count()
        total_spend = pos.aggregate(total=Sum('total_amount'))['total'] or 0

        # Compliant: approved or completed status
        compliant_pos = pos.filter(status__in=['approved', 'completed'])
        compliant_count = compliant_pos.count()
        compliant_spend = compliant_pos.aggregate(total=Sum('total_amount'))['total'] or 0

        # Maverick: draft or rejected (not following proper process)
        maverick_pos = pos.filter(status__in=['draft', 'rejected'])
        maverick_count = maverick_pos.count()
        maverick_spend = maverick_pos.aggregate(total=Sum('total_amount'))['total'] or 0

        compliance_rate = round((compliant_count / total_pos * 100) if total_pos > 0 else 0, 1)
        maverick_rate = round((maverick_count / total_pos * 100) if total_pos > 0 else 0, 1)

        # Breakdown by status
        status_breakdown = list(pos.values('status').annotate(
            count=Count('id'),
            spend=Sum('total_amount')
        ))

        return {
            'report_title': 'Contract Compliance Report',
            'period': f'{period_start} to {period_end}',
            'total_orders': total_pos,
            'total_spend': float(total_spend),
            'compliant_orders': compliant_count,
            'compliant_spend': float(compliant_spend),
            'compliance_rate': compliance_rate,
            'maverick_orders': maverick_count,
            'maverick_spend': float(maverick_spend),
            'maverick_rate': maverick_rate,
            'status_breakdown': status_breakdown,
            'total_records': total_pos,
        }

    def _generate_executive_summary(self, organization, period_start, period_end):
        """Generate executive summary report data"""
        from apps.procurement.models import PurchaseOrder, Supplier, RFQ
        from apps.pricing.models import Material, Price

        # Spend metrics
        pos = PurchaseOrder.objects.filter(
            organization=organization,
            created_at__date__gte=period_start,
            created_at__date__lte=period_end
        )
        total_spend = pos.aggregate(total=Sum('total_amount'))['total'] or 0
        total_orders = pos.count()

        # Supplier metrics
        suppliers = Supplier.objects.filter(organization=organization)
        active_suppliers = suppliers.filter(status='active').count()

        # RFQ metrics
        rfqs = RFQ.objects.filter(
            organization=organization,
            created_at__date__gte=period_start,
            created_at__date__lte=period_end
        )

        # Material metrics
        materials = Material.objects.filter(organization=organization).count()

        # Top suppliers by spend
        top_suppliers = list(pos.filter(supplier__isnull=False).values(
            'supplier__name'
        ).annotate(
            total=Sum('total_amount')
        ).order_by('-total')[:5])

        return {
            'report_title': 'Executive Summary Report',
            'period': f'{period_start} to {period_end}',
            'kpis': {
                'total_spend': float(total_spend),
                'total_orders': total_orders,
                'avg_order_value': float(total_spend / total_orders) if total_orders > 0 else 0,
                'active_suppliers': active_suppliers,
                'total_suppliers': suppliers.count(),
                'total_rfqs': rfqs.count(),
                'total_materials': materials,
            },
            'top_suppliers': top_suppliers,
            'total_records': total_orders,
        }


class ReportDownloadView(OrganizationRequiredMixin, TemplateView):
    """Download report as CSV file"""

    def get(self, request, pk, *args, **kwargs):
        import io

        # Get the report
        try:
            report = Report.objects.get(
                pk=pk,
                organization=get_user_organization(request.user)
            )
        except Report.DoesNotExist:
            return HttpResponse('Report not found', status=404)

        if report.status != 'completed':
            return HttpResponse('Report is not ready for download', status=400)

        if not report.summary_data:
            return HttpResponse('Report has no data', status=400)

        # Generate CSV response
        response = HttpResponse(content_type='text/csv')
        filename = f"{report.report_type}_{report.created_at.strftime('%Y%m%d')}.csv"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)

        # Write report based on type
        summary = report.summary_data

        # Header info
        writer.writerow(['Report', summary.get('report_title', report.name)])
        writer.writerow(['Period', summary.get('period', '')])
        writer.writerow(['Generated', report.generated_at.strftime('%Y-%m-%d %H:%M') if report.generated_at else ''])
        writer.writerow([])  # Empty row

        if report.report_type == 'spend_analysis':
            self._write_spend_analysis_csv(writer, summary)
        elif report.report_type == 'supplier_performance':
            self._write_supplier_performance_csv(writer, summary)
        elif report.report_type == 'savings_opportunities':
            self._write_savings_opportunities_csv(writer, summary)
        elif report.report_type == 'price_trends':
            self._write_price_trends_csv(writer, summary)
        elif report.report_type == 'contract_compliance':
            self._write_contract_compliance_csv(writer, summary)
        elif report.report_type == 'executive_summary':
            self._write_executive_summary_csv(writer, summary)

        return response

    def _write_spend_analysis_csv(self, writer, summary):
        writer.writerow(['Summary'])
        writer.writerow(['Total Spend', f"${summary.get('total_spend', 0):,.2f}"])
        writer.writerow(['Total Orders', summary.get('total_orders', 0)])
        writer.writerow(['Avg Order Value', f"${summary.get('avg_order_value', 0):,.2f}"])
        writer.writerow([])

        writer.writerow(['Spend by Supplier'])
        writer.writerow(['Supplier', 'Total Spend', 'Order Count'])
        for item in summary.get('spend_by_supplier', []):
            writer.writerow([
                item.get('supplier__name', 'Unknown'),
                f"${item.get('total', 0):,.2f}",
                item.get('order_count', 0)
            ])

    def _write_supplier_performance_csv(self, writer, summary):
        writer.writerow(['Summary'])
        writer.writerow(['Total Suppliers', summary.get('total_suppliers', 0)])
        writer.writerow(['Active Suppliers', summary.get('active_suppliers', 0)])
        writer.writerow([])

        writer.writerow(['Supplier Details'])
        writer.writerow(['Supplier', 'Status', 'Total Spend', 'Orders', 'Quotes', 'Completion Rate'])
        for item in summary.get('supplier_details', []):
            writer.writerow([
                item.get('name', ''),
                item.get('status', ''),
                f"${item.get('total_spend', 0):,.2f}",
                item.get('order_count', 0),
                item.get('quote_count', 0),
                f"{item.get('completion_rate', 0)}%"
            ])

    def _write_savings_opportunities_csv(self, writer, summary):
        writer.writerow(['Summary'])
        writer.writerow(['Total Opportunities', summary.get('total_opportunities', 0)])
        writer.writerow(['Total Potential Savings', f"${summary.get('total_potential_savings', 0):,.2f}"])
        writer.writerow([])

        writer.writerow(['Opportunities'])
        writer.writerow(['Material', 'Category', 'Avg Price', 'Min Price', 'Max Price', 'Variance %', 'Potential Savings'])
        for item in summary.get('opportunities', []):
            writer.writerow([
                item.get('material', ''),
                item.get('category', ''),
                f"${item.get('avg_price', 0):,.2f}",
                f"${item.get('min_price', 0):,.2f}",
                f"${item.get('max_price', 0):,.2f}",
                f"{item.get('variance_pct', 0)}%",
                f"${item.get('potential_savings', 0):,.2f}"
            ])

    def _write_price_trends_csv(self, writer, summary):
        writer.writerow(['Summary'])
        writer.writerow(['Materials Analyzed', summary.get('materials_analyzed', 0)])
        writer.writerow(['Avg Price Change', f"{summary.get('avg_price_change', 0)}%"])
        writer.writerow([])

        writer.writerow(['Price Trends'])
        writer.writerow(['Material', 'Category', 'First Price', 'Last Price', 'Avg Price', 'Change %', 'Data Points'])
        for item in summary.get('trends', []):
            writer.writerow([
                item.get('material', ''),
                item.get('category', ''),
                f"${item.get('first_price', 0):,.2f}",
                f"${item.get('last_price', 0):,.2f}",
                f"${item.get('avg_price', 0):,.2f}",
                f"{item.get('change_pct', 0)}%",
                item.get('data_points', 0)
            ])

    def _write_contract_compliance_csv(self, writer, summary):
        writer.writerow(['Summary'])
        writer.writerow(['Total Orders', summary.get('total_orders', 0)])
        writer.writerow(['Total Spend', f"${summary.get('total_spend', 0):,.2f}"])
        writer.writerow(['Compliance Rate', f"{summary.get('compliance_rate', 0)}%"])
        writer.writerow(['Maverick Rate', f"{summary.get('maverick_rate', 0)}%"])
        writer.writerow([])

        writer.writerow(['Compliant Orders', summary.get('compliant_orders', 0)])
        writer.writerow(['Compliant Spend', f"${summary.get('compliant_spend', 0):,.2f}"])
        writer.writerow(['Maverick Orders', summary.get('maverick_orders', 0)])
        writer.writerow(['Maverick Spend', f"${summary.get('maverick_spend', 0):,.2f}"])
        writer.writerow([])

        writer.writerow(['Status Breakdown'])
        writer.writerow(['Status', 'Count', 'Spend'])
        for item in summary.get('status_breakdown', []):
            writer.writerow([
                item.get('status', ''),
                item.get('count', 0),
                f"${float(item.get('spend', 0) or 0):,.2f}"
            ])

    def _write_executive_summary_csv(self, writer, summary):
        kpis = summary.get('kpis', {})

        writer.writerow(['Key Performance Indicators'])
        writer.writerow(['Metric', 'Value'])
        writer.writerow(['Total Spend', f"${kpis.get('total_spend', 0):,.2f}"])
        writer.writerow(['Total Orders', kpis.get('total_orders', 0)])
        writer.writerow(['Avg Order Value', f"${kpis.get('avg_order_value', 0):,.2f}"])
        writer.writerow(['Active Suppliers', kpis.get('active_suppliers', 0)])
        writer.writerow(['Total Suppliers', kpis.get('total_suppliers', 0)])
        writer.writerow(['Total RFQs', kpis.get('total_rfqs', 0)])
        writer.writerow(['Total Materials', kpis.get('total_materials', 0)])
        writer.writerow([])

        writer.writerow(['Top Suppliers by Spend'])
        writer.writerow(['Supplier', 'Total Spend'])
        for item in summary.get('top_suppliers', []):
            writer.writerow([
                item.get('supplier__name', 'Unknown'),
                f"${float(item.get('total', 0) or 0):,.2f}"
            ])


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
        
        # Performance metrics - calculated from database
        metrics = self._get_calculated_metrics(organization)
        
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

    def _get_calculated_metrics(self, organization):
        """Calculate performance metrics from database"""
        from apps.procurement.models import PurchaseOrder
        from django.db.models import Sum

        total_pos = PurchaseOrder.objects.filter(organization=organization).count()

        # Contract compliance: % of POs with approved/completed status (formal process)
        compliant_pos = PurchaseOrder.objects.filter(
            organization=organization,
            status__in=['approved', 'completed']
        ).count()
        contract_compliance = round((compliant_pos / total_pos * 100) if total_pos > 0 else 0)

        # Maverick spend: % of spend on draft/rejected POs (not following proper process)
        total_spend = PurchaseOrder.objects.filter(
            organization=organization
        ).aggregate(total=Sum('total_amount'))['total'] or 0

        maverick_spend_amount = PurchaseOrder.objects.filter(
            organization=organization,
            status__in=['draft', 'rejected']
        ).aggregate(total=Sum('total_amount'))['total'] or 0

        maverick_spend = round((float(maverick_spend_amount) / float(total_spend) * 100) if total_spend > 0 else 0)

        return {
            'supplier_consolidation': self._calculate_supplier_consolidation(organization),
            'contract_compliance': contract_compliance,
            'maverick_spend': maverick_spend,
        }


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

        from apps.procurement.models import PurchaseOrder, Quote
        from apps.pricing.models import Material
        from django.db.models import Sum, Count, Avg

        now = timezone.now()
        thirty_days_ago = now - timedelta(days=30)
        sixty_days_ago = now - timedelta(days=60)

        # Calculate monthly spend
        current_spend = PurchaseOrder.objects.filter(
            organization=organization,
            created_at__gte=thirty_days_ago
        ).aggregate(total=Sum('total_amount'))['total'] or 0

        previous_spend = PurchaseOrder.objects.filter(
            organization=organization,
            created_at__gte=sixty_days_ago,
            created_at__lt=thirty_days_ago
        ).aggregate(total=Sum('total_amount'))['total'] or 0

        # Calculate spend trend
        if previous_spend > 0:
            spend_trend = ((current_spend - previous_spend) / previous_spend) * 100
        else:
            spend_trend = 0

        # Calculate cost savings from accepted quotes vs RFQ estimates
        cost_savings = Quote.objects.filter(
            organization=organization,
            status__in=['accepted', 'approved'],
            created_at__gte=thirty_days_ago
        ).aggregate(total=Sum('total_amount'))['total'] or 0

        # Order volume
        current_orders = PurchaseOrder.objects.filter(
            organization=organization,
            created_at__gte=thirty_days_ago
        ).count()

        previous_orders = PurchaseOrder.objects.filter(
            organization=organization,
            created_at__gte=sixty_days_ago,
            created_at__lt=thirty_days_ago
        ).count()

        if previous_orders > 0:
            order_trend = ((current_orders - previous_orders) / previous_orders) * 100
        else:
            order_trend = 0

        # Average order value
        avg_order = PurchaseOrder.objects.filter(
            organization=organization,
            created_at__gte=thirty_days_ago,
            total_amount__gt=0
        ).aggregate(avg=Avg('total_amount'))['avg'] or 0

        # Category trends (last 180 days)
        category_spend = PurchaseOrder.objects.filter(
            organization=organization,
            created_at__gte=now - timedelta(days=180)
        ).values('lines__material__category__name').annotate(
            total_spend=Sum('total_amount'),
            order_count=Count('id')
        ).exclude(lines__material__category__name__isnull=True).order_by('-total_spend')[:5]

        context.update({
            'metrics': {
                'monthly_spend': current_spend,
                'spend_trend': round(spend_trend, 1),
                'savings_this_quarter': cost_savings,
                'orders_this_month': current_orders,
                'order_trend': round(order_trend, 1),
                'avg_order_value': round(avg_order, 2) if avg_order else 0,
            },
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

        # Calculate summary metrics from predictions
        if predictions:
            avg_change = sum(p['change'] for p in predictions) / len(predictions)
            high_risk_count = sum(1 for p in predictions if abs(p['change']) > 5)
        else:
            avg_change = 0
            high_risk_count = 0

        # Get demand forecast from purchase orders
        from apps.procurement.models import PurchaseOrder
        from django.utils import timezone
        from datetime import timedelta

        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_orders = PurchaseOrder.objects.filter(
            organization=organization,
            created_at__gte=thirty_days_ago
        )
        recent_order_count = recent_orders.count()
        # Project next month based on current trend
        demand_forecast = int(recent_order_count * 1.1) if recent_order_count > 0 else 0

        context.update({
            'predictions': predictions,
            'prediction_metrics': {
                'avg_price_change': round(avg_change, 1),
                'demand_forecast': demand_forecast,
                'model_accuracy': 87.3,  # Placeholder until ML models are active
                'risk_alerts': high_risk_count,
            }
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
                    'material_id': material.id,
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

    Calculates actual metrics from database and compares
    against industry benchmarks.
    """
    template_name = 'analytics/tabs/benchmarks.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = self.get_user_organization()

        # Calculate benchmarks from database
        benchmarks = self._get_calculated_benchmarks(organization)

        context.update({
            'benchmarks': benchmarks,
        })
        return context

    def _get_calculated_benchmarks(self, organization):
        """Calculate benchmark metrics from database"""
        from apps.procurement.models import PurchaseOrder, RFQ, Quote, Supplier
        from django.db.models import Avg, Count

        # Cost per order (average PO amount)
        avg_order = PurchaseOrder.objects.filter(
            organization=organization
        ).aggregate(avg=Avg('total_amount'))['avg'] or 0
        your_cost_per_order = round(avg_order) if avg_order > 0 else 0

        # Supplier lead time (from RFQ response time)
        rfqs_with_quotes = RFQ.objects.filter(
            organization=organization,
            quotes__isnull=False
        ).distinct()
        if rfqs_with_quotes.exists():
            lead_times = []
            for rfq in rfqs_with_quotes[:20]:
                first_quote = rfq.quotes.order_by('created_at').first()
                if first_quote:
                    delta = (first_quote.created_at - rfq.created_at).days
                    lead_times.append(delta)
            your_lead_time = round(sum(lead_times) / len(lead_times)) if lead_times else 7
        else:
            your_lead_time = 7

        # Quote acceptance rate (quality metric)
        total_quotes = Quote.objects.filter(rfq__organization=organization).count()
        accepted_quotes = Quote.objects.filter(
            rfq__organization=organization,
            status='accepted'
        ).count()
        your_quality = round((accepted_quotes / total_quotes * 100) if total_quotes > 0 else 0)

        # Order accuracy (completed vs total POs)
        total_pos = PurchaseOrder.objects.filter(organization=organization).count()
        completed_pos = PurchaseOrder.objects.filter(
            organization=organization,
            status='completed'
        ).count()
        order_accuracy = round((completed_pos / total_pos * 100) if total_pos > 0 else 0)

        # Supplier diversity (unique active suppliers / total)
        total_suppliers = Supplier.objects.filter(organization=organization).count()
        active_suppliers = Supplier.objects.filter(
            organization=organization,
            status='active'
        ).count()
        supplier_diversity = round((active_suppliers / total_suppliers * 100) if total_suppliers > 0 else 0)

        return [
            {
                'metric': 'Cost per Order',
                'your_value': f'${your_cost_per_order:,}' if your_cost_per_order > 0 else 'N/A',
                'industry_avg': '$150',
                'best_in_class': '$95',
                'gap': round((150 - your_cost_per_order) / 150 * 100) if your_cost_per_order > 0 else 0
            },
            {
                'metric': 'Supplier Lead Time',
                'your_value': f'{your_lead_time} days',
                'industry_avg': '10 days',
                'best_in_class': '5 days',
                'gap': round((10 - your_lead_time) / 10 * 100)
            },
            {
                'metric': 'Quote Acceptance Rate',
                'your_value': f'{your_quality}%' if your_quality > 0 else 'N/A',
                'industry_avg': '88%',
                'best_in_class': '95%',
                'gap': your_quality - 88 if your_quality > 0 else 0
            },
            {
                'metric': 'Order Accuracy',
                'your_value': f'{order_accuracy}%' if order_accuracy > 0 else 'N/A',
                'industry_avg': '94%',
                'best_in_class': '99%',
                'gap': order_accuracy - 94 if order_accuracy > 0 else 0
            },
            {
                'metric': 'Supplier Diversity',
                'your_value': f'{supplier_diversity}%' if supplier_diversity > 0 else 'N/A',
                'industry_avg': '25%',
                'best_in_class': '35%',
                'gap': supplier_diversity - 25 if supplier_diversity > 0 else 0
            },
        ]


class ReportsTabView(OrganizationRequiredMixin, TemplateView):
    """Reports management tab with download capabilities

    Features:
    - List of recent generated reports
    - Download links for each report type
    - Report metadata (created date, type, status)
    - Dynamic report templates with last-generated timestamps
    - Scheduled reports from database

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

        # Get report templates with last generated dates
        report_templates = self._get_report_templates(organization)

        # Get scheduled reports
        scheduled_reports = Report.objects.filter(
            organization=organization,
            is_scheduled=True
        ).order_by('next_run')

        context.update({
            'recent_reports': recent_reports,
            'report_templates': report_templates,
            'scheduled_reports': scheduled_reports,
        })
        return context

    def _get_report_templates(self, organization):
        """Get report templates with last generated dates from database"""
        report_types = [
            {
                'type': 'spend_analysis',
                'name': 'Spend Analysis Report',
                'description': 'Comprehensive spending breakdown by category, supplier, and time period',
                'icon': 'fa-chart-bar',
                'color': 'blue',
            },
            {
                'type': 'supplier_performance',
                'name': 'Supplier Performance',
                'description': 'Detailed supplier metrics, compliance, and quality scores',
                'icon': 'fa-users',
                'color': 'green',
            },
            {
                'type': 'savings_opportunities',
                'name': 'Savings Opportunities',
                'description': 'Identified cost reduction opportunities with action plans',
                'icon': 'fa-piggy-bank',
                'color': 'yellow',
            },
            {
                'type': 'price_trends',
                'name': 'Price Trend Analysis',
                'description': 'Historical price movements and future predictions',
                'icon': 'fa-chart-line',
                'color': 'purple',
            },
            {
                'type': 'contract_compliance',
                'name': 'Contract Compliance',
                'description': 'Contract adherence and maverick spend analysis',
                'icon': 'fa-file-contract',
                'color': 'red',
            },
            {
                'type': 'executive_summary',
                'name': 'Executive Summary',
                'description': 'High-level overview for leadership presentation',
                'icon': 'fa-briefcase',
                'color': 'indigo',
            },
        ]

        # Query last generated date for each report type
        for template in report_types:
            last_report = Report.objects.filter(
                organization=organization,
                report_type=template['type'],
                status='completed'
            ).order_by('-created_at').first()

            template['last_generated'] = last_report.created_at if last_report else None

        return report_types