"""
Celery tasks for ML operations in the pricing module.

These tasks handle asynchronous ML operations like batch predictions,
anomaly detection, and model training triggers.
"""
import logging
from decimal import Decimal
from typing import List, Optional

from celery import shared_task
from django.utils import timezone

from .ml_client import get_ml_client, MLServiceError

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def generate_price_prediction(self, material_id: str, supplier_id: Optional[str] = None):
    """
    Generate price prediction for a single material and store result.

    Args:
        material_id: UUID of the material
        supplier_id: Optional UUID of the supplier
    """
    from .models import Material, PricePrediction

    try:
        material = Material.objects.get(id=material_id)
        client = get_ml_client()

        # Get prediction from ML service
        prediction = client.predict_price(
            material_id=material_id,
            supplier_id=supplier_id,
            quantity=float(material.minimum_order_quantity or 1)
        )

        # Store prediction
        PricePrediction.objects.create(
            organization=material.organization,
            material=material,
            predicted_price=prediction.predicted_price,
            confidence_interval=prediction.confidence_interval,
            prediction_horizon_days=30,
            model_version=prediction.model_version,
            model_confidence=prediction.confidence_score,
            status='completed'
        )

        logger.info(f"Price prediction generated for material {material_id}: ${prediction.predicted_price}")
        return {
            'material_id': material_id,
            'predicted_price': str(prediction.predicted_price),
            'confidence': prediction.confidence_score
        }

    except Material.DoesNotExist:
        logger.error(f"Material {material_id} not found")
        return {'error': f'Material {material_id} not found'}

    except MLServiceError as e:
        logger.warning(f"ML service error for material {material_id}: {e}")
        # Retry the task
        raise self.retry(exc=e)

    except Exception as e:
        logger.error(f"Error generating prediction for material {material_id}: {e}")
        return {'error': str(e)}


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def generate_price_predictions_batch(self, material_ids: List[str]):
    """
    Generate price predictions for multiple materials.

    Args:
        material_ids: List of material UUIDs
    """
    from .models import Material, PricePrediction

    try:
        client = get_ml_client()
        materials = Material.objects.filter(id__in=material_ids)

        # Prepare batch request
        items = [
            {
                'material_id': str(m.id),
                'quantity': float(m.minimum_order_quantity or 1)
            }
            for m in materials
        ]

        # Get batch predictions
        predictions = client.predict_prices_batch(items)

        # Store predictions
        created_count = 0
        for material, prediction in zip(materials, predictions):
            PricePrediction.objects.create(
                organization=material.organization,
                material=material,
                predicted_price=prediction.predicted_price,
                confidence_interval=prediction.confidence_interval,
                prediction_horizon_days=30,
                model_version=prediction.model_version,
                model_confidence=prediction.confidence_score,
                status='completed'
            )
            created_count += 1

        logger.info(f"Batch predictions generated for {created_count} materials")
        return {'predictions_created': created_count}

    except MLServiceError as e:
        logger.warning(f"ML service error in batch prediction: {e}")
        raise self.retry(exc=e)

    except Exception as e:
        logger.error(f"Error in batch prediction: {e}")
        return {'error': str(e)}


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def check_price_anomaly(self, price_id: str):
    """
    Check if a price is anomalous and create alert if needed.

    Args:
        price_id: UUID of the Price record to check
    """
    from .models import Price, PriceAlert

    try:
        price = Price.objects.select_related('material', 'organization').get(id=price_id)
        client = get_ml_client()

        # Detect anomaly
        result = client.detect_anomaly(
            material_id=str(price.material_id),
            price=float(price.price),
            supplier_id=str(price.supplier_id) if price.supplier_id else None,
            quantity=float(price.quantity)
        )

        if result.is_anomaly:
            # Get or create a system user for auto-generated alerts
            from django.contrib.auth import get_user_model
            User = get_user_model()
            system_user = User.objects.filter(is_superuser=True).first()
            if not system_user:
                # Fall back to any user in the organization
                from apps.accounts.models import UserProfile
                profile = UserProfile.objects.filter(
                    organization=price.organization
                ).select_related('user').first()
                system_user = profile.user if profile else None

            if not system_user:
                logger.warning(f"No user found for alert creation, skipping alert for price {price_id}")
                return {
                    'price_id': price_id,
                    'is_anomaly': True,
                    'severity': result.severity,
                    'alert_id': None,
                    'warning': 'No user available for alert creation'
                }

            # Create price alert
            alert = PriceAlert.objects.create(
                user=system_user,
                material=price.material,
                organization=price.organization,
                name=f'Price anomaly detected: {price.material.name}',
                alert_type='anomaly',
                condition_type='above' if result.deviation_percentage and result.deviation_percentage > 0 else 'below',
                threshold_value=result.expected_price or Decimal('0'),
                status='triggered',
                last_triggered=timezone.now(),
                trigger_count=1
            )

            logger.warning(
                f"Anomaly detected for price {price_id}: "
                f"severity={result.severity}, score={result.anomaly_score:.2f}"
            )

            return {
                'price_id': price_id,
                'is_anomaly': True,
                'severity': result.severity,
                'alert_id': str(alert.id)
            }

        logger.debug(f"No anomaly detected for price {price_id}")
        return {
            'price_id': price_id,
            'is_anomaly': False
        }

    except Price.DoesNotExist:
        logger.error(f"Price {price_id} not found")
        return {'error': f'Price {price_id} not found'}

    except MLServiceError as e:
        logger.warning(f"ML service error checking anomaly for price {price_id}: {e}")
        raise self.retry(exc=e)

    except Exception as e:
        logger.error(f"Error checking anomaly for price {price_id}: {e}")
        return {'error': str(e)}


@shared_task(bind=True, max_retries=2, default_retry_delay=300)
def run_anomaly_detection_for_organization(self, organization_id: str, days: int = 7):
    """
    Run anomaly detection on recent prices for an organization.

    Args:
        organization_id: UUID of the organization
        days: Number of days to look back for recent prices
    """
    from datetime import timedelta
    from .models import Price

    try:
        cutoff_date = timezone.now() - timedelta(days=days)
        recent_prices = Price.objects.filter(
            organization_id=organization_id,
            time__gte=cutoff_date
        ).values_list('id', flat=True)

        # Queue individual anomaly checks
        for price_id in recent_prices:
            check_price_anomaly.delay(str(price_id))

        logger.info(f"Queued anomaly detection for {len(recent_prices)} prices")
        return {'prices_queued': len(recent_prices)}

    except Exception as e:
        logger.error(f"Error running anomaly detection for org {organization_id}: {e}")
        return {'error': str(e)}


@shared_task(bind=True, max_retries=2, default_retry_delay=300)
def calculate_should_cost(self, material_id: str, components: Optional[dict] = None):
    """
    Calculate should-cost for a material and store as benchmark.

    Args:
        material_id: UUID of the material
        components: Optional component cost breakdown
    """
    from .models import Material, PriceBenchmark

    try:
        material = Material.objects.get(id=material_id)
        client = get_ml_client()

        # Calculate should-cost
        result = client.calculate_should_cost(
            material_id=material_id,
            components=components,
            quantity=float(material.minimum_order_quantity or 1)
        )

        # Store as benchmark
        benchmark = PriceBenchmark.objects.create(
            material=material,
            organization=material.organization,
            benchmark_type='should_cost',
            benchmark_price=result.total_should_cost,
            currency=material.currency or 'USD',
            quantity=material.minimum_order_quantity or Decimal('1'),
            period_start=timezone.now().date(),
            period_end=timezone.now().date() + timezone.timedelta(days=90),
            min_price=result.material_cost,
            max_price=result.total_should_cost * Decimal('1.2'),  # +20% buffer
            calculation_method=f"Material: ${result.material_cost}, Labor: ${result.labor_cost}, Overhead: ${result.overhead_cost}"
        )

        logger.info(f"Should-cost calculated for material {material_id}: ${result.total_should_cost}")
        return {
            'material_id': material_id,
            'should_cost': str(result.total_should_cost),
            'benchmark_id': str(benchmark.id),
            'breakdown': {
                'material': str(result.material_cost),
                'labor': str(result.labor_cost),
                'overhead': str(result.overhead_cost)
            }
        }

    except Material.DoesNotExist:
        logger.error(f"Material {material_id} not found")
        return {'error': f'Material {material_id} not found'}

    except MLServiceError as e:
        logger.warning(f"ML service error calculating should-cost for {material_id}: {e}")
        raise self.retry(exc=e)

    except Exception as e:
        logger.error(f"Error calculating should-cost for {material_id}: {e}")
        return {'error': str(e)}


@shared_task(bind=True, max_retries=1, default_retry_delay=600)
def trigger_model_training(self, model_type: str, parameters: Optional[dict] = None):
    """
    Trigger model training via ML service.

    Args:
        model_type: Type of model to train (price, anomaly, demand, should_cost)
        parameters: Optional training parameters
    """
    try:
        client = get_ml_client()
        result = client.trigger_training(model_type, parameters)

        logger.info(f"Training triggered for {model_type}: {result}")
        return result

    except MLServiceError as e:
        logger.error(f"Failed to trigger training for {model_type}: {e}")
        raise self.retry(exc=e)

    except Exception as e:
        logger.error(f"Error triggering training for {model_type}: {e}")
        return {'error': str(e)}


@shared_task
def check_ml_service_health():
    """
    Periodic task to check ML service health.
    Can be scheduled via Celery Beat.
    """
    try:
        client = get_ml_client()
        health = client.health_check()

        if health.get('status') != 'healthy':
            logger.warning(f"ML service unhealthy: {health}")

        return health

    except MLServiceError as e:
        logger.error(f"ML service health check failed: {e}")
        return {'status': 'unhealthy', 'error': str(e)}


@shared_task
def check_model_drift():
    """
    Periodic task to check for model drift.
    Should be scheduled daily or weekly via Celery Beat.
    """
    try:
        client = get_ml_client()
        drift_status = client.get_drift_status()

        # Check if any model has significant drift
        for model_name, status in drift_status.items():
            if status.get('drift_detected'):
                logger.warning(f"Drift detected in {model_name}: {status}")
                # Optionally trigger retraining
                # trigger_model_training.delay(model_name)

        return drift_status

    except MLServiceError as e:
        logger.error(f"Failed to check model drift: {e}")
        return {'error': str(e)}
