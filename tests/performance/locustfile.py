"""
Locust performance testing for the AI Pricing Agent system.
"""
import json
import random
import time
from locust import HttpUser, task, between, events
from locust.contrib.fasthttp import FastHttpUser
import jwt
from datetime import datetime, timedelta


class AuthenticatedUser(HttpUser):
    """Base class for authenticated user tests."""
    
    wait_time = between(1, 3)
    
    def on_start(self):
        """Login and get authentication token."""
        self.login()
        self.setup_test_data()
    
    def login(self):
        """Authenticate user and store token."""
        response = self.client.post("/auth/login/", json={
            "email": "test@example.com",
            "password": "testpass123"
        })
        
        if response.status_code == 200:
            data = response.json()
            self.token = data.get("access_token")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            self.token = None
            self.headers = {}
    
    def setup_test_data(self):
        """Setup test data for performance tests."""
        self.material_ids = list(range(1, 101))  # Assume 100 materials exist
        self.supplier_ids = list(range(1, 21))   # Assume 20 suppliers exist
        self.categories = ["steel", "aluminum", "plastic", "composite"]
        self.grades = ["A36", "6061", "304", "standard"]


class DjangoAPIUser(AuthenticatedUser):
    """Performance tests for Django API endpoints."""
    
    host = "http://localhost:8000"
    
    @task(3)
    def list_materials(self):
        """Test materials listing endpoint."""
        params = {
            "page": random.randint(1, 5),
            "page_size": random.choice([10, 25, 50]),
            "material_type": random.choice(["", "raw_material", "component"])
        }
        
        with self.client.get("/api/v1/materials/", 
                           params=params, 
                           headers=self.headers,
                           catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if len(data.get("results", [])) > 0:
                    response.success()
                else:
                    response.failure("No results returned")
            else:
                response.failure(f"HTTP {response.status_code}")
    
    @task(2)
    def get_material_detail(self):
        """Test material detail endpoint."""
        material_id = random.choice(self.material_ids)
        
        with self.client.get(f"/api/v1/materials/{material_id}/",
                           headers=self.headers,
                           catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 404:
                response.success()  # Expected for non-existent materials
            else:
                response.failure(f"HTTP {response.status_code}")
    
    @task(2)
    def get_price_history(self):
        """Test price history endpoint."""
        material_id = random.choice(self.material_ids)
        params = {
            "days": random.choice([7, 30, 90]),
            "price_type": random.choice(["", "quote", "market"])
        }
        
        self.client.get(f"/api/v1/materials/{material_id}/price-history/",
                       params=params,
                       headers=self.headers)
    
    @task(1)
    def create_rfq(self):
        """Test RFQ creation endpoint."""
        rfq_data = {
            "title": f"Load Test RFQ {random.randint(1000, 9999)}",
            "description": "Performance test RFQ",
            "category": random.choice(self.categories),
            "delivery_date": "2024-12-31",
            "materials": [
                {
                    "material_id": random.choice(self.material_ids),
                    "quantity": random.randint(100, 2000),
                    "specifications": {
                        "grade": random.choice(self.grades),
                        "thickness": random.uniform(1, 50)
                    }
                }
            ]
        }
        
        with self.client.post("/api/v1/rfqs/",
                            json=rfq_data,
                            headers=self.headers,
                            catch_response=True) as response:
            if response.status_code == 201:
                response.success()
            else:
                response.failure(f"Failed to create RFQ: HTTP {response.status_code}")
    
    @task(1)
    def search_materials(self):
        """Test material search endpoint."""
        search_terms = ["steel", "aluminum", "plate", "rod", "sheet"]
        params = {
            "search": random.choice(search_terms),
            "category": random.choice(["", "construction", "automotive"])
        }
        
        self.client.get("/api/v1/materials/search/",
                       params=params,
                       headers=self.headers)
    
    @task(1)
    def get_analytics_data(self):
        """Test analytics endpoint."""
        params = {
            "metric": random.choice(["price_trends", "volume_analysis", "supplier_performance"]),
            "period": random.choice(["7d", "30d", "90d"]),
            "material_ids": ",".join(map(str, random.sample(self.material_ids, 3)))
        }
        
        self.client.get("/api/v1/analytics/",
                       params=params,
                       headers=self.headers)


class MLServiceUser(FastHttpUser):
    """Performance tests for FastAPI ML service."""
    
    host = "http://localhost:8001"
    wait_time = between(0.5, 2)
    
    def on_start(self):
        """Setup ML service test data."""
        self.material_types = ["steel", "aluminum", "plastic", "composite"]
        self.grades = ["A36", "6061", "304", "standard"]
    
    @task(5)
    def predict_price(self):
        """Test price prediction endpoint."""
        prediction_data = {
            "material_specifications": {
                "material_type": random.choice(self.material_types),
                "grade": random.choice(self.grades),
                "thickness": random.uniform(1, 50),
                "width": random.uniform(10, 500),
                "length": random.uniform(10, 1000)
            },
            "quantity": random.randint(1, 5000),
            "delivery_location": random.choice([
                "New York, NY", "Los Angeles, CA", "Chicago, IL", 
                "Houston, TX", "Philadelphia, PA"
            ]),
            "delivery_date": "2024-12-31"
        }
        
        with self.client.post("/api/v1/predictions/",
                            json=prediction_data,
                            catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if "prediction" in data and "confidence" in data:
                    response.success()
                else:
                    response.failure("Invalid response format")
            else:
                response.failure(f"HTTP {response.status_code}")
    
    @task(2)
    def batch_predict(self):
        """Test batch prediction endpoint."""
        requests = []
        for _ in range(random.randint(2, 10)):
            requests.append({
                "material_specifications": {
                    "material_type": random.choice(self.material_types),
                    "grade": random.choice(self.grades),
                    "thickness": random.uniform(1, 50),
                    "width": random.uniform(10, 500),
                    "length": random.uniform(10, 1000)
                },
                "quantity": random.randint(1, 2000)
            })
        
        batch_data = {"requests": requests}
        
        with self.client.post("/api/v1/predictions/batch/",
                            json=batch_data,
                            catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if len(data.get("predictions", [])) == len(requests):
                    response.success()
                else:
                    response.failure("Batch prediction count mismatch")
            else:
                response.failure(f"HTTP {response.status_code}")
    
    @task(1)
    def get_model_info(self):
        """Test model information endpoint."""
        self.client.get("/api/v1/models/info/")
    
    @task(1)
    def health_check(self):
        """Test health check endpoint."""
        with self.client.get("/health/",
                           catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "healthy":
                    response.success()
                else:
                    response.failure("Service not healthy")
            else:
                response.failure(f"Health check failed: HTTP {response.status_code}")


class DatabaseLoadUser(AuthenticatedUser):
    """Specific tests for database performance under load."""
    
    host = "http://localhost:8000"
    
    @task(3)
    def concurrent_price_queries(self):
        """Test concurrent price data queries."""
        material_id = random.choice(self.material_ids)
        
        # Simulate multiple concurrent queries that might happen
        queries = [
            f"/api/v1/materials/{material_id}/prices/current/",
            f"/api/v1/materials/{material_id}/price-history/",
            f"/api/v1/materials/{material_id}/price-trends/",
            f"/api/v1/materials/{material_id}/benchmarks/"
        ]
        
        query = random.choice(queries)
        self.client.get(query, headers=self.headers)
    
    @task(2)
    def bulk_data_operations(self):
        """Test bulk data operations."""
        # Simulate bulk price update
        price_data = []
        for _ in range(random.randint(10, 100)):
            price_data.append({
                "material_id": random.choice(self.material_ids),
                "supplier_id": random.choice(self.supplier_ids),
                "price": random.uniform(1, 1000),
                "quantity": random.randint(1, 1000),
                "currency": "USD",
                "price_type": random.choice(["quote", "market", "contract"])
            })
        
        self.client.post("/api/v1/prices/bulk/",
                        json={"prices": price_data},
                        headers=self.headers)
    
    @task(1)
    def complex_analytics_query(self):
        """Test complex analytics queries."""
        params = {
            "metrics": ["avg_price", "price_volatility", "volume"],
            "group_by": ["material_type", "supplier"],
            "filter": {
                "date_range": "30d",
                "material_types": random.sample(self.categories, 2),
                "min_quantity": 100
            }
        }
        
        self.client.post("/api/v1/analytics/complex/",
                        json=params,
                        headers=self.headers)


class StressTestUser(AuthenticatedUser):
    """Stress tests for system limits."""
    
    host = "http://localhost:8000"
    wait_time = between(0.1, 0.5)  # Faster requests for stress testing
    
    @task
    def rapid_api_calls(self):
        """Make rapid API calls to test system limits."""
        endpoints = [
            "/api/v1/materials/",
            "/api/v1/suppliers/",
            "/api/v1/rfqs/",
            "/api/v1/quotes/"
        ]
        
        endpoint = random.choice(endpoints)
        self.client.get(endpoint, headers=self.headers)


# Custom event handlers for performance metrics
@events.request.add_listener
def request_handler(request_type, name, response_time, response_length, exception, **kwargs):
    """Custom request handler for performance metrics."""
    if response_time > 2000:  # Log slow requests (>2s)
        print(f"SLOW REQUEST: {name} took {response_time}ms")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Handle test start event."""
    print("Starting performance test...")
    print(f"Target host: {environment.host}")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Handle test stop event."""
    print("Performance test completed.")
    
    # Print summary statistics
    stats = environment.stats
    print(f"Total requests: {stats.total.num_requests}")
    print(f"Failed requests: {stats.total.num_failures}")
    print(f"Average response time: {stats.total.avg_response_time:.2f}ms")
    print(f"95th percentile: {stats.total.get_response_time_percentile(0.95):.2f}ms")


# Performance test scenarios
class LightLoad(DjangoAPIUser):
    """Light load test scenario."""
    wait_time = between(5, 10)
    weight = 3


class NormalLoad(DjangoAPIUser):
    """Normal load test scenario."""
    wait_time = between(2, 5)
    weight = 5


class HeavyLoad(DjangoAPIUser):
    """Heavy load test scenario."""
    wait_time = between(1, 3)
    weight = 2


class SpikeLoad(StressTestUser):
    """Spike load test scenario."""
    wait_time = between(0.1, 1)
    weight = 1


# ML Service specific load tests
class MLLightLoad(MLServiceUser):
    """Light load for ML service."""
    wait_time = between(3, 8)
    weight = 3


class MLHeavyLoad(MLServiceUser):
    """Heavy load for ML service."""
    wait_time = between(0.5, 2)
    weight = 2


if __name__ == "__main__":
    """
    Run locust directly for quick testing.
    
    Usage:
    python locustfile.py --host=http://localhost:8000 --users=50 --spawn-rate=5 --run-time=300s
    """
    import os
    os.system("locust -f locustfile.py --host=http://localhost:8000")