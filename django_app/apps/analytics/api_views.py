"""
API Views for Enhanced Analytics
Provides JSON endpoints for real-time price analytics
"""
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from .analytics_enhanced import EnhancedAnalytics
from apps.core.models import Organization
import json


@login_required
@require_http_methods(["GET"])
def price_trends_api(request):
    """API endpoint for price trends data"""
    # Get organization
    if hasattr(request.user, 'profile') and request.user.profile.organization:
        organization = request.user.profile.organization
    else:
        organization = Organization.objects.first()

    # Get parameters
    material_id = request.GET.get('material_id')
    days = int(request.GET.get('days', 30))

    # Get analytics
    analytics = EnhancedAnalytics(organization)
    trends = analytics.get_price_trends(material_id=material_id, days=days)

    return JsonResponse({
        'success': True,
        'data': trends
    })


@login_required
@require_http_methods(["GET"])
def price_anomalies_api(request):
    """API endpoint for price anomalies"""
    # Get organization
    if hasattr(request.user, 'profile') and request.user.profile.organization:
        organization = request.user.profile.organization
    else:
        organization = Organization.objects.first()

    # Get analytics
    analytics = EnhancedAnalytics(organization)
    anomalies = analytics.detect_price_anomalies()

    return JsonResponse({
        'success': True,
        'count': len(anomalies),
        'data': anomalies
    })


@login_required
@require_http_methods(["GET"])
def savings_opportunities_api(request):
    """API endpoint for savings opportunities"""
    # Get organization
    if hasattr(request.user, 'profile') and request.user.profile.organization:
        organization = request.user.profile.organization
    else:
        organization = Organization.objects.first()

    # Get analytics
    analytics = EnhancedAnalytics(organization)
    opportunities = analytics.calculate_savings_opportunities()

    # Calculate total potential savings
    total_savings = sum(opp['estimated_annual_saving'] for opp in opportunities)

    return JsonResponse({
        'success': True,
        'total_potential_savings': round(total_savings, 2),
        'count': len(opportunities),
        'data': opportunities
    })


@login_required
@require_http_methods(["GET"])
def supplier_comparison_api(request):
    """API endpoint for supplier price comparison"""
    # Get organization
    if hasattr(request.user, 'profile') and request.user.profile.organization:
        organization = request.user.profile.organization
    else:
        organization = Organization.objects.first()

    # Get analytics
    analytics = EnhancedAnalytics(organization)
    comparisons = analytics.get_supplier_price_comparison()

    return JsonResponse({
        'success': True,
        'count': len(comparisons),
        'data': comparisons
    })


@login_required
@require_http_methods(["GET"])
def price_forecast_api(request):
    """API endpoint for price forecasting"""
    # Get organization
    if hasattr(request.user, 'profile') and request.user.profile.organization:
        organization = request.user.profile.organization
    else:
        organization = Organization.objects.first()

    # Get parameters
    material_id = request.GET.get('material_id')
    days_ahead = int(request.GET.get('days_ahead', 30))

    if not material_id:
        return JsonResponse({
            'success': False,
            'error': 'material_id parameter required'
        }, status=400)

    # Get analytics
    analytics = EnhancedAnalytics(organization)
    forecast = analytics.get_price_forecast(material_id=material_id, days_ahead=days_ahead)

    if forecast:
        return JsonResponse({
            'success': True,
            'data': forecast
        })
    else:
        return JsonResponse({
            'success': False,
            'error': 'Insufficient data for forecast'
        }, status=404)


@login_required
@require_http_methods(["GET"])
def upload_impact_api(request):
    """API endpoint for upload impact analysis"""
    # Get organization
    if hasattr(request.user, 'profile') and request.user.profile.organization:
        organization = request.user.profile.organization
    else:
        organization = Organization.objects.first()

    # Get analytics
    analytics = EnhancedAnalytics(organization)
    impact = analytics.get_upload_impact_analysis()

    return JsonResponse({
        'success': True,
        'count': len(impact),
        'data': impact
    })


@login_required
@require_http_methods(["GET"])
def analytics_dashboard_api(request):
    """API endpoint for complete dashboard data"""
    # Get organization
    if hasattr(request.user, 'profile') and request.user.profile.organization:
        organization = request.user.profile.organization
    else:
        organization = Organization.objects.first()

    # Get analytics
    analytics = EnhancedAnalytics(organization)

    # Compile dashboard data
    dashboard_data = {
        'summary': analytics.get_dashboard_summary(),
        'recent_anomalies': analytics.detect_price_anomalies()[:5],
        'top_savings': analytics.calculate_savings_opportunities()[:5],
        'price_trends': analytics.get_price_trends(days=7),  # Last week
        'upload_impact': analytics.get_upload_impact_analysis()[:3]
    }

    return JsonResponse({
        'success': True,
        'data': dashboard_data
    })