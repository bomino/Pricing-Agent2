"""
Analytics Services - Calculate real KPIs from procurement data
"""
from django.db.models import Q, Avg, Count, Sum, F, StdDev, Max, Min
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal
from apps.procurement.models import PurchaseOrder, Supplier, Material
from apps.pricing.models import Price
from apps.data_ingestion.models import DataUpload


class AnalyticsService:
    """Service for calculating analytics metrics from real data"""
    
    def __init__(self, organization):
        self.organization = organization
    
    def get_dashboard_metrics(self):
        """Get comprehensive dashboard metrics"""
        now = timezone.now()
        last_30_days = now - timedelta(days=30)
        last_90_days = now - timedelta(days=90)
        last_year = now - timedelta(days=365)
        
        return {
            'procurement': self._get_procurement_metrics(last_30_days, last_90_days),
            'pricing': self._get_pricing_metrics(last_30_days, last_90_days),
            'suppliers': self._get_supplier_metrics(last_30_days),
            'materials': self._get_material_metrics(last_30_days),
            'savings': self._get_savings_opportunities(),
            'trends': self._get_trend_data(),
            'alerts': self._get_alerts()
        }
    
    def _get_procurement_metrics(self, last_30_days, last_90_days):
        """Calculate procurement KPIs"""
        # Total POs and spend
        all_pos = PurchaseOrder.objects.filter(organization=self.organization)
        recent_pos = all_pos.filter(order_date__gte=last_30_days)
        
        # Calculate metrics
        total_spend = all_pos.aggregate(
            total=Sum('total_amount')
        )['total'] or Decimal('0')
        
        recent_spend = recent_pos.aggregate(
            total=Sum('total_amount')
        )['total'] or Decimal('0')
        
        # Average order value
        avg_order_value = all_pos.aggregate(
            avg=Avg('total_amount')
        )['avg'] or Decimal('0')
        
        # Top categories by spend - handle POs without materials
        category_spend = all_pos.exclude(
            lines__material__isnull=True
        ).values('lines__material__category').annotate(
            total_spend=Sum('total_amount'),
            order_count=Count('id', distinct=True)
        ).order_by('-total_spend')[:5]
        
        return {
            'total_purchase_orders': all_pos.count(),
            'recent_purchase_orders': recent_pos.count(),
            'total_spend': float(total_spend),
            'recent_spend': float(recent_spend),
            'avg_order_value': float(avg_order_value),
            'category_breakdown': list(category_spend),
            'spend_trend': self._calculate_spend_trend(last_90_days)
        }
    
    def _get_pricing_metrics(self, last_30_days, last_90_days):
        """Calculate pricing analytics"""
        materials = Material.objects.filter(organization=self.organization)
        
        # Price volatility calculation
        price_changes = []
        for material in materials[:50]:  # Sample first 50 materials
            prices = Price.objects.filter(
                material=material,
                time__gte=last_30_days
            ).order_by('time')
            
            if prices.count() > 1:
                price_values = list(prices.values_list('price', flat=True))
                if price_values:
                    volatility = self._calculate_volatility(price_values)
                    price_changes.append(volatility)
        
        avg_volatility = sum(price_changes) / len(price_changes) if price_changes else 0
        
        # Materials with recent price increases
        materials_with_increases = 0
        significant_increases = []
        
        for material in materials:
            recent_prices = Price.objects.filter(
                material=material,
                time__gte=last_30_days
            ).order_by('time')
            
            if recent_prices.count() >= 2:
                first_price = recent_prices.first().price
                last_price = recent_prices.last().price
                
                if first_price > 0:
                    change_pct = ((last_price - first_price) / first_price) * 100
                    
                    if change_pct > 0:
                        materials_with_increases += 1
                    
                    if change_pct > 5:  # Significant increase threshold
                        significant_increases.append({
                            'material': material.name,
                            'category': material.category,
                            'increase': round(change_pct, 2),
                            'current_price': float(last_price),
                            'previous_price': float(first_price)
                        })
        
        return {
            'total_materials': materials.count(),
            'materials_tracked': Price.objects.filter(
                organization=self.organization
            ).values('material').distinct().count(),
            'avg_price_volatility': round(avg_volatility, 2),
            'materials_with_increases': materials_with_increases,
            'significant_increases': significant_increases[:10],  # Top 10
            'price_updates_30d': Price.objects.filter(
                organization=self.organization,
                time__gte=last_30_days
            ).count()
        }
    
    def _get_supplier_metrics(self, last_30_days):
        """Calculate supplier performance metrics"""
        suppliers = Supplier.objects.filter(organization=self.organization)
        
        # Top suppliers by volume
        top_suppliers = PurchaseOrder.objects.filter(
            organization=self.organization,
            supplier__isnull=False
        ).values('supplier__name').annotate(
            total_orders=Count('id'),
            total_spend=Sum('total_amount'),
            avg_order_value=Avg('total_amount')
        ).order_by('-total_spend')[:10]
        
        # Supplier diversity
        active_suppliers = suppliers.filter(status='active').count()
        new_suppliers = suppliers.filter(created_at__gte=last_30_days).count()
        
        # Calculate supplier concentration risk
        if top_suppliers:
            top_supplier_spend = top_suppliers[0]['total_spend'] or 0
            total_spend = PurchaseOrder.objects.filter(
                organization=self.organization
            ).aggregate(Sum('total_amount'))['total_amount__sum'] or 1
            
            concentration_risk = (top_supplier_spend / total_spend) * 100 if total_spend > 0 else 0
        else:
            concentration_risk = 0
        
        # Convert Decimal to float for JSON serialization
        top_suppliers_clean = []
        for supplier in top_suppliers:
            supplier_clean = dict(supplier)
            if supplier_clean.get('total_spend'):
                supplier_clean['total_spend'] = float(supplier_clean['total_spend'])
            if supplier_clean.get('avg_order_value'):
                supplier_clean['avg_order_value'] = float(supplier_clean['avg_order_value'])
            top_suppliers_clean.append(supplier_clean)
        
        return {
            'total_suppliers': suppliers.count(),
            'active_suppliers': active_suppliers,
            'new_suppliers_30d': new_suppliers,
            'top_suppliers': top_suppliers_clean,
            'supplier_concentration_risk': round(concentration_risk, 2),
            'suppliers_by_category': list(
                suppliers.values('supplier_type').annotate(
                    count=Count('id')
                ).order_by('-count')[:5]
            )
        }
    
    def _get_material_metrics(self, last_30_days):
        """Calculate material analytics"""
        materials = Material.objects.filter(organization=self.organization)
        
        # Most purchased materials from PurchaseOrderLine
        from apps.procurement.models import PurchaseOrderLine
        top_materials = PurchaseOrderLine.objects.filter(
            purchase_order__organization=self.organization,
            material__isnull=False
        ).values('material__name', 'material__category').annotate(
            order_count=Count('purchase_order', distinct=True),
            total_quantity=Sum('quantity'),
            total_spend=Sum('total_price'),
            avg_unit_price=Avg('unit_price')
        ).order_by('-total_spend')[:10]
        
        # Materials by category
        category_distribution = materials.values('category').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Convert Decimal to float for JSON serialization
        top_materials_clean = []
        for material in top_materials:
            material_clean = dict(material)
            if material_clean.get('total_spend'):
                material_clean['total_spend'] = float(material_clean['total_spend'])
            if material_clean.get('avg_unit_price'):
                material_clean['avg_unit_price'] = float(material_clean['avg_unit_price'])
            if material_clean.get('total_quantity'):
                material_clean['total_quantity'] = float(material_clean['total_quantity'])
            top_materials_clean.append(material_clean)
        
        return {
            'total_materials': materials.count(),
            'active_materials': materials.filter(status='active').count(),
            'top_materials': top_materials_clean,
            'category_distribution': list(category_distribution),
            'new_materials_30d': materials.filter(created_at__gte=last_30_days).count()
        }
    
    def _get_savings_opportunities(self):
        """Identify cost savings opportunities"""
        opportunities = []
        from apps.procurement.models import PurchaseOrderLine
        
        # 1. Find materials with multiple suppliers and price variations
        materials_with_multiple_suppliers = PurchaseOrderLine.objects.filter(
            purchase_order__organization=self.organization,
            material__isnull=False
        ).values('material').annotate(
            supplier_count=Count('purchase_order__supplier', distinct=True)
        ).filter(supplier_count__gt=1)
        
        for mat_data in materials_with_multiple_suppliers[:20]:
            material_lines = PurchaseOrderLine.objects.filter(
                purchase_order__organization=self.organization,
                material_id=mat_data['material']
            ).values('purchase_order__supplier__name', 'material__name').annotate(
                avg_price=Avg('unit_price'),
                min_price=Min('unit_price'),
                max_price=Max('unit_price')
            )
            
            if material_lines:
                price_data = list(material_lines)
                if len(price_data) > 1:
                    min_price = min(p['min_price'] for p in price_data if p['min_price'])
                    max_price = max(p['max_price'] for p in price_data if p['max_price'])
                    
                    if min_price and max_price and max_price > min_price:
                        potential_saving = ((max_price - min_price) / max_price) * 100
                        
                        if potential_saving > 5:  # Significant saving threshold
                            opportunities.append({
                                'type': 'price_variance',
                                'material': price_data[0]['material__name'],
                                'potential_saving_pct': round(potential_saving, 2),
                                'best_price': float(min_price),
                                'current_high': float(max_price),
                                'suppliers': [p['purchase_order__supplier__name'] for p in price_data]
                            })
        
        # 2. Volume consolidation opportunities
        low_volume_orders = PurchaseOrderLine.objects.filter(
            purchase_order__organization=self.organization,
            quantity__lt=10,
            material__isnull=False
        ).values('material__name', 'material__category').annotate(
            order_count=Count('id'),
            total_quantity=Sum('quantity'),
            avg_unit_price=Avg('unit_price')
        ).filter(order_count__gt=3)  # Multiple small orders
        
        for order_data in low_volume_orders[:10]:
            opportunities.append({
                'type': 'volume_consolidation',
                'material': order_data['material__name'],
                'category': order_data['material__category'],
                'small_orders': order_data['order_count'],
                'total_quantity': float(order_data['total_quantity']),
                'potential_saving_pct': 10  # Estimated bulk discount
            })
        
        # Calculate total potential savings
        total_potential = sum(opp.get('potential_saving_pct', 0) for opp in opportunities)
        
        return {
            'opportunities': opportunities[:10],  # Top 10 opportunities
            'total_opportunities': len(opportunities),
            'estimated_savings_pct': round(min(total_potential / 10, 15), 2)  # Cap at 15%
        }
    
    def _get_trend_data(self):
        """Get trend data for charts"""
        now = timezone.now()
        
        # Daily spend for last 30 days
        spend_trend = []
        for i in range(30):
            date = (now - timedelta(days=i)).date()
            daily_spend = PurchaseOrder.objects.filter(
                organization=self.organization,
                order_date=date
            ).aggregate(total=Sum('total_amount'))['total'] or 0
            
            spend_trend.append({
                'date': date.strftime('%Y-%m-%d'),
                'spend': float(daily_spend)
            })
        
        spend_trend.reverse()
        
        # Monthly spend for last 12 months
        monthly_trend = []
        for i in range(12):
            month_start = (now - timedelta(days=i*30)).replace(day=1)
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            monthly_spend = PurchaseOrder.objects.filter(
                organization=self.organization,
                order_date__gte=month_start,
                order_date__lte=month_end
            ).aggregate(total=Sum('total_amount'))['total'] or 0
            
            monthly_trend.append({
                'month': month_start.strftime('%b %Y'),
                'spend': float(monthly_spend)
            })
        
        monthly_trend.reverse()
        
        return {
            'daily_spend': spend_trend,
            'monthly_spend': monthly_trend
        }
    
    def _get_alerts(self):
        """Generate alerts for anomalies and important events"""
        alerts = []
        now = timezone.now()
        last_7_days = now - timedelta(days=7)
        
        # Price increase alerts
        materials = Material.objects.filter(organization=self.organization)
        for material in materials[:100]:  # Check first 100 materials
            recent_prices = Price.objects.filter(
                material=material,
                time__gte=last_7_days
            ).order_by('time')
            
            if recent_prices.count() >= 2:
                first_price = recent_prices.first().price
                last_price = recent_prices.last().price
                
                if first_price > 0:
                    change_pct = ((last_price - first_price) / first_price) * 100
                    
                    if change_pct > 10:  # Alert threshold
                        alerts.append({
                            'type': 'price_increase',
                            'severity': 'high' if change_pct > 20 else 'medium',
                            'message': f'{material.name} price increased by {change_pct:.1f}%',
                            'details': {
                                'material': material.name,
                                'increase': round(change_pct, 2),
                                'from': float(first_price),
                                'to': float(last_price)
                            },
                            'timestamp': recent_prices.last().time.isoformat() if recent_prices.last() else None
                        })
        
        # New supplier alerts
        new_suppliers = Supplier.objects.filter(
            organization=self.organization,
            created_at__gte=last_7_days
        )
        
        for supplier in new_suppliers:
            alerts.append({
                'type': 'new_supplier',
                'severity': 'info',
                'message': f'New supplier added: {supplier.name}',
                'details': {
                    'supplier': supplier.name,
                    'type': supplier.supplier_type
                },
                'timestamp': supplier.created_at.isoformat()
            })
        
        # Large order alerts
        large_orders = PurchaseOrder.objects.filter(
            organization=self.organization,
            order_date__gte=last_7_days,
            total_amount__gt=10000  # Threshold for large orders
        )
        
        for order in large_orders[:5]:
            alerts.append({
                'type': 'large_order',
                'severity': 'info',
                'message': f'Large PO: {order.po_number} - ${order.total_amount:,.2f}',
                'details': {
                    'po_number': order.po_number,
                    'supplier': order.supplier.name if order.supplier else 'Unknown',
                    'amount': float(order.total_amount)
                },
                'timestamp': order.order_date.isoformat() if order.order_date else None
            })
        
        # Sort alerts by timestamp (most recent first)
        alerts.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return alerts[:20]  # Return top 20 alerts
    
    def _calculate_volatility(self, prices):
        """Calculate price volatility as coefficient of variation"""
        if len(prices) < 2:
            return 0
        
        avg = sum(prices) / len(prices)
        if avg == 0:
            return 0
        
        variance = sum((p - avg) ** 2 for p in prices) / len(prices)
        std_dev = variance ** 0.5
        
        return (std_dev / avg) * 100  # Return as percentage
    
    def _calculate_spend_trend(self, since_date):
        """Calculate spending trend"""
        # Get weekly spend data
        weeks_data = []
        current_date = timezone.now().date()
        
        while current_date >= since_date.date():
            week_start = current_date - timedelta(days=7)
            week_spend = PurchaseOrder.objects.filter(
                organization=self.organization,
                order_date__gte=week_start,
                order_date__lte=current_date
            ).aggregate(total=Sum('total_amount'))['total'] or 0
            
            weeks_data.append(float(week_spend))
            current_date = week_start
        
        if len(weeks_data) < 2:
            return 'stable'
        
        # Simple trend analysis
        first_half_avg = sum(weeks_data[:len(weeks_data)//2]) / (len(weeks_data)//2)
        second_half_avg = sum(weeks_data[len(weeks_data)//2:]) / (len(weeks_data) - len(weeks_data)//2)
        
        if second_half_avg > first_half_avg * 1.1:
            return 'increasing'
        elif second_half_avg < first_half_avg * 0.9:
            return 'decreasing'
        else:
            return 'stable'