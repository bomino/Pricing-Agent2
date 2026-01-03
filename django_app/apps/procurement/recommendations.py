"""
AI-powered Negotiation Recommendations Engine

This module provides intelligent negotiation recommendations based on
price predictions, should-cost analysis, and market data.
"""
import logging
from decimal import Decimal
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from django.db.models import Avg, Min, Max

logger = logging.getLogger(__name__)


@dataclass
class NegotiationRecommendation:
    """A single negotiation recommendation"""
    item_id: str
    material_name: str
    action: str  # negotiate_lower, accept, request_breakdown, seek_alternatives
    target_price: Optional[Decimal]
    current_price: Decimal
    savings_potential: Optional[Decimal]
    savings_percentage: Optional[float]
    confidence: float
    priority: str  # high, medium, low
    reasoning: str
    data_sources: List[str]


class NegotiationRecommendationEngine:
    """
    Engine for generating AI-powered negotiation recommendations.

    Uses price predictions, should-cost analysis, historical data,
    and market benchmarks to suggest negotiation strategies.
    """

    def __init__(self, organization):
        """
        Initialize the recommendation engine.

        Args:
            organization: The organization to generate recommendations for
        """
        self.organization = organization
        self._ml_client = None

    @property
    def ml_client(self):
        """Lazy load ML client"""
        if self._ml_client is None:
            from apps.pricing.ml_client import get_ml_client
            self._ml_client = get_ml_client()
        return self._ml_client

    def get_rfq_recommendations(self, rfq_id: str) -> List[NegotiationRecommendation]:
        """
        Get negotiation recommendations for all items in an RFQ.

        Args:
            rfq_id: UUID of the RFQ

        Returns:
            List of NegotiationRecommendation objects
        """
        from .models import RFQ

        try:
            rfq = RFQ.objects.prefetch_related('items__material').get(
                id=rfq_id,
                organization=self.organization
            )
        except RFQ.DoesNotExist:
            logger.error(f"RFQ {rfq_id} not found")
            return []

        recommendations = []
        for item in rfq.items.all():
            rec = self._analyze_rfq_item(item)
            if rec:
                recommendations.append(rec)

        # Sort by savings potential (highest first)
        recommendations.sort(
            key=lambda x: x.savings_potential or Decimal('0'),
            reverse=True
        )

        return recommendations

    def get_quote_recommendations(
        self,
        quote_id: str
    ) -> List[NegotiationRecommendation]:
        """
        Get negotiation recommendations for items in a quote.

        Compares quoted prices against should-cost and market data.

        Args:
            quote_id: UUID of the Quote

        Returns:
            List of NegotiationRecommendation objects
        """
        from .models import Quote

        try:
            quote = Quote.objects.prefetch_related(
                'items__material',
                'items__rfq_item'
            ).get(
                id=quote_id,
                organization=self.organization
            )
        except Quote.DoesNotExist:
            logger.error(f"Quote {quote_id} not found")
            return []

        recommendations = []
        for item in quote.items.all():
            rec = self._analyze_quote_item(item)
            if rec:
                recommendations.append(rec)

        # Sort by savings potential
        recommendations.sort(
            key=lambda x: x.savings_potential or Decimal('0'),
            reverse=True
        )

        return recommendations

    def _analyze_rfq_item(self, rfq_item) -> Optional[NegotiationRecommendation]:
        """
        Analyze an RFQ item and generate recommendation.

        Args:
            rfq_item: RFQItem instance

        Returns:
            NegotiationRecommendation or None
        """
        material = rfq_item.material
        if not material:
            return None

        data_sources = []

        # Get budget estimate (target price from RFQ)
        budget_estimate = rfq_item.budget_estimate or Decimal('0')

        # Get historical price data
        historical_data = self._get_historical_prices(material)
        if historical_data:
            data_sources.append('historical_prices')

        # Get price prediction from ML service
        predicted_price = self._get_price_prediction(material)
        if predicted_price:
            data_sources.append('ml_prediction')

        # Get should-cost
        should_cost = self._get_should_cost(material)
        if should_cost:
            data_sources.append('should_cost_model')

        # Determine recommendation
        return self._generate_recommendation(
            item_id=str(rfq_item.id),
            material_name=material.name,
            budget_estimate=budget_estimate,
            historical_data=historical_data,
            predicted_price=predicted_price,
            should_cost=should_cost,
            data_sources=data_sources
        )

    def _analyze_quote_item(self, quote_item) -> Optional[NegotiationRecommendation]:
        """
        Analyze a quote item and generate recommendation.

        Args:
            quote_item: QuoteItem instance

        Returns:
            NegotiationRecommendation or None
        """
        material = quote_item.material
        if not material:
            return None

        data_sources = []

        # Get quoted price (per unit)
        quoted_price = quote_item.unit_price if hasattr(quote_item, 'unit_price') else quote_item.price
        if quote_item.quantity and quote_item.quantity > 0:
            unit_price = quoted_price / quote_item.quantity
        else:
            unit_price = quoted_price

        # Get historical price data
        historical_data = self._get_historical_prices(material)
        if historical_data:
            data_sources.append('historical_prices')

        # Get price prediction
        predicted_price = self._get_price_prediction(material)
        if predicted_price:
            data_sources.append('ml_prediction')

        # Get should-cost
        should_cost = self._get_should_cost(material)
        if should_cost:
            data_sources.append('should_cost_model')

        # Compare quoted price with benchmarks
        return self._generate_quote_recommendation(
            item_id=str(quote_item.id),
            material_name=material.name,
            quoted_price=unit_price,
            historical_data=historical_data,
            predicted_price=predicted_price,
            should_cost=should_cost,
            data_sources=data_sources
        )

    def _get_historical_prices(self, material) -> Optional[Dict[str, Any]]:
        """Get historical price statistics for material"""
        from apps.pricing.models import Price
        from django.utils import timezone
        from datetime import timedelta

        try:
            ninety_days_ago = timezone.now() - timedelta(days=90)
            prices = Price.objects.filter(
                material=material,
                organization=self.organization,
                time__gte=ninety_days_ago
            )

            if not prices.exists():
                return None

            stats = prices.aggregate(
                avg_price=Avg('price'),
                min_price=Min('price'),
                max_price=Max('price')
            )

            return {
                'avg_price': stats['avg_price'],
                'min_price': stats['min_price'],
                'max_price': stats['max_price'],
                'count': prices.count()
            }
        except Exception as e:
            logger.warning(f"Failed to get historical prices for material {material.id}: {e}")
            return None

    def _get_price_prediction(self, material) -> Optional[Dict[str, Any]]:
        """Get ML price prediction for material"""
        from apps.pricing.ml_client import MLServiceError

        try:
            prediction = self.ml_client.predict_price(
                material_id=str(material.id),
                quantity=float(material.minimum_order_quantity or 1)
            )
            return {
                'predicted_price': prediction.predicted_price,
                'confidence': prediction.confidence_score,
                'model_version': prediction.model_version
            }
        except MLServiceError as e:
            logger.debug(f"ML prediction not available for material {material.id}: {e}")
            return None
        except Exception as e:
            logger.warning(f"Error getting prediction for material {material.id}: {e}")
            return None

    def _get_should_cost(self, material) -> Optional[Dict[str, Any]]:
        """Get should-cost calculation for material"""
        from apps.pricing.ml_client import MLServiceError

        try:
            result = self.ml_client.calculate_should_cost(
                material_id=str(material.id),
                quantity=float(material.minimum_order_quantity or 1)
            )
            return {
                'total': result.total_should_cost,
                'material_cost': result.material_cost,
                'labor_cost': result.labor_cost,
                'overhead_cost': result.overhead_cost,
                'confidence': result.confidence
            }
        except MLServiceError as e:
            logger.debug(f"Should-cost not available for material {material.id}: {e}")
            return None
        except Exception as e:
            logger.warning(f"Error getting should-cost for material {material.id}: {e}")
            return None

    def _generate_recommendation(
        self,
        item_id: str,
        material_name: str,
        budget_estimate: Decimal,
        historical_data: Optional[Dict],
        predicted_price: Optional[Dict],
        should_cost: Optional[Dict],
        data_sources: List[str]
    ) -> NegotiationRecommendation:
        """Generate recommendation for RFQ item"""

        # Determine target price based on available data
        target_price = None
        confidence = 0.5  # Default confidence

        if should_cost:
            target_price = should_cost['total']
            confidence = max(confidence, should_cost.get('confidence', 0.7))

        if predicted_price:
            if target_price:
                # Average of should-cost and prediction
                target_price = (target_price + predicted_price['predicted_price']) / 2
            else:
                target_price = predicted_price['predicted_price']
            confidence = max(confidence, predicted_price.get('confidence', 0.6))

        if historical_data and not target_price:
            target_price = historical_data['avg_price']
            confidence = 0.5

        # Default to budget estimate if no other data
        if not target_price:
            target_price = budget_estimate
            confidence = 0.3

        # Calculate savings potential
        savings_potential = None
        savings_percentage = None
        if budget_estimate > 0 and target_price:
            savings_potential = budget_estimate - target_price
            savings_percentage = float((savings_potential / budget_estimate) * 100)

        # Determine action and priority
        action, priority, reasoning = self._determine_action(
            budget_estimate=budget_estimate,
            target_price=target_price,
            historical_data=historical_data,
            predicted_price=predicted_price,
            should_cost=should_cost
        )

        return NegotiationRecommendation(
            item_id=item_id,
            material_name=material_name,
            action=action,
            target_price=target_price,
            current_price=budget_estimate,
            savings_potential=savings_potential if savings_potential and savings_potential > 0 else None,
            savings_percentage=savings_percentage if savings_percentage and savings_percentage > 0 else None,
            confidence=confidence,
            priority=priority,
            reasoning=reasoning,
            data_sources=data_sources
        )

    def _generate_quote_recommendation(
        self,
        item_id: str,
        material_name: str,
        quoted_price: Decimal,
        historical_data: Optional[Dict],
        predicted_price: Optional[Dict],
        should_cost: Optional[Dict],
        data_sources: List[str]
    ) -> NegotiationRecommendation:
        """Generate recommendation for quote item"""

        # Determine target price
        target_price = None
        confidence = 0.5

        if should_cost:
            target_price = should_cost['total']
            confidence = max(confidence, should_cost.get('confidence', 0.7))

        if predicted_price:
            if target_price:
                target_price = (target_price + predicted_price['predicted_price']) / 2
            else:
                target_price = predicted_price['predicted_price']
            confidence = max(confidence, predicted_price.get('confidence', 0.6))

        if historical_data:
            if target_price:
                # Use historical min as negotiation floor
                if historical_data['min_price'] < target_price:
                    target_price = (target_price + historical_data['min_price']) / 2
            else:
                target_price = historical_data['avg_price']
                confidence = 0.5

        # Calculate savings
        savings_potential = None
        savings_percentage = None
        if target_price and quoted_price > target_price:
            savings_potential = quoted_price - target_price
            savings_percentage = float((savings_potential / quoted_price) * 100)

        # Determine action
        action, priority, reasoning = self._determine_quote_action(
            quoted_price=quoted_price,
            target_price=target_price,
            historical_data=historical_data,
            should_cost=should_cost
        )

        return NegotiationRecommendation(
            item_id=item_id,
            material_name=material_name,
            action=action,
            target_price=target_price,
            current_price=quoted_price,
            savings_potential=savings_potential,
            savings_percentage=savings_percentage,
            confidence=confidence,
            priority=priority,
            reasoning=reasoning,
            data_sources=data_sources
        )

    def _determine_action(
        self,
        budget_estimate: Decimal,
        target_price: Optional[Decimal],
        historical_data: Optional[Dict],
        predicted_price: Optional[Dict],
        should_cost: Optional[Dict]
    ) -> tuple:
        """Determine negotiation action for RFQ item"""

        if not target_price:
            return (
                'gather_data',
                'medium',
                'Insufficient data for recommendation. Gather quotes from multiple suppliers.'
            )

        variance = float((budget_estimate - target_price) / budget_estimate * 100) if budget_estimate > 0 else 0

        if variance > 20:
            return (
                'negotiate_lower',
                'high',
                f'Budget estimate is {variance:.1f}% above target price. Significant negotiation opportunity.'
            )
        elif variance > 10:
            return (
                'negotiate_lower',
                'medium',
                f'Budget estimate is {variance:.1f}% above target price. Room for negotiation.'
            )
        elif variance > 0:
            return (
                'monitor',
                'low',
                'Budget estimate is close to target price. Minor optimization possible.'
            )
        else:
            return (
                'accept',
                'low',
                'Budget estimate is at or below target price. Price is competitive.'
            )

    def _determine_quote_action(
        self,
        quoted_price: Decimal,
        target_price: Optional[Decimal],
        historical_data: Optional[Dict],
        should_cost: Optional[Dict]
    ) -> tuple:
        """Determine negotiation action for quote item"""

        if not target_price:
            return (
                'request_breakdown',
                'medium',
                'Request detailed cost breakdown from supplier to validate pricing.'
            )

        variance = float((quoted_price - target_price) / quoted_price * 100) if quoted_price > 0 else 0

        # Check against historical min
        below_historical_min = False
        if historical_data and historical_data.get('min_price'):
            if quoted_price < historical_data['min_price']:
                below_historical_min = True

        if below_historical_min:
            return (
                'verify_quality',
                'high',
                'Quoted price is below historical minimum. Verify quality and specifications.'
            )
        elif variance > 25:
            return (
                'negotiate_lower',
                'high',
                f'Quote is {variance:.1f}% above target. Strong negotiation position.'
            )
        elif variance > 15:
            return (
                'negotiate_lower',
                'high',
                f'Quote is {variance:.1f}% above target. Request price reduction.'
            )
        elif variance > 5:
            return (
                'negotiate_lower',
                'medium',
                f'Quote is {variance:.1f}% above target. Room for negotiation.'
            )
        elif variance > 0:
            return (
                'accept_with_terms',
                'low',
                'Quote is slightly above target. Consider accepting with favorable terms.'
            )
        else:
            return (
                'accept',
                'low',
                'Quote is at or below target price. Competitive offer.'
            )


def get_recommendations_for_rfq(rfq_id: str, organization) -> List[Dict[str, Any]]:
    """
    Convenience function to get recommendations for an RFQ.

    Args:
        rfq_id: UUID of the RFQ
        organization: Organization instance

    Returns:
        List of recommendation dictionaries
    """
    engine = NegotiationRecommendationEngine(organization)
    recommendations = engine.get_rfq_recommendations(rfq_id)

    return [
        {
            'item_id': rec.item_id,
            'material_name': rec.material_name,
            'action': rec.action,
            'target_price': float(rec.target_price) if rec.target_price else None,
            'current_price': float(rec.current_price),
            'savings_potential': float(rec.savings_potential) if rec.savings_potential else None,
            'savings_percentage': rec.savings_percentage,
            'confidence': rec.confidence,
            'priority': rec.priority,
            'reasoning': rec.reasoning,
            'data_sources': rec.data_sources
        }
        for rec in recommendations
    ]


def get_recommendations_for_quote(quote_id: str, organization) -> List[Dict[str, Any]]:
    """
    Convenience function to get recommendations for a Quote.

    Args:
        quote_id: UUID of the Quote
        organization: Organization instance

    Returns:
        List of recommendation dictionaries
    """
    engine = NegotiationRecommendationEngine(organization)
    recommendations = engine.get_quote_recommendations(quote_id)

    return [
        {
            'item_id': rec.item_id,
            'material_name': rec.material_name,
            'action': rec.action,
            'target_price': float(rec.target_price) if rec.target_price else None,
            'current_price': float(rec.current_price),
            'savings_potential': float(rec.savings_potential) if rec.savings_potential else None,
            'savings_percentage': rec.savings_percentage,
            'confidence': rec.confidence,
            'priority': rec.priority,
            'reasoning': rec.reasoning,
            'data_sources': rec.data_sources
        }
        for rec in recommendations
    ]
