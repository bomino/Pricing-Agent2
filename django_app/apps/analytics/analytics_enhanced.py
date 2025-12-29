"""
Enhanced Analytics with Real Price History Data
Leverages the price records from Phase 1 implementation
"""
from django.db.models import Q, Avg, Count, Sum, F, StdDev, Max, Min
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal
import json
from apps.procurement.models import PurchaseOrder, Supplier
from apps.pricing.models import Price, Material
from apps.data_ingestion.models import DataUpload


class EnhancedAnalytics:
    """Enhanced analytics using real price history data"""

    def __init__(self, organization):
        self.organization = organization
        self.now = timezone.now()

    def get_price_trends(self, material_id=None, days=30):
        """Get price trend data for charting"""
        start_date = self.now - timedelta(days=days)

        query = Price.objects.filter(
            organization=self.organization,
            time__gte=start_date
        )

        if material_id:
            query = query.filter(material_id=material_id)

        # Group by date and material
        trends = query.values('time__date', 'material__name').annotate(
            avg_price=Avg('price'),
            min_price=Min('price'),
            max_price=Max('price'),
            count=Count('id')
        ).order_by('time__date')

        # Format for Chart.js
        chart_data = {}
        for trend in trends:
            material = trend['material__name'] or 'Unknown'
            if material not in chart_data:
                chart_data[material] = {
                    'labels': [],
                    'avg_prices': [],
                    'min_prices': [],
                    'max_prices': []
                }

            chart_data[material]['labels'].append(str(trend['time__date']))
            chart_data[material]['avg_prices'].append(float(trend['avg_price']))
            chart_data[material]['min_prices'].append(float(trend['min_price']))
            chart_data[material]['max_prices'].append(float(trend['max_price']))

        return chart_data

    def detect_price_anomalies(self, threshold_std=2):
        """Detect price anomalies using statistical methods"""
        anomalies = []

        # Get materials with sufficient price history
        materials = Material.objects.filter(
            organization=self.organization
        ).annotate(
            price_count=Count('prices')
        ).filter(price_count__gte=3)

        for material in materials:
            # Get recent prices
            prices = Price.objects.filter(
                material=material,
                organization=self.organization,
                time__gte=self.now - timedelta(days=90)
            ).order_by('time')

            if prices.count() < 3:
                continue

            price_values = list(prices.values_list('price', flat=True))

            # Calculate statistics
            avg_price = sum(price_values) / len(price_values)
            variance = sum((x - avg_price) ** 2 for x in price_values) / len(price_values)
            std_dev = variance ** 0.5

            # Check latest price for anomaly
            latest_price = prices.last()
            z_score = (latest_price.price - avg_price) / std_dev if std_dev > 0 else 0

            if abs(z_score) > threshold_std:
                anomalies.append({
                    'material': material.name,
                    'material_id': str(material.id),
                    'current_price': float(latest_price.price),
                    'avg_price': float(avg_price),
                    'std_dev': float(std_dev),
                    'z_score': float(z_score),
                    'deviation_pct': float(((latest_price.price - avg_price) / avg_price * 100)),
                    'supplier': latest_price.supplier.name if latest_price.supplier else 'Unknown',
                    'date': latest_price.time.date().isoformat(),
                    'severity': 'high' if abs(z_score) > 3 else 'medium'
                })

        # Sort by absolute z-score (most anomalous first)
        anomalies.sort(key=lambda x: abs(x['z_score']), reverse=True)

        return anomalies[:20]  # Top 20 anomalies

    def calculate_savings_opportunities(self):
        """Identify cost savings opportunities from price data"""
        opportunities = []

        # Find materials with multiple suppliers
        materials_with_options = Material.objects.filter(
            organization=self.organization
        ).annotate(
            supplier_count=Count('prices__supplier', distinct=True)
        ).filter(supplier_count__gte=2)

        for material in materials_with_options:
            # Get prices by supplier in last 30 days
            recent_prices = Price.objects.filter(
                material=material,
                organization=self.organization,
                time__gte=self.now - timedelta(days=30)
            ).values('supplier__name', 'supplier__id').annotate(
                avg_price=Avg('price'),
                min_price=Min('price'),
                max_price=Max('price'),
                price_count=Count('id')
            ).order_by('avg_price')

            if recent_prices.count() >= 2:
                best_price = recent_prices.first()
                current_avg = recent_prices.aggregate(
                    overall_avg=Avg('avg_price')
                )['overall_avg']

                if current_avg and best_price['avg_price'] < current_avg:
                    saving_pct = ((current_avg - best_price['avg_price']) / current_avg) * 100

                    # Estimate annual savings based on recent purchase volume
                    recent_orders = PurchaseOrder.objects.filter(
                        organization=self.organization,
                        lines__material=material,
                        order_date__gte=self.now - timedelta(days=90)
                    ).aggregate(
                        total_qty=Sum('lines__quantity'),
                        total_spend=Sum('lines__total_price')
                    )

                    annual_qty = (recent_orders['total_qty'] or 0) * 4  # Extrapolate to year
                    potential_annual_saving = float(annual_qty) * float(current_avg - best_price['avg_price'])

                    opportunities.append({
                        'material': material.name,
                        'material_id': str(material.id),
                        'current_avg_price': float(current_avg),
                        'best_price': float(best_price['avg_price']),
                        'best_supplier': best_price['supplier__name'] or 'Unknown',
                        'saving_per_unit': float(current_avg - best_price['avg_price']),
                        'saving_pct': round(saving_pct, 2),
                        'estimated_annual_saving': round(potential_annual_saving, 2),
                        'supplier_options': recent_prices.count()
                    })

        # Sort by annual saving potential
        opportunities.sort(key=lambda x: x['estimated_annual_saving'], reverse=True)

        return opportunities[:15]  # Top 15 opportunities

    def get_supplier_price_comparison(self):
        """Compare prices across suppliers for benchmarking"""
        comparisons = []

        # Get materials with multiple suppliers
        materials = Material.objects.filter(
            organization=self.organization
        ).annotate(
            supplier_count=Count('prices__supplier', distinct=True)
        ).filter(supplier_count__gte=2)[:20]  # Top 20 materials

        for material in materials:
            supplier_prices = Price.objects.filter(
                material=material,
                organization=self.organization,
                time__gte=self.now - timedelta(days=30)
            ).values('supplier__name').annotate(
                avg_price=Avg('price'),
                min_price=Min('price'),
                max_price=Max('price'),
                last_price=Max('price'),  # Approximation of last price
                price_count=Count('id')
            ).order_by('avg_price')

            if supplier_prices:
                comparisons.append({
                    'material': material.name,
                    'material_id': str(material.id),
                    'suppliers': list(supplier_prices)
                })

        return comparisons

    def get_upload_impact_analysis(self):
        """Analyze the impact of recent data uploads"""
        recent_uploads = DataUpload.objects.filter(
            organization=self.organization,
            status='completed',
            created_at__gte=self.now - timedelta(days=7)
        ).order_by('-created_at')

        impact_analysis = []

        for upload in recent_uploads[:10]:
            # Count entities created from this upload
            prices_created = Price.objects.filter(
                organization=self.organization,
                metadata__upload_id=str(upload.id)
            ).count()

            # Get unique materials and suppliers from this upload
            unique_materials = Price.objects.filter(
                organization=self.organization,
                metadata__upload_id=str(upload.id)
            ).values('material').distinct().count()

            unique_suppliers = Price.objects.filter(
                organization=self.organization,
                metadata__upload_id=str(upload.id)
            ).values('supplier').distinct().count()

            impact_analysis.append({
                'upload_id': str(upload.id),
                'filename': upload.original_filename,
                'uploaded_at': upload.created_at.isoformat(),
                'records_processed': upload.processed_rows or 0,
                'price_records_created': prices_created,
                'unique_materials': unique_materials,
                'unique_suppliers': unique_suppliers,
                'status': upload.status
            })

        return impact_analysis

    def get_price_forecast(self, material_id, days_ahead=30):
        """Simple price forecasting based on historical trends"""
        material = Material.objects.filter(
            id=material_id,
            organization=self.organization
        ).first()

        if not material:
            return None

        # Get historical prices
        historical_prices = Price.objects.filter(
            material=material,
            organization=self.organization
        ).order_by('time').values('time', 'price')

        if historical_prices.count() < 3:
            return None  # Not enough data for forecast

        prices = list(historical_prices)

        # Simple moving average forecast
        recent_prices = prices[-30:] if len(prices) > 30 else prices
        avg_price = sum(p['price'] for p in recent_prices) / len(recent_prices)

        # Calculate trend (simple linear regression)
        if len(recent_prices) >= 2:
            n = len(recent_prices)
            x_values = list(range(n))
            y_values = [float(p['price']) for p in recent_prices]

            x_mean = sum(x_values) / n
            y_mean = sum(y_values) / n

            numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, y_values))
            denominator = sum((x - x_mean) ** 2 for x in x_values)

            slope = numerator / denominator if denominator != 0 else 0
            intercept = y_mean - slope * x_mean

            # Generate forecast
            forecast = []
            last_date = recent_prices[-1]['time']

            for i in range(1, days_ahead + 1):
                forecast_date = last_date + timedelta(days=i)
                forecast_price = intercept + slope * (n + i)

                # Add some bounds to prevent unrealistic forecasts
                forecast_price = max(avg_price * 0.5, min(avg_price * 2, forecast_price))

                forecast.append({
                    'date': forecast_date.date().isoformat(),
                    'predicted_price': round(float(forecast_price), 2),
                    'confidence': 'low' if i > 14 else 'medium' if i > 7 else 'high'
                })

            return {
                'material': material.name,
                'current_price': float(recent_prices[-1]['price']),
                'avg_price_30d': float(avg_price),
                'trend': 'increasing' if slope > 0 else 'decreasing' if slope < 0 else 'stable',
                'forecast': forecast
            }

        return None

    def get_dashboard_summary(self):
        """Get comprehensive dashboard summary with real data"""
        return {
            'total_price_records': Price.objects.filter(
                organization=self.organization
            ).count(),

            'materials_tracked': Material.objects.filter(
                organization=self.organization,
                prices__isnull=False
            ).distinct().count(),

            'suppliers_active': Supplier.objects.filter(
                organization=self.organization,
                price__isnull=False
            ).distinct().count(),

            'recent_uploads': DataUpload.objects.filter(
                organization=self.organization,
                status='completed'
            ).count(),

            'price_updates_today': Price.objects.filter(
                organization=self.organization,
                time__date=self.now.date()
            ).count(),

            'price_updates_week': Price.objects.filter(
                organization=self.organization,
                time__gte=self.now - timedelta(days=7)
            ).count(),

            'anomalies_detected': len(self.detect_price_anomalies()),

            'savings_opportunities': len(self.calculate_savings_opportunities()),

            'last_update': Price.objects.filter(
                organization=self.organization
            ).order_by('-time').first().time.isoformat() if Price.objects.filter(
                organization=self.organization
            ).exists() else None
        }