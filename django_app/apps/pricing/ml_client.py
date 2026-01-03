"""
ML Service Client for Django-FastAPI Integration

This module provides a client for communicating with the FastAPI ML service
for price predictions, anomaly detection, and should-cost calculations.
"""
import logging
from decimal import Decimal
from typing import Optional, Dict, List, Any
from dataclasses import dataclass

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class PricePrediction:
    """Price prediction result from ML service"""
    predicted_price: Decimal
    confidence_score: float
    confidence_interval: Dict[str, float]
    model_version: str
    features_used: List[str]


@dataclass
class AnomalyResult:
    """Anomaly detection result from ML service"""
    is_anomaly: bool
    anomaly_score: float
    severity: str  # low, medium, high, critical
    expected_price: Optional[Decimal]
    deviation_percentage: Optional[float]
    explanation: str


@dataclass
class ShouldCostResult:
    """Should-cost calculation result from ML service"""
    total_should_cost: Decimal
    material_cost: Decimal
    labor_cost: Decimal
    overhead_cost: Decimal
    confidence: float
    breakdown: List[Dict[str, Any]]


class MLServiceError(Exception):
    """Exception raised when ML service communication fails"""
    pass


class MLServiceClient:
    """Client for communicating with FastAPI ML service"""

    def __init__(self, base_url: Optional[str] = None, timeout: float = 30.0):
        """
        Initialize the ML service client.

        Args:
            base_url: Base URL of the ML service. Defaults to settings.ML_SERVICE_URL
            timeout: Request timeout in seconds
        """
        self.base_url = base_url or getattr(settings, 'ML_SERVICE_URL', 'http://localhost:8001')
        self.timeout = timeout
        self._client = None

    def _get_client(self) -> httpx.Client:
        """Get or create HTTP client"""
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={'Content-Type': 'application/json'}
            )
        return self._client

    def close(self):
        """Close the HTTP client"""
        if self._client:
            self._client.close()
            self._client = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # Health Check Methods

    def health_check(self) -> Dict[str, Any]:
        """Check ML service health"""
        try:
            client = self._get_client()
            response = client.get('/health')
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"ML service health check failed: {e}")
            raise MLServiceError(f"Health check failed: {e}")

    def is_healthy(self) -> bool:
        """Check if ML service is healthy"""
        try:
            health = self.health_check()
            return health.get('status') == 'healthy'
        except MLServiceError:
            return False

    # Price Prediction Methods

    def predict_price(
        self,
        material_id: str,
        supplier_id: Optional[str] = None,
        quantity: float = 1.0,
        additional_features: Optional[Dict[str, Any]] = None
    ) -> PricePrediction:
        """
        Get price prediction for a material.

        Args:
            material_id: UUID of the material
            supplier_id: Optional UUID of the supplier
            quantity: Quantity for the price
            additional_features: Optional additional features for the model

        Returns:
            PricePrediction with predicted price and confidence

        Raises:
            MLServiceError: If prediction fails
        """
        try:
            client = self._get_client()
            payload = {
                'material_id': str(material_id),
                'quantity': quantity,
            }
            if supplier_id:
                payload['supplier_id'] = str(supplier_id)
            if additional_features:
                payload['features'] = additional_features

            response = client.post('/api/v1/predictions/price', json=payload)
            response.raise_for_status()
            data = response.json()

            return PricePrediction(
                predicted_price=Decimal(str(data['predicted_price'])),
                confidence_score=data.get('confidence_score', 0.0),
                confidence_interval=data.get('confidence_interval', {}),
                model_version=data.get('model_version', 'unknown'),
                features_used=data.get('features_used', [])
            )
        except httpx.HTTPError as e:
            logger.error(f"Price prediction failed for material {material_id}: {e}")
            raise MLServiceError(f"Price prediction failed: {e}")

    def predict_prices_batch(
        self,
        materials: List[Dict[str, Any]]
    ) -> List[PricePrediction]:
        """
        Get price predictions for multiple materials.

        Args:
            materials: List of dicts with material_id, supplier_id (optional), quantity

        Returns:
            List of PricePrediction results

        Raises:
            MLServiceError: If batch prediction fails
        """
        try:
            client = self._get_client()
            payload = {'items': materials}

            response = client.post('/api/v1/predictions/batch', json=payload)
            response.raise_for_status()
            data = response.json()

            results = []
            for item in data.get('predictions', []):
                results.append(PricePrediction(
                    predicted_price=Decimal(str(item['predicted_price'])),
                    confidence_score=item.get('confidence_score', 0.0),
                    confidence_interval=item.get('confidence_interval', {}),
                    model_version=item.get('model_version', 'unknown'),
                    features_used=item.get('features_used', [])
                ))
            return results
        except httpx.HTTPError as e:
            logger.error(f"Batch price prediction failed: {e}")
            raise MLServiceError(f"Batch prediction failed: {e}")

    # Anomaly Detection Methods

    def detect_anomaly(
        self,
        material_id: str,
        price: float,
        supplier_id: Optional[str] = None,
        quantity: float = 1.0
    ) -> AnomalyResult:
        """
        Detect if a price is anomalous.

        Args:
            material_id: UUID of the material
            price: Price to check
            supplier_id: Optional UUID of the supplier
            quantity: Quantity for the price

        Returns:
            AnomalyResult with detection details

        Raises:
            MLServiceError: If detection fails
        """
        try:
            client = self._get_client()
            payload = {
                'material_id': str(material_id),
                'price': price,
                'quantity': quantity,
            }
            if supplier_id:
                payload['supplier_id'] = str(supplier_id)

            response = client.post('/api/v1/predictions/anomaly', json=payload)
            response.raise_for_status()
            data = response.json()

            return AnomalyResult(
                is_anomaly=data.get('is_anomaly', False),
                anomaly_score=data.get('anomaly_score', 0.0),
                severity=data.get('severity', 'low'),
                expected_price=Decimal(str(data['expected_price'])) if data.get('expected_price') else None,
                deviation_percentage=data.get('deviation_percentage'),
                explanation=data.get('explanation', '')
            )
        except httpx.HTTPError as e:
            logger.error(f"Anomaly detection failed for material {material_id}: {e}")
            raise MLServiceError(f"Anomaly detection failed: {e}")

    def detect_anomalies_batch(
        self,
        prices: List[Dict[str, Any]]
    ) -> List[AnomalyResult]:
        """
        Detect anomalies in multiple prices.

        Args:
            prices: List of dicts with material_id, price, supplier_id (optional), quantity

        Returns:
            List of AnomalyResult results

        Raises:
            MLServiceError: If batch detection fails
        """
        try:
            client = self._get_client()
            payload = {'items': prices}

            response = client.post('/api/v1/predictions/anomaly/batch', json=payload)
            response.raise_for_status()
            data = response.json()

            results = []
            for item in data.get('results', []):
                results.append(AnomalyResult(
                    is_anomaly=item.get('is_anomaly', False),
                    anomaly_score=item.get('anomaly_score', 0.0),
                    severity=item.get('severity', 'low'),
                    expected_price=Decimal(str(item['expected_price'])) if item.get('expected_price') else None,
                    deviation_percentage=item.get('deviation_percentage'),
                    explanation=item.get('explanation', '')
                ))
            return results
        except httpx.HTTPError as e:
            logger.error(f"Batch anomaly detection failed: {e}")
            raise MLServiceError(f"Batch anomaly detection failed: {e}")

    # Should-Cost Methods

    def calculate_should_cost(
        self,
        material_id: str,
        components: Optional[Dict[str, Any]] = None,
        quantity: float = 1.0
    ) -> ShouldCostResult:
        """
        Calculate should-cost for a material.

        Args:
            material_id: UUID of the material
            components: Optional component cost breakdown
            quantity: Quantity for the calculation

        Returns:
            ShouldCostResult with cost breakdown

        Raises:
            MLServiceError: If calculation fails
        """
        try:
            client = self._get_client()
            payload = {
                'material_id': str(material_id),
                'quantity': quantity,
            }
            if components:
                payload['components'] = components

            response = client.post('/api/v1/predictions/should-cost', json=payload)
            response.raise_for_status()
            data = response.json()

            return ShouldCostResult(
                total_should_cost=Decimal(str(data.get('total_should_cost', 0))),
                material_cost=Decimal(str(data.get('material_cost', 0))),
                labor_cost=Decimal(str(data.get('labor_cost', 0))),
                overhead_cost=Decimal(str(data.get('overhead_cost', 0))),
                confidence=data.get('confidence', 0.0),
                breakdown=data.get('breakdown', [])
            )
        except httpx.HTTPError as e:
            logger.error(f"Should-cost calculation failed for material {material_id}: {e}")
            raise MLServiceError(f"Should-cost calculation failed: {e}")

    # Model Management Methods

    def get_models(self) -> List[Dict[str, Any]]:
        """Get list of available models"""
        try:
            client = self._get_client()
            response = client.get('/api/v1/models')
            response.raise_for_status()
            return response.json().get('models', [])
        except httpx.HTTPError as e:
            logger.error(f"Failed to get models: {e}")
            raise MLServiceError(f"Failed to get models: {e}")

    def get_model_health(self, model_id: str) -> Dict[str, Any]:
        """Get health status of a specific model"""
        try:
            client = self._get_client()
            response = client.get(f'/api/v1/models/{model_id}/health')
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get model health for {model_id}: {e}")
            raise MLServiceError(f"Failed to get model health: {e}")

    def trigger_training(
        self,
        model_type: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Trigger model training.

        Args:
            model_type: Type of model to train (price, anomaly, demand, should_cost)
            parameters: Optional training parameters

        Returns:
            Training job status

        Raises:
            MLServiceError: If training trigger fails
        """
        try:
            client = self._get_client()
            payload = {'model_type': model_type}
            if parameters:
                payload['parameters'] = parameters

            response = client.post('/api/v1/models/train', json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to trigger training for {model_type}: {e}")
            raise MLServiceError(f"Failed to trigger training: {e}")

    # Analytics Methods

    def get_analytics_overview(self) -> Dict[str, Any]:
        """Get ML analytics overview"""
        try:
            client = self._get_client()
            response = client.get('/api/v1/analytics/overview')
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get analytics overview: {e}")
            raise MLServiceError(f"Failed to get analytics: {e}")

    def get_drift_status(self) -> Dict[str, Any]:
        """Get model drift detection status"""
        try:
            client = self._get_client()
            response = client.get('/api/v1/analytics/drift')
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get drift status: {e}")
            raise MLServiceError(f"Failed to get drift status: {e}")


# Singleton instance for convenience
_ml_client: Optional[MLServiceClient] = None


def get_ml_client() -> MLServiceClient:
    """Get singleton ML client instance"""
    global _ml_client
    if _ml_client is None:
        _ml_client = MLServiceClient()
    return _ml_client
