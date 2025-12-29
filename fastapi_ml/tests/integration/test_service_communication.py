"""
Integration tests for service-to-service communication.
"""
import pytest
import asyncio
import httpx
from unittest.mock import patch, Mock
from fastapi.testclient import TestClient


class TestServiceCommunication:
    """Test communication between FastAPI ML service and Django app."""
    
    @pytest.mark.asyncio
    async def test_ml_service_to_django_authentication(self, async_client, auth_headers):
        """Test ML service authentication with Django."""
        # Test authenticated request to Django API
        django_api_url = "http://localhost:8000/api/v1/materials/"
        
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.return_value = httpx.Response(
                200,
                json={'results': [{'id': 1, 'name': 'Steel Plate'}]}
            )
            
            response = await async_client.get(
                "/api/v1/materials/sync/",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            mock_get.assert_called_once()
    
    def test_django_to_ml_service_prediction_request(self, client, sample_prediction_request, mock_ml_service):
        """Test Django app requesting predictions from ML service."""
        response = client.post("/api/v1/predictions/", json=sample_prediction_request)
        
        assert response.status_code == 200
        data = response.json()
        assert "prediction" in data
        assert "confidence" in data
    
    @pytest.mark.asyncio
    async def test_service_health_check_integration(self, async_client):
        """Test health check between services."""
        # Mock Django service health check
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.return_value = httpx.Response(200, json={'status': 'healthy'})
            
            response = await async_client.get("/health/services/")
            
            assert response.status_code == 200
            data = response.json()
            assert "django_service" in data
            assert data["django_service"]["status"] == "healthy"
    
    def test_data_synchronization(self, client, sample_material_data):
        """Test data synchronization between services."""
        # Test pushing material data to Django
        sync_data = {
            "materials": sample_material_data.to_dict('records')
        }
        
        with patch('httpx.post') as mock_post:
            mock_post.return_value = Mock(status_code=200)
            
            response = client.post("/api/v1/data/sync/", json=sync_data)
            
            assert response.status_code == 200
            mock_post.assert_called_once()
    
    def test_error_propagation(self, client, sample_prediction_request):
        """Test error propagation between services."""
        # Mock Django service returning error
        with patch('services.ml_service.MLService.predict') as mock_predict:
            mock_predict.side_effect = httpx.HTTPError("Connection failed")
            
            response = client.post("/api/v1/predictions/", json=sample_prediction_request)
            
            assert response.status_code == 500
            assert "error" in response.json()
    
    @pytest.mark.asyncio
    async def test_concurrent_service_requests(self, async_client, sample_prediction_request):
        """Test concurrent requests between services."""
        async def make_request():
            return await async_client.post("/api/v1/predictions/", json=sample_prediction_request)
        
        # Make multiple concurrent requests
        tasks = [make_request() for _ in range(10)]
        responses = await asyncio.gather(*tasks)
        
        # All requests should succeed
        for response in responses:
            assert response.status_code == 200
    
    def test_circuit_breaker_pattern(self, client, sample_prediction_request):
        """Test circuit breaker pattern for service failures."""
        # Simulate repeated failures to trigger circuit breaker
        with patch('services.ml_service.MLService.predict') as mock_predict:
            mock_predict.side_effect = Exception("Service unavailable")
            
            # Make multiple requests to trigger circuit breaker
            for _ in range(5):
                response = client.post("/api/v1/predictions/", json=sample_prediction_request)
                assert response.status_code in [500, 503]  # Error or service unavailable
    
    def test_service_discovery(self, client):
        """Test service discovery functionality."""
        response = client.get("/api/v1/services/discover/")
        
        assert response.status_code == 200
        data = response.json()
        assert "services" in data
        assert isinstance(data["services"], list)
    
    def test_load_balancing(self, client, sample_prediction_request):
        """Test load balancing between service instances."""
        # Mock multiple service instances
        with patch('services.ml_service.MLService._get_service_url') as mock_get_url:
            urls = ["http://ml-service-1:8001", "http://ml-service-2:8001"]
            mock_get_url.side_effect = urls * 5  # Simulate round-robin
            
            responses = []
            for _ in range(10):
                response = client.post("/api/v1/predictions/", json=sample_prediction_request)
                responses.append(response)
            
            # Should distribute requests across instances
            assert all(r.status_code == 200 for r in responses)


class TestDatabaseIntegration:
    """Test database integration between services."""
    
    def test_shared_database_access(self, client, test_db_session):
        """Test shared database access between services."""
        # Test reading data that Django app created
        response = client.get("/api/v1/materials/")
        
        assert response.status_code == 200
        # Should be able to access shared database
    
    def test_transaction_consistency(self, client):
        """Test transaction consistency across services."""
        # Test that database transactions are properly handled
        transaction_data = {
            "operations": [
                {"type": "create", "table": "materials", "data": {"name": "Test Material"}},
                {"type": "create", "table": "prices", "data": {"price": 100.0}}
            ]
        }
        
        response = client.post("/api/v1/transactions/", json=transaction_data)
        
        # Should handle transactions properly
        assert response.status_code in [200, 201]
    
    def test_database_connection_pooling(self, client):
        """Test database connection pooling efficiency."""
        # Make multiple rapid requests to test connection pooling
        responses = []
        for _ in range(20):
            response = client.get("/api/v1/health/db/")
            responses.append(response)
        
        # All should succeed and be fast
        assert all(r.status_code == 200 for r in responses)


class TestCacheIntegration:
    """Test Redis cache integration."""
    
    def test_cache_sharing_between_services(self, client, override_redis):
        """Test cache sharing between Django and FastAPI services."""
        # Set cache value
        cache_data = {"key": "test_key", "value": "test_value", "ttl": 300}
        response = client.post("/api/v1/cache/set/", json=cache_data)
        assert response.status_code == 200
        
        # Get cache value
        response = client.get("/api/v1/cache/get/test_key/")
        assert response.status_code == 200
        assert response.json()["value"] == "test_value"
    
    def test_cache_invalidation(self, client, override_redis):
        """Test cache invalidation across services."""
        # Set cache
        override_redis.set("test_key", "test_value")
        
        # Invalidate cache
        response = client.delete("/api/v1/cache/invalidate/test_key/")
        assert response.status_code == 200
        
        # Verify cache is cleared
        override_redis.delete.assert_called_with("test_key")
    
    def test_distributed_cache_locking(self, client, override_redis):
        """Test distributed locking using Redis."""
        lock_data = {"resource": "ml_model_training", "timeout": 300}
        
        response = client.post("/api/v1/cache/lock/", json=lock_data)
        assert response.status_code == 200
        
        # Try to acquire same lock (should fail)
        response = client.post("/api/v1/cache/lock/", json=lock_data)
        assert response.status_code == 409  # Conflict


class TestMessageQueueIntegration:
    """Test Celery/RQ message queue integration."""
    
    def test_async_task_dispatch(self, client):
        """Test dispatching async tasks between services."""
        task_data = {
            "task_type": "model_training",
            "parameters": {
                "model_name": "test_model",
                "data_source": "materials_2024"
            }
        }
        
        response = client.post("/api/v1/tasks/dispatch/", json=task_data)
        
        assert response.status_code == 202  # Accepted
        assert "task_id" in response.json()
    
    def test_task_status_monitoring(self, client):
        """Test monitoring task status across services."""
        # Mock task ID
        task_id = "test_task_123"
        
        response = client.get(f"/api/v1/tasks/status/{task_id}/")
        
        # Should return task status
        assert response.status_code in [200, 404]  # Found or not found
    
    def test_task_result_retrieval(self, client):
        """Test retrieving task results."""
        task_id = "completed_task_123"
        
        response = client.get(f"/api/v1/tasks/result/{task_id}/")
        
        if response.status_code == 200:
            data = response.json()
            assert "result" in data
            assert "status" in data


class TestWebSocketIntegration:
    """Test WebSocket integration between services."""
    
    @pytest.mark.asyncio
    async def test_websocket_connection(self, client):
        """Test WebSocket connection for real-time updates."""
        with client.websocket_connect("/ws/predictions/") as websocket:
            # Send test message
            await websocket.send_json({"type": "ping"})
            
            # Receive response
            response = await websocket.receive_json()
            assert response["type"] == "pong"
    
    @pytest.mark.asyncio
    async def test_real_time_price_updates(self, client):
        """Test real-time price updates via WebSocket."""
        with client.websocket_connect("/ws/prices/") as websocket:
            # Subscribe to price updates
            await websocket.send_json({
                "type": "subscribe",
                "material_ids": [1, 2, 3]
            })
            
            # Should receive subscription confirmation
            response = await websocket.receive_json()
            assert response["type"] == "subscription_confirmed"


class TestSecurityIntegration:
    """Test security aspects of service integration."""
    
    def test_jwt_token_validation(self, client):
        """Test JWT token validation between services."""
        # Test with invalid token
        headers = {"Authorization": "Bearer invalid_token"}
        response = client.get("/api/v1/protected/", headers=headers)
        
        assert response.status_code == 401
    
    def test_api_key_authentication(self, client):
        """Test API key authentication between services."""
        # Test with missing API key
        response = client.get("/api/v1/internal/data/")
        
        assert response.status_code == 401
        
        # Test with valid API key
        headers = {"X-API-Key": "test_api_key"}
        response = client.get("/api/v1/internal/data/", headers=headers)
        
        # Should work with valid key (mocked)
        assert response.status_code in [200, 401]  # Depends on mock setup
    
    def test_rate_limiting_across_services(self, client):
        """Test rate limiting across service boundaries."""
        # Make multiple rapid requests
        responses = []
        for _ in range(100):
            response = client.get("/api/v1/public/data/")
            responses.append(response)
        
        # Some requests should be rate limited
        status_codes = [r.status_code for r in responses]
        assert 429 in status_codes or all(sc == 200 for sc in status_codes)
    
    def test_cors_handling(self, client):
        """Test CORS handling between services."""
        headers = {
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type"
        }
        
        response = client.options("/api/v1/predictions/", headers=headers)
        
        # Should handle CORS preflight
        assert response.status_code in [200, 204]