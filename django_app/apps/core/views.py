"""
Core views for the pricing agent
"""
import json
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from apps.core.mixins import OrganizationRequiredMixin, get_user_organization
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view
from rest_framework import viewsets
from django.views.generic import ListView, DetailView
try:
    from apps.core.authentication import MLServiceClient
except ImportError:
    MLServiceClient = None
import asyncio


class HomeView(TemplateView):
    """Home page view"""
    template_name = 'pages/home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'title': 'AI Pricing Agent',
            'description': 'Intelligent pricing and procurement analytics',
        })
        return context


class DashboardView(OrganizationRequiredMixin, TemplateView):
    """Main dashboard view"""
    template_name = 'dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get organization - handle users without profiles
        organization = self.get_user_organization()
        if not organization:
            from apps.core.models import Organization
            organization = Organization.objects.first()
            if not organization:
                organization = Organization.objects.create(
                    name='Default Organization',
                    code='DEFAULT'
                )
        
        # Import models
        from apps.pricing.models import Material, Price
        from apps.procurement.models import RFQ, Quote, Supplier, PurchaseOrder
        from apps.analytics.services import AnalyticsService
        from django.db.models import Sum, Count, Avg
        from datetime import datetime, timedelta
        from decimal import Decimal
        
        # Get current date ranges
        now = timezone.now()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_of_month = now.replace(day=1, month=now.month % 12 + 1, hour=0, minute=0, second=0, microsecond=0) - timedelta(microseconds=1)
        if now.month == 12:
            end_of_month = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(microseconds=1)
        start_of_year = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        last_30_days = now - timedelta(days=30)
        
        # Calculate ACCURATE Total Spend (MTD) - Month to Date for current month
        total_spend_mtd = PurchaseOrder.objects.filter(
            organization=organization,
            order_date__gte=start_of_month.date(),
            order_date__lte=now.date()
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')

        # Calculate previous month spend for trend calculation
        prev_month_start = (start_of_month - timedelta(days=1)).replace(day=1)
        prev_month_end = start_of_month - timedelta(days=1)
        total_spend_prev_month = PurchaseOrder.objects.filter(
            organization=organization,
            order_date__gte=prev_month_start.date(),
            order_date__lte=prev_month_end.date()
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')

        # Calculate spend trend percentage
        if total_spend_prev_month > 0:
            spend_trend_pct = ((float(total_spend_mtd) - float(total_spend_prev_month)) / float(total_spend_prev_month)) * 100
        else:
            spend_trend_pct = 0

        # Active RFQs count
        active_rfqs = RFQ.objects.filter(
            organization=organization,
            status__in=['published', 'open', 'active']
        ).count()

        # Active Suppliers count
        active_suppliers = Supplier.objects.filter(
            organization=organization,
            status='active'
        ).count()
        
        # Calculate Cost Savings (YTD) - Year to Date for current year
        ytd_spend = PurchaseOrder.objects.filter(
            organization=organization,
            order_date__gte=start_of_year.date(),
            order_date__lte=now.date()
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
        
        # Use analytics service for savings calculation
        analytics_service = AnalyticsService(organization)
        savings_data = analytics_service._get_savings_opportunities()
        cost_savings_ytd = savings_data.get('estimated_savings_pct', 0)
        
        # Get spending trend data for chart - Last 30 days of actual orders
        recent_orders = PurchaseOrder.objects.filter(
            organization=organization,
            order_date__gte=last_30_days.date(),
            order_date__lte=now.date()
        ).order_by('order_date')
        
        spend_trend = []
        for po in reversed(recent_orders):
            spend_trend.append({
                'date': po.order_date.strftime('%b %d'),
                'amount': float(po.total_amount or 0)
            })
        
        # Get category breakdown for pie chart (using all data for demo)
        category_breakdown = PurchaseOrder.objects.filter(
            organization=organization
        ).exclude(
            lines__material__isnull=True
        ).values('lines__material__category__name').annotate(
            total=Sum('total_amount')
        ).order_by('-total')[:5]
        
        # Format category data for chart
        category_data = []
        for cat in category_breakdown:
            if cat['lines__material__category__name'] and cat['total']:
                category_data.append({
                    'category': cat['lines__material__category__name'],
                    'amount': float(cat['total'])
                })
        
        # Get supplier performance data (using all data for demo)
        top_suppliers = PurchaseOrder.objects.filter(
            organization=organization,
            supplier__isnull=False
        ).values('supplier__name').annotate(
            total_orders=Count('id'),
            total_spend=Sum('total_amount')
        ).order_by('-total_spend')[:5]
        
        # Format supplier data
        supplier_data = []
        for supplier in top_suppliers:
            if supplier['supplier__name'] and supplier['total_spend']:
                supplier_data.append({
                    'name': supplier['supplier__name'],
                    'orders': supplier['total_orders'],
                    'spend': float(supplier['total_spend'])
                })
        
        # Update context with ACCURATE real data
        context.update({
            'metrics': {
                'total_spend_mtd': float(total_spend_mtd),
                'total_spend_ytd': float(ytd_spend),
                'spend_trend_pct': round(spend_trend_pct, 1),
                'active_rfqs': active_rfqs,
                'active_suppliers': active_suppliers,
                'cost_savings_ytd': cost_savings_ytd,
                'total_materials': Material.objects.filter(organization=organization).count(),
                'pending_quotes': Quote.objects.filter(
                    organization=organization,
                    status='submitted'
                ).count(),
                'mtd_order_count': PurchaseOrder.objects.filter(
                    organization=organization,
                    order_date__gte=start_of_month.date(),
                    order_date__lte=now.date()
                ).count(),
            },
            'charts': {
                'spend_trend': json.dumps(spend_trend),
                'category_breakdown': json.dumps(category_data),
                'supplier_performance': json.dumps(supplier_data),
            },
            'recent_activity': {
                'new_pos': PurchaseOrder.objects.filter(
                    organization=organization,
                    order_date__gte=(now - timedelta(days=7)).date(),
                    order_date__lte=now.date()
                ).count(),
                'new_suppliers': Supplier.objects.filter(
                    organization=organization,
                    created_at__gte=(now - timedelta(days=7))
                ).count(),
                'price_updates': Price.objects.filter(
                    organization=organization,
                    time__gte=(now - timedelta(days=7))
                ).count(),
            }
        })
        
        return context


class HealthCheckView(APIView):
    """Health check endpoint for load balancers"""
    permission_classes = []
    
    def get(self, request):
        """Basic health check"""
        try:
            # Check database connectivity
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            
            # Check Redis connectivity
            from django.core.cache import cache
            cache.set('health_check', 'ok', 10)
            cache_status = cache.get('health_check') == 'ok'
            
            # Check ML service connectivity
            ml_service_status = False
            if MLServiceClient:
                try:
                    ml_client = MLServiceClient()
                    ml_service_status = asyncio.run(ml_client.health_check())
                except:
                    pass
            
            health_data = {
                'status': 'healthy',
                'timestamp': timezone.now().isoformat(),
                'version': '1.0.0',
                'services': {
                    'database': 'healthy',
                    'cache': 'healthy' if cache_status else 'unhealthy',
                    'ml_service': 'healthy' if ml_service_status else 'unhealthy',
                }
            }
            
            # Return 503 if any critical service is down
            if not cache_status:
                return Response(health_data, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            
            return Response(health_data)
            
        except Exception as e:
            return Response({
                'status': 'unhealthy',
                'timestamp': timezone.now().isoformat(),
                'error': str(e),
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


@api_view(['GET'])
def recent_rfqs_api(request):
    """API endpoint for recent RFQs - used by dashboard HTMX"""
    from apps.procurement.models import RFQ
    from apps.core.mixins import get_user_organization

    organization = get_user_organization(request.user)
    if not organization:
        return Response('<tr><td colspan="5" class="text-center py-4 text-gray-500">No organization found</td></tr>')

    rfqs = RFQ.objects.filter(organization=organization).order_by('-created_at')[:5]

    if not rfqs.exists():
        html = '<tr><td colspan="5" class="text-center py-8 text-gray-500"><i class="fas fa-file-invoice text-4xl mb-3"></i><p>No RFQs found</p></td></tr>'
        return HttpResponse(html)

    html = ''
    for rfq in rfqs:
        status_colors = {
            'draft': 'bg-gray-100 text-gray-800',
            'open': 'bg-blue-100 text-blue-800',
            'published': 'bg-green-100 text-green-800',
            'closed': 'bg-yellow-100 text-yellow-800',
            'awarded': 'bg-purple-100 text-purple-800',
            'cancelled': 'bg-red-100 text-red-800',
        }
        status_class = status_colors.get(rfq.status, 'bg-gray-100 text-gray-800')
        deadline = rfq.deadline.strftime('%b %d, %Y') if rfq.deadline else 'No deadline'

        html += f'''
        <tr class="hover:bg-gray-50">
            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-navy-600">{rfq.rfq_number}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{rfq.title[:30]}...</td>
            <td class="px-6 py-4 whitespace-nowrap">
                <span class="px-2 py-1 text-xs rounded-full {status_class}">{rfq.get_status_display()}</span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{deadline}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm">
                <a href="/procurement/rfqs/{rfq.id}/" class="text-navy-600 hover:text-navy-800">View</a>
            </td>
        </tr>
        '''

    return HttpResponse(html)


@api_view(['GET'])
def price_alerts_api(request):
    """API endpoint for price alerts - used by dashboard HTMX"""
    from apps.analytics.models import Alert
    from apps.core.mixins import get_user_organization

    organization = get_user_organization(request.user)
    if not organization:
        return HttpResponse('<div class="text-center text-gray-500 py-4">No organization found</div>')

    # Filter by status='active' (not is_active - Alert model uses status field)
    alerts = Alert.objects.filter(organization=organization, status='active').order_by('-created_at')[:5]

    if not alerts.exists():
        html = '''
        <div class="text-center py-8 text-gray-500">
            <i class="fas fa-bell-slash text-4xl mb-3"></i>
            <p>No active alerts</p>
            <p class="text-sm mt-2">Price alerts will appear here when triggered</p>
        </div>
        '''
        return HttpResponse(html)

    html = ''
    for alert in alerts:
        severity_colors = {
            'low': 'border-blue-500 bg-blue-50',
            'medium': 'border-yellow-500 bg-yellow-50',
            'high': 'border-orange-500 bg-orange-50',
            'critical': 'border-red-500 bg-red-50',
        }
        severity_class = severity_colors.get(alert.severity, 'border-gray-500 bg-gray-50')

        html += f'''
        <div class="p-3 border-l-4 {severity_class} rounded-r-lg">
            <div class="flex items-start justify-between">
                <div>
                    <p class="font-medium text-gray-900">{alert.title}</p>
                    <p class="text-sm text-gray-600 mt-1">{alert.message[:50]}...</p>
                </div>
                <span class="text-xs text-gray-500">{alert.created_at.strftime('%b %d')}</span>
            </div>
        </div>
        '''

    return HttpResponse(html)


class APIRootView(APIView):
    """API root endpoint with service information"""
    permission_classes = []

    def get(self, request):
        """Return API information"""
        return Response({
            'service': 'AI Pricing Agent - Django API',
            'version': 'v1',
            'documentation': '/api/schema/',
            'endpoints': {
                'materials': '/api/v1/materials/',
                'prices': '/api/v1/prices/',
                'benchmarks': '/api/v1/benchmarks/',
                'alerts': '/api/v1/alerts/',
                'suppliers': '/api/v1/suppliers/',
                'rfqs': '/api/v1/rfqs/',
                'quotes': '/api/v1/quotes/',
                'analytics': '/api/v1/analytics/',
            },
            'authentication': {
                'session': '/accounts/login/',
                'token': '/api/v1/auth/token/',
                'jwt': '/api/v1/auth/jwt/',
            },
            'health': '/health/',
            'timestamp': timezone.now().isoformat(),
        })


# Error handlers
def error_400(request, exception=None):
    """400 Bad Request handler"""
    if request.path.startswith('/api/'):
        return JsonResponse({
            'error': {
                'code': 'bad_request',
                'message': 'Bad Request',
                'status_code': 400,
            }
        }, status=400)
    
    return render(request, 'errors/400.html', {
        'error_title': 'Bad Request',
        'error_message': 'Your request could not be processed.',
    }, status=400)


def error_403(request, exception=None):
    """403 Forbidden handler"""
    if request.path.startswith('/api/'):
        return JsonResponse({
            'error': {
                'code': 'forbidden',
                'message': 'Access Denied',
                'status_code': 403,
            }
        }, status=403)
    
    return render(request, 'errors/403.html', {
        'error_title': 'Access Denied',
        'error_message': 'You do not have permission to access this resource.',
    }, status=403)


def error_404(request, exception=None):
    """404 Not Found handler"""
    if request.path.startswith('/api/'):
        return JsonResponse({
            'error': {
                'code': 'not_found',
                'message': 'Resource Not Found',
                'status_code': 404,
            }
        }, status=404)
    
    return render(request, 'errors/404.html', {
        'error_title': 'Page Not Found',
        'error_message': 'The requested page could not be found.',
    }, status=404)


def error_500(request):
    """500 Internal Server Error handler"""
    if request.path.startswith('/api/'):
        return JsonResponse({
            'error': {
                'code': 'internal_server_error',
                'message': 'Internal Server Error',
                'status_code': 500,
            }
        }, status=500)
    
    return render(request, 'errors/500.html', {
        'error_title': 'Server Error',
        'error_message': 'An unexpected error occurred. Please try again later.',
    }, status=500)


# HTMX Views
class HTMXMixin:
    """Mixin for HTMX-aware views"""
    
    def dispatch(self, request, *args, **kwargs):
        """Add HTMX context to all requests"""
        self.is_htmx = hasattr(request, 'htmx') and request.htmx
        return super().dispatch(request, *args, **kwargs)
    
    def get_template_names(self):
        """Use different templates for HTMX requests"""
        templates = super().get_template_names()
        
        if self.is_htmx and hasattr(self, 'htmx_template_name'):
            templates.insert(0, self.htmx_template_name)
        
        return templates
    
    def get_context_data(self, **kwargs):
        """Add HTMX context data"""
        context = super().get_context_data(**kwargs)
        context['is_htmx'] = self.is_htmx
        return context


# API Documentation Views
@api_view(['GET'])
def api_schema(request):
    """OpenAPI schema endpoint"""
    from django.conf import settings
    from rest_framework.schemas.openapi import AutoSchema
    
    # This would typically use DRF's schema generation
    # For now, return a placeholder
    return Response({
        'openapi': '3.0.0',
        'info': {
            'title': 'AI Pricing Agent API',
            'version': '1.0.0',
            'description': 'API for AI-powered pricing and procurement analytics',
        },
        'servers': [
            {'url': f'{request.scheme}://{request.get_host()}/api/v1/'}
        ],
        'paths': {
            '/materials/': {
                'get': {
                    'summary': 'List materials',
                    'tags': ['materials'],
                    'responses': {
                        '200': {
                            'description': 'List of materials',
                        }
                    }
                },
                'post': {
                    'summary': 'Create material',
                    'tags': ['materials'],
                    'responses': {
                        '201': {
                            'description': 'Material created',
                        }
                    }
                }
            },
            # Add more endpoints as needed
        }
    })


# WebSocket routing (for ASGI) - commented out until channels is installed
# from django.urls import path
# from channels.routing import ProtocolTypeRouter, URLRouter
# from channels.auth import AuthMiddlewareStack

# WebSocket consumer placeholder
# class PriceUpdateConsumer:
#     """WebSocket consumer for price updates"""
#     
#     async def connect(self):
#         await self.accept()
#     
#     async def disconnect(self, close_code):
#         pass
#     
#     async def receive(self, text_data):
#         pass



# Additional views for URLs
@api_view(['GET'])
def health_check(request):
    """Simple health check endpoint"""
    return Response({
        'status': 'healthy',
        'timestamp': timezone.now().isoformat(),
        'service': 'AI Pricing Agent Django API'
    })


@api_view(['GET'])
def status_view(request):
    """System status view"""
    return Response({
        'status': 'operational',
        'timestamp': timezone.now().isoformat(),
        'version': '1.0.0',
        'uptime': 'healthy'
    })


class OrganizationListView(ListView):
    """List organizations"""
    template_name = 'core/organization_list.html'
    context_object_name = 'organizations'
    
    def get_queryset(self):
        from apps.core.models import Organization
        return Organization.objects.filter(is_active=True)


class OrganizationDetailView(DetailView):
    """Organization detail view"""
    template_name = 'core/organization_detail.html'
    context_object_name = 'organization'

    def get_queryset(self):
        from apps.core.models import Organization
        return Organization.objects.filter(is_active=True)


# Notification API endpoints (for header HTMX polling)
@api_view(['GET'])
def notifications_list_api(request):
    """API endpoint for notifications list - used by header HTMX"""
    from apps.core.models import Notification

    if not request.user.is_authenticated:
        return HttpResponse('')

    organization = get_user_organization(request.user)
    if not organization:
        return HttpResponse('<div class="p-4 text-center text-gray-500">No notifications</div>')

    try:
        notifications = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).order_by('-created_at')[:10]
    except Exception:
        # Model may not exist or have different structure
        notifications = []

    if not notifications:
        return HttpResponse('''
        <div class="p-4 text-center text-gray-500">
            <i class="fas fa-bell-slash text-2xl mb-2"></i>
            <p class="text-sm">No new notifications</p>
        </div>
        ''')

    html = ''
    for notification in notifications:
        html += f'''
        <div class="p-3 hover:bg-gray-50 border-b border-gray-100">
            <p class="text-sm text-gray-900">{notification.message}</p>
            <p class="text-xs text-gray-500 mt-1">{notification.created_at.strftime('%b %d, %H:%M')}</p>
        </div>
        '''

    return HttpResponse(html)


@api_view(['GET'])
def notifications_unread_count_api(request):
    """API endpoint for unread notification count - used by header HTMX"""
    from apps.core.models import Notification

    if not request.user.is_authenticated:
        return HttpResponse('0')

    try:
        count = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).count()
    except Exception:
        # Model may not exist or have different structure
        count = 0

    if count > 0:
        return HttpResponse(f'<span class="absolute -top-1 -right-1 bg-red-500 text-white text-xs rounded-full h-5 w-5 flex items-center justify-center">{count if count < 100 else "99+"}</span>')
    else:
        return HttpResponse('')


@api_view(['POST'])
def notifications_mark_all_read_api(request):
    """API endpoint to mark all notifications as read"""
    from apps.core.models import Notification

    if not request.user.is_authenticated:
        return HttpResponse('')

    try:
        Notification.objects.filter(
            user=request.user,
            is_read=False
        ).update(is_read=True)
    except Exception:
        pass

    return HttpResponse('<span class="text-sm text-gray-500">All notifications marked as read</span>')