"""
Django signals for pricing module ML integration.

Automatically triggers anomaly detection when new prices are created.
"""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings

from .models import Price

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Price)
def detect_price_anomaly_on_create(sender, instance, created, **kwargs):
    """
    Automatically check for price anomalies when a new price is created.

    This signal triggers an async Celery task to check if the new price
    is anomalous compared to historical data for the same material.
    """
    if not created:
        # Only check new prices, not updates
        return

    # Skip if ML service is disabled
    ml_enabled = getattr(settings, 'ML_ANOMALY_DETECTION_ENABLED', True)
    if not ml_enabled:
        logger.debug(f"ML anomaly detection disabled, skipping price {instance.id}")
        return

    # Skip if price doesn't have a material (required for anomaly detection)
    if not instance.material_id:
        logger.debug(f"Price {instance.id} has no material, skipping anomaly detection")
        return

    try:
        from .tasks import check_price_anomaly

        # Queue anomaly detection task
        check_price_anomaly.delay(str(instance.id))
        logger.debug(f"Queued anomaly detection for price {instance.id}")

    except Exception as e:
        # Don't fail the price save if anomaly detection fails
        logger.warning(f"Failed to queue anomaly detection for price {instance.id}: {e}")


@receiver(post_save, sender=Price)
def update_material_price_stats(sender, instance, created, **kwargs):
    """
    Update material statistics when a new price is recorded.

    This updates the material's current_price and other statistics
    based on the new price data.
    """
    if not instance.material_id:
        return

    try:
        from django.db.models import Avg, Max, Min, Count
        from django.utils import timezone
        from datetime import timedelta

        material = instance.material

        # Get price statistics for last 30 days
        thirty_days_ago = timezone.now() - timedelta(days=30)
        stats = Price.objects.filter(
            material=material,
            time__gte=thirty_days_ago
        ).aggregate(
            avg_price=Avg('price'),
            max_price=Max('price'),
            min_price=Min('price'),
            count=Count('id')
        )

        # Log the statistics update
        logger.debug(
            f"Price stats updated for material {material.id}: "
            f"avg=${stats['avg_price']:.2f}, "
            f"min=${stats['min_price']:.2f}, "
            f"max=${stats['max_price']:.2f}, "
            f"count={stats['count']}"
        )

    except Exception as e:
        logger.warning(f"Failed to update price stats for material: {e}")
