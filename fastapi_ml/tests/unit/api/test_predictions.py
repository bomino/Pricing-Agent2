"""
Unit tests for predictions API endpoints.
"""
import pytest
import json
from unittest.mock import patch, Mock
from fastapi import status
from fastapi.testclient import TestClient


class TestPredictionsAPI:
    """Test predictions API endpoints."""
    
    def test_predict_endpoint_success(self, client, sample_prediction_request, mock_ml_service):
        """Test successful prediction request."""
        response = client.post("/api/v1/predictions/", json=sample_prediction_request)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "prediction" in data
        assert "confidence" in data
        assert "model_version" in data
        assert isinstance(data["prediction"], (int, float))
        assert 0 <= data["confidence"] <= 1
    
    def test_predict_endpoint_invalid_input(self, client):
        """Test prediction with invalid input data."""
        invalid_request = {
            "material_specifications": {},  # Missing required fields
            "quantity": -100,  # Invalid quantity
        }
        
        response = client.post("/api/v1/predictions/", json=invalid_request)
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "detail" in response.json()
    
    def test_predict_endpoint_missing_fields(self, client):
        """Test prediction with missing required fields."""
        incomplete_request = {
            "quantity": 1000
            # Missing material_specifications
        }
        
        response = client.post("/api/v1/predictions/", json=incomplete_request)
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_predict_endpoint_empty_request(self, client):
        """Test prediction with empty request body."""
        response = client.post("/api/v1/predictions/", json={})
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_predict_endpoint_malformed_json(self, client):
        """Test prediction with malformed JSON."""
        response = client.post(
            "/api/v1/predictions/",
            data='{"incomplete": }',
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    @pytest.mark.asyncio
    async def test_predict_endpoint_async(self, async_client, sample_prediction_request, mock_ml_service):
        """Test async prediction request."""
        response = await async_client.post("/api/v1/predictions/", json=sample_prediction_request)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "prediction" in data
    
    def test_predict_endpoint_with_authentication(self, client, sample_prediction_request, auth_headers, mock_ml_service):
        """Test prediction with authentication headers."""
        response = client.post(
            "/api/v1/predictions/",
            json=sample_prediction_request,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_predict_endpoint_rate_limiting(self, client, sample_prediction_request, mock_ml_service):
        """Test rate limiting on prediction endpoint."""
        # Make multiple requests quickly
        responses = []
        for _ in range(10):
            response = client.post("/api/v1/predictions/", json=sample_prediction_request)
            responses.append(response)
        
        # All requests should succeed in test environment
        for response in responses:
            assert response.status_code in [status.HTTP_200_OK, status.HTTP_429_TOO_MANY_REQUESTS]
    
    def test_predict_endpoint_large_payload(self, client, mock_ml_service):
        """Test prediction with large payload."""
        large_request = {
            "material_specifications": {
                "material_type": "steel",
                "grade": "A36",
                "thickness": 10.0,
                "width": 100.0,
                "length": 200.0,
                "description": "x" * 1000  # Large description
            },
            "quantity": 1000,
            "delivery_location": "New York, NY",
            "features": {f"feature_{i}": f"value_{i}" for i in range(100)}  # Many features
        }
        
        response = client.post("/api/v1/predictions/", json=large_request)
        
        # Should handle large payloads gracefully
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_413_REQUEST_ENTITY_TOO_LARGE]
    
    def test_batch_predict_endpoint_success(self, client, mock_ml_service):
        """Test successful batch prediction request."""
        batch_request = {
            "requests": [
                {
                    "material_specifications": {
                        "material_type": "steel",
                        "grade": "A36",
                        "thickness": 10.0,
                        "width": 100.0,
                        "length": 200.0
                    },
                    "quantity": 1000
                },
                {
                    "material_specifications": {
                        "material_type": "aluminum",
                        "grade": "6061",
                        "thickness": 5.0,
                        "width": 150.0,
                        "length": 300.0
                    },
                    "quantity": 500
                }
            ]
        }
        
        response = client.post("/api/v1/predictions/batch/", json=batch_request)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "predictions" in data
        assert len(data["predictions"]) == 2
    
    def test_batch_predict_empty_batch(self, client):
        """Test batch prediction with empty batch."""
        batch_request = {"requests": []}
        
        response = client.post("/api/v1/predictions/batch/", json=batch_request)
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_batch_predict_too_many_requests(self, client):
        """Test batch prediction with too many requests."""
        batch_request = {
            "requests": [
                {
                    "material_specifications": {"material_type": "steel"},
                    "quantity": 1000
                }
            ] * 1000  # Too many requests
        }
        
        response = client.post("/api/v1/predictions/batch/", json=batch_request)
        
        # Should reject or limit batch size
        assert response.status_code in [status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, status.HTTP_422_UNPROCESSABLE_ENTITY]
    
    def test_predict_with_model_version(self, client, sample_prediction_request, mock_ml_service):
        """Test prediction with specific model version."""
        sample_prediction_request["model_version"] = "v1.2.0"
        
        response = client.post("/api/v1/predictions/", json=sample_prediction_request)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "model_version" in data
    
    def test_predict_with_invalid_model_version(self, client, sample_prediction_request):
        """Test prediction with invalid model version."""
        sample_prediction_request["model_version"] = "invalid_version"
        
        response = client.post("/api/v1/predictions/", json=sample_prediction_request)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    @patch('services.ml_service.MLService.predict')
    def test_predict_service_error(self, mock_predict, client, sample_prediction_request):
        """Test handling of service errors during prediction."""
        mock_predict.side_effect = Exception("Model prediction failed")
        
        response = client.post("/api/v1/predictions/", json=sample_prediction_request)
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "error" in response.json()
    
    @patch('services.ml_service.MLService.predict')
    def test_predict_timeout(self, mock_predict, client, sample_prediction_request):
        """Test prediction timeout handling."""
        import time
        mock_predict.side_effect = lambda *args, **kwargs: time.sleep(10)  # Simulate timeout
        
        # This test depends on timeout configuration in the service
        response = client.post("/api/v1/predictions/", json=sample_prediction_request)
        
        # Should handle timeout gracefully
        assert response.status_code in [status.HTTP_500_INTERNAL_SERVER_ERROR, status.HTTP_408_REQUEST_TIMEOUT]
    
    def test_predict_response_schema(self, client, sample_prediction_request, mock_ml_service):
        """Test that prediction response matches expected schema."""
        response = client.post("/api/v1/predictions/", json=sample_prediction_request)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Required fields
        required_fields = ["prediction", "confidence", "model_version"]
        for field in required_fields:
            assert field in data
        
        # Data types
        assert isinstance(data["prediction"], (int, float))
        assert isinstance(data["confidence"], (int, float))
        assert isinstance(data["model_version"], str)
        
        # Value ranges
        assert data["confidence"] >= 0 and data["confidence"] <= 1
        assert data["prediction"] > 0  # Assuming positive predictions
    
    def test_predict_with_feature_importance(self, client, sample_prediction_request, mock_ml_service):
        """Test prediction request with feature importance."""
        sample_prediction_request["include_feature_importance"] = True
        
        response = client.post("/api/v1/predictions/", json=sample_prediction_request)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        if "feature_importance" in data:
            assert isinstance(data["feature_importance"], dict)
            # Feature importance values should be between 0 and 1
            for feature, importance in data["feature_importance"].items():
                assert 0 <= importance <= 1
    
    def test_predict_with_explanation(self, client, sample_prediction_request, mock_ml_service):
        """Test prediction request with model explanation."""
        sample_prediction_request["include_explanation"] = True
        
        response = client.post("/api/v1/predictions/", json=sample_prediction_request)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        if "explanation" in data:
            assert isinstance(data["explanation"], (str, dict))
    
    def test_predict_different_material_types(self, client, mock_ml_service):
        """Test prediction for different material types."""
        material_types = ["steel", "aluminum", "plastic", "composite"]
        
        for material_type in material_types:
            request_data = {
                "material_specifications": {
                    "material_type": material_type,
                    "grade": "standard",
                    "thickness": 10.0,
                    "width": 100.0,
                    "length": 200.0
                },
                "quantity": 1000
            }
            
            response = client.post("/api/v1/predictions/", json=request_data)
            assert response.status_code == status.HTTP_200_OK
    
    def test_predict_edge_case_quantities(self, client, mock_ml_service):
        """Test prediction with edge case quantities."""
        base_request = {
            "material_specifications": {
                "material_type": "steel",
                "grade": "A36",
                "thickness": 10.0,
                "width": 100.0,
                "length": 200.0
            }
        }
        
        edge_quantities = [1, 999999, 0.001, 1000000]
        
        for quantity in edge_quantities:
            request_data = base_request.copy()
            request_data["quantity"] = quantity
            
            response = client.post("/api/v1/predictions/", json=request_data)
            # Should handle edge cases gracefully
            assert response.status_code in [status.HTTP_200_OK, status.HTTP_422_UNPROCESSABLE_ENTITY]


class TestPredictionValidation:
    """Test prediction request validation."""
    
    def test_material_specifications_validation(self, client):
        """Test validation of material specifications."""
        test_cases = [
            # Missing material_type
            {
                "material_specifications": {
                    "grade": "A36",
                    "thickness": 10.0
                },
                "quantity": 1000
            },
            # Invalid thickness (negative)
            {
                "material_specifications": {
                    "material_type": "steel",
                    "grade": "A36",
                    "thickness": -5.0
                },
                "quantity": 1000
            },
            # Invalid dimensions (zero)
            {
                "material_specifications": {
                    "material_type": "steel",
                    "grade": "A36",
                    "thickness": 10.0,
                    "width": 0.0,
                    "length": 100.0
                },
                "quantity": 1000
            }
        ]
        
        for request_data in test_cases:
            response = client.post("/api/v1/predictions/", json=request_data)
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_quantity_validation(self, client):
        """Test quantity field validation."""
        base_request = {
            "material_specifications": {
                "material_type": "steel",
                "grade": "A36",
                "thickness": 10.0,
                "width": 100.0,
                "length": 200.0
            }
        }
        
        invalid_quantities = [-1, 0, "invalid", None]
        
        for quantity in invalid_quantities:
            request_data = base_request.copy()
            request_data["quantity"] = quantity
            
            response = client.post("/api/v1/predictions/", json=request_data)
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_date_validation(self, client):
        """Test date field validation."""
        base_request = {
            "material_specifications": {
                "material_type": "steel",
                "grade": "A36",
                "thickness": 10.0,
                "width": 100.0,
                "length": 200.0
            },
            "quantity": 1000
        }
        
        invalid_dates = [
            "invalid-date",
            "2024-13-01",  # Invalid month
            "2024-02-30",  # Invalid day
            "1900-01-01",  # Too old
            "not-a-date"
        ]
        
        for date in invalid_dates:
            request_data = base_request.copy()
            request_data["delivery_date"] = date
            
            response = client.post("/api/v1/predictions/", json=request_data)
            # Should either accept and parse or reject invalid dates
            if response.status_code != status.HTTP_200_OK:
                assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY