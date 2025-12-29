"""
Redis Caching Strategy for AI Pricing Agent
Comprehensive caching patterns, key structures, and TTL strategies
Designed for 10K concurrent users with optimal performance
"""

import json
import hashlib
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
from enum import Enum
import redis
from redis.exceptions import RedisError


class CacheKeyPatterns:
    """
    Centralized cache key naming conventions and patterns
    Format: {service}:{entity}:{identifier}:{sub_key}
    """
    
    # User and Authentication
    USER_SESSION = "auth:session:{session_id}"
    USER_PROFILE = "user:profile:{user_id}"
    USER_PERMISSIONS = "user:perms:{user_id}:{org_id}"
    API_KEY_VALIDATION = "auth:api:{key_hash}"
    LOGIN_ATTEMPTS = "auth:attempts:{email}:{ip}"
    
    # Organization and Multi-tenancy
    ORG_SETTINGS = "org:settings:{org_id}"
    ORG_USERS = "org:users:{org_id}"
    ORG_STATS = "org:stats:{org_id}:{date}"
    
    # Materials and Catalog
    MATERIAL_DETAILS = "material:details:{org_id}:{material_id}"
    MATERIAL_ATTRIBUTES = "material:attrs:{material_id}"
    MATERIAL_SEARCH = "material:search:{org_id}:{query_hash}"
    MATERIAL_CATEGORY = "category:tree:{org_id}:{category_id}"
    
    # Suppliers
    SUPPLIER_DETAILS = "supplier:details:{org_id}:{supplier_id}"
    SUPPLIER_MATERIALS = "supplier:materials:{supplier_id}"
    SUPPLIER_RATINGS = "supplier:rating:{supplier_id}:{period}"
    SUPPLIER_SEARCH = "supplier:search:{org_id}:{query_hash}"
    
    # Pricing Data (Hot cache for recent prices)
    LATEST_PRICE = "price:latest:{org_id}:{material_id}:{supplier_id}"
    PRICE_HISTORY = "price:history:{material_id}:{days}"
    PRICE_TRENDS = "price:trends:{material_id}:{period}"
    MARKET_DATA = "market:latest:{symbol}"
    PRICE_ALERTS = "price:alerts:{user_id}"
    
    # RFQs and Quotes
    RFQ_DETAILS = "rfq:details:{org_id}:{rfq_id}"
    RFQ_ITEMS = "rfq:items:{rfq_id}"
    RFQ_SUPPLIERS = "rfq:suppliers:{rfq_id}"
    QUOTE_DETAILS = "quote:details:{org_id}:{quote_id}"
    QUOTE_COMPARISON = "quote:compare:{rfq_id}"
    ACTIVE_RFQS = "rfq:active:{org_id}:{user_id}"
    
    # Contracts
    CONTRACT_DETAILS = "contract:details:{org_id}:{contract_id}"
    CONTRACT_ITEMS = "contract:items:{contract_id}"
    EXPIRING_CONTRACTS = "contract:expiring:{org_id}:{days}"
    
    # ML and Analytics
    ML_PREDICTION = "ml:prediction:{model_id}:{entity_type}:{entity_id}"
    ML_FEATURES = "ml:features:{entity_type}:{entity_id}:{feature_group}"
    ANALYTICS_DASHBOARD = "analytics:dashboard:{org_id}:{user_id}:{period}"
    PRICE_FORECAST = "ml:forecast:{material_id}:{horizon_days}"
    
    # System and Performance
    QUERY_RESULT = "query:result:{query_hash}"
    SLOW_QUERY_LOG = "perf:slow_queries:{date}"
    RATE_LIMIT = "rate:limit:{user_id}:{endpoint}"
    FEATURE_FLAGS = "system:features:{org_id}"


class TTLStrategies(Enum):
    """
    Time-To-Live strategies for different data types
    """
    # Authentication and Sessions
    USER_SESSION = 28800  # 8 hours
    API_KEY_VALIDATION = 3600  # 1 hour
    LOGIN_ATTEMPTS = 900  # 15 minutes
    
    # User Data
    USER_PROFILE = 1800  # 30 minutes
    USER_PERMISSIONS = 900  # 15 minutes
    
    # Organization Data
    ORG_SETTINGS = 3600  # 1 hour
    ORG_USERS = 600  # 10 minutes
    
    # Master Data (relatively stable)
    MATERIAL_DETAILS = 3600  # 1 hour
    MATERIAL_ATTRIBUTES = 1800  # 30 minutes
    SUPPLIER_DETAILS = 1800  # 30 minutes
    
    # Search Results
    SEARCH_RESULTS = 300  # 5 minutes
    
    # Pricing Data (time-sensitive)
    LATEST_PRICE = 120  # 2 minutes
    PRICE_HISTORY = 600  # 10 minutes
    MARKET_DATA = 60  # 1 minute
    
    # Workflow Data
    RFQ_DETAILS = 300  # 5 minutes
    QUOTE_DETAILS = 300  # 5 minutes
    
    # Analytics and Reports
    ANALYTICS_DASHBOARD = 1800  # 30 minutes
    ML_PREDICTIONS = 3600  # 1 hour
    
    # System Performance
    QUERY_RESULT = 180  # 3 minutes
    RATE_LIMIT = 3600  # 1 hour


class RedisCache:
    """
    Advanced Redis caching implementation with patterns and strategies
    """
    
    def __init__(self, 
                 host: str = 'localhost',
                 port: int = 6379,
                 db: int = 0,
                 password: Optional[str] = None,
                 max_connections: int = 50,
                 decode_responses: bool = True):
        
        self.pool = redis.ConnectionPool(
            host=host,
            port=port,
            db=db,
            password=password,
            max_connections=max_connections,
            decode_responses=decode_responses
        )
        self.redis = redis.Redis(connection_pool=self.pool)
        
    def _serialize(self, value: Any) -> str:
        """Serialize value for Redis storage"""
        if isinstance(value, (dict, list)):
            return json.dumps(value, default=str)
        return str(value)
    
    def _deserialize(self, value: str) -> Any:
        """Deserialize value from Redis"""
        if not value:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    
    def _generate_query_hash(self, query: str, params: Dict = None) -> str:
        """Generate hash for query caching"""
        query_string = f"{query}_{json.dumps(params or {}, sort_keys=True)}"
        return hashlib.md5(query_string.encode()).hexdigest()[:16]
    
    # =====================================================================
    # USER AND AUTHENTICATION CACHING
    # =====================================================================
    
    def cache_user_session(self, session_id: str, user_data: Dict, ttl: int = None) -> bool:
        """Cache user session data"""
        key = CacheKeyPatterns.USER_SESSION.format(session_id=session_id)
        ttl = ttl or TTLStrategies.USER_SESSION.value
        
        try:
            return self.redis.setex(key, ttl, self._serialize(user_data))
        except RedisError:
            return False
    
    def get_user_session(self, session_id: str) -> Optional[Dict]:
        """Retrieve user session data"""
        key = CacheKeyPatterns.USER_SESSION.format(session_id=session_id)
        
        try:
            data = self.redis.get(key)
            return self._deserialize(data) if data else None
        except RedisError:
            return None
    
    def cache_user_permissions(self, user_id: int, org_id: int, permissions: List[str]) -> bool:
        """Cache user permissions for fast authorization checks"""
        key = CacheKeyPatterns.USER_PERMISSIONS.format(user_id=user_id, org_id=org_id)
        ttl = TTLStrategies.USER_PERMISSIONS.value
        
        try:
            # Use Redis sets for efficient permission checking
            pipe = self.redis.pipeline()
            pipe.delete(key)
            if permissions:
                pipe.sadd(key, *permissions)
            pipe.expire(key, ttl)
            pipe.execute()
            return True
        except RedisError:
            return False
    
    def has_permission(self, user_id: int, org_id: int, permission: str) -> bool:
        """Check if user has specific permission"""
        key = CacheKeyPatterns.USER_PERMISSIONS.format(user_id=user_id, org_id=org_id)
        
        try:
            return self.redis.sismember(key, permission)
        except RedisError:
            return False
    
    def track_login_attempts(self, email: str, ip_address: str, 
                           max_attempts: int = 5, window: int = 900) -> Dict:
        """Track and limit login attempts"""
        key = CacheKeyPatterns.LOGIN_ATTEMPTS.format(email=email, ip=ip_address)
        
        try:
            current = self.redis.get(key) or "0"
            attempts = int(current) + 1
            
            if attempts == 1:
                self.redis.setex(key, window, attempts)
            else:
                self.redis.set(key, attempts, keepttl=True)
            
            return {
                'attempts': attempts,
                'max_attempts': max_attempts,
                'locked': attempts >= max_attempts,
                'ttl': self.redis.ttl(key)
            }
        except RedisError:
            return {'attempts': 0, 'max_attempts': max_attempts, 'locked': False, 'ttl': 0}
    
    # =====================================================================
    # PRICING AND MARKET DATA CACHING
    # =====================================================================
    
    def cache_latest_price(self, org_id: int, material_id: int, 
                          supplier_id: Optional[int], price_data: Dict) -> bool:
        """Cache latest price for fast lookups"""
        key = CacheKeyPatterns.LATEST_PRICE.format(
            org_id=org_id, 
            material_id=material_id, 
            supplier_id=supplier_id or 'all'
        )
        ttl = TTLStrategies.LATEST_PRICE.value
        
        try:
            return self.redis.setex(key, ttl, self._serialize(price_data))
        except RedisError:
            return False
    
    def get_latest_price(self, org_id: int, material_id: int, 
                        supplier_id: Optional[int] = None) -> Optional[Dict]:
        """Retrieve cached latest price"""
        key = CacheKeyPatterns.LATEST_PRICE.format(
            org_id=org_id,
            material_id=material_id,
            supplier_id=supplier_id or 'all'
        )
        
        try:
            data = self.redis.get(key)
            return self._deserialize(data) if data else None
        except RedisError:
            return None
    
    def cache_price_trends(self, material_id: int, period: str, trend_data: Dict) -> bool:
        """Cache price trend analysis"""
        key = CacheKeyPatterns.PRICE_TRENDS.format(material_id=material_id, period=period)
        ttl = TTLStrategies.ANALYTICS_DASHBOARD.value
        
        try:
            return self.redis.setex(key, ttl, self._serialize(trend_data))
        except RedisError:
            return False
    
    def cache_market_data(self, symbol: str, market_data: Dict) -> bool:
        """Cache real-time market data"""
        key = CacheKeyPatterns.MARKET_DATA.format(symbol=symbol)
        ttl = TTLStrategies.MARKET_DATA.value
        
        try:
            # Store current data
            current_success = self.redis.setex(key, ttl, self._serialize(market_data))
            
            # Store in time series for historical data
            ts_key = f"market:timeseries:{symbol}"
            timestamp = int(datetime.now().timestamp())
            ts_success = self.redis.zadd(ts_key, {self._serialize(market_data): timestamp})
            
            # Keep only last 24 hours of time series data
            cutoff = timestamp - 86400
            self.redis.zremrangebyscore(ts_key, 0, cutoff)
            self.redis.expire(ts_key, 86400)
            
            return current_success and ts_success
        except RedisError:
            return False
    
    # =====================================================================
    # SEARCH AND QUERY RESULT CACHING
    # =====================================================================
    
    def cache_search_results(self, org_id: int, query: str, params: Dict, 
                           results: List[Dict]) -> bool:
        """Cache search results with query hash"""
        query_hash = self._generate_query_hash(query, params)
        key = CacheKeyPatterns.MATERIAL_SEARCH.format(org_id=org_id, query_hash=query_hash)
        ttl = TTLStrategies.SEARCH_RESULTS.value
        
        try:
            cache_data = {
                'query': query,
                'params': params,
                'results': results,
                'cached_at': datetime.now().isoformat(),
                'count': len(results)
            }
            return self.redis.setex(key, ttl, self._serialize(cache_data))
        except RedisError:
            return False
    
    def get_cached_search(self, org_id: int, query: str, params: Dict) -> Optional[Dict]:
        """Retrieve cached search results"""
        query_hash = self._generate_query_hash(query, params)
        key = CacheKeyPatterns.MATERIAL_SEARCH.format(org_id=org_id, query_hash=query_hash)
        
        try:
            data = self.redis.get(key)
            return self._deserialize(data) if data else None
        except RedisError:
            return None
    
    def cache_query_result(self, query: str, params: Dict, result: Any) -> bool:
        """Cache database query results"""
        query_hash = self._generate_query_hash(query, params)
        key = CacheKeyPatterns.QUERY_RESULT.format(query_hash=query_hash)
        ttl = TTLStrategies.QUERY_RESULT.value
        
        try:
            cache_data = {
                'result': result,
                'query_hash': query_hash,
                'cached_at': datetime.now().isoformat()
            }
            return self.redis.setex(key, ttl, self._serialize(cache_data))
        except RedisError:
            return False
    
    # =====================================================================
    # RFQ AND QUOTE WORKFLOW CACHING
    # =====================================================================
    
    def cache_rfq_details(self, org_id: int, rfq_id: int, rfq_data: Dict) -> bool:
        """Cache RFQ details for fast access"""
        key = CacheKeyPatterns.RFQ_DETAILS.format(org_id=org_id, rfq_id=rfq_id)
        ttl = TTLStrategies.RFQ_DETAILS.value
        
        try:
            return self.redis.setex(key, ttl, self._serialize(rfq_data))
        except RedisError:
            return False
    
    def cache_quote_comparison(self, rfq_id: int, comparison_data: Dict) -> bool:
        """Cache quote comparison analysis"""
        key = CacheKeyPatterns.QUOTE_COMPARISON.format(rfq_id=rfq_id)
        ttl = TTLStrategies.ANALYTICS_DASHBOARD.value
        
        try:
            return self.redis.setex(key, ttl, self._serialize(comparison_data))
        except RedisError:
            return False
    
    def get_active_rfqs(self, org_id: int, user_id: int) -> Optional[List[Dict]]:
        """Get cached active RFQs for user"""
        key = CacheKeyPatterns.ACTIVE_RFQS.format(org_id=org_id, user_id=user_id)
        
        try:
            data = self.redis.get(key)
            return self._deserialize(data) if data else None
        except RedisError:
            return None
    
    # =====================================================================
    # ML AND ANALYTICS CACHING
    # =====================================================================
    
    def cache_ml_prediction(self, model_id: int, entity_type: str, 
                           entity_id: int, prediction: Dict) -> bool:
        """Cache ML model predictions"""
        key = CacheKeyPatterns.ML_PREDICTION.format(
            model_id=model_id,
            entity_type=entity_type,
            entity_id=entity_id
        )
        ttl = TTLStrategies.ML_PREDICTIONS.value
        
        try:
            prediction_data = {
                **prediction,
                'cached_at': datetime.now().isoformat(),
                'model_id': model_id
            }
            return self.redis.setex(key, ttl, self._serialize(prediction_data))
        except RedisError:
            return False
    
    def cache_price_forecast(self, material_id: int, horizon_days: int, 
                           forecast_data: Dict) -> bool:
        """Cache price forecasting results"""
        key = CacheKeyPatterns.PRICE_FORECAST.format(
            material_id=material_id,
            horizon_days=horizon_days
        )
        ttl = TTLStrategies.ML_PREDICTIONS.value
        
        try:
            return self.redis.setex(key, ttl, self._serialize(forecast_data))
        except RedisError:
            return False
    
    def cache_analytics_dashboard(self, org_id: int, user_id: int, 
                                period: str, dashboard_data: Dict) -> bool:
        """Cache dashboard analytics data"""
        key = CacheKeyPatterns.ANALYTICS_DASHBOARD.format(
            org_id=org_id,
            user_id=user_id,
            period=period
        )
        ttl = TTLStrategies.ANALYTICS_DASHBOARD.value
        
        try:
            return self.redis.setex(key, ttl, self._serialize(dashboard_data))
        except RedisError:
            return False
    
    # =====================================================================
    # RATE LIMITING AND PERFORMANCE
    # =====================================================================
    
    def check_rate_limit(self, user_id: int, endpoint: str, 
                        limit: int, window: int) -> Dict:
        """Implement rate limiting using sliding window"""
        key = CacheKeyPatterns.RATE_LIMIT.format(user_id=user_id, endpoint=endpoint)
        
        try:
            current_time = datetime.now().timestamp()
            pipe = self.redis.pipeline()
            
            # Remove old entries outside the window
            pipe.zremrangebyscore(key, 0, current_time - window)
            
            # Count current requests
            pipe.zcard(key)
            
            # Add current request
            pipe.zadd(key, {str(current_time): current_time})
            
            # Set expiration
            pipe.expire(key, window)
            
            results = pipe.execute()
            current_requests = results[1]
            
            return {
                'allowed': current_requests < limit,
                'current': current_requests,
                'limit': limit,
                'reset_time': int(current_time + window)
            }
        except RedisError:
            return {'allowed': True, 'current': 0, 'limit': limit, 'reset_time': 0}
    
    def cache_slow_query(self, query: str, execution_time: float, 
                        params: Dict = None) -> bool:
        """Track slow queries for optimization"""
        if execution_time < 1.0:  # Only cache queries slower than 1 second
            return False
            
        date_key = datetime.now().strftime('%Y-%m-%d')
        key = CacheKeyPatterns.SLOW_QUERY_LOG.format(date=date_key)
        
        try:
            query_data = {
                'query': query,
                'execution_time': execution_time,
                'params': params or {},
                'timestamp': datetime.now().isoformat()
            }
            
            # Add to sorted set with execution time as score
            self.redis.zadd(key, {self._serialize(query_data): execution_time})
            
            # Keep only top 100 slowest queries per day
            self.redis.zremrangebyrank(key, 0, -101)
            
            # Set expiration to 7 days
            self.redis.expire(key, 604800)
            
            return True
        except RedisError:
            return False
    
    # =====================================================================
    # UTILITY METHODS
    # =====================================================================
    
    def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching a pattern"""
        try:
            keys = self.redis.keys(pattern)
            if keys:
                return self.redis.delete(*keys)
            return 0
        except RedisError:
            return 0
    
    def invalidate_user_cache(self, user_id: int) -> int:
        """Invalidate all cache entries for a user"""
        patterns = [
            f"user:*:{user_id}*",
            f"auth:session:*{user_id}*",
            f"analytics:dashboard:*:{user_id}:*"
        ]
        
        total_deleted = 0
        for pattern in patterns:
            total_deleted += self.invalidate_pattern(pattern)
        
        return total_deleted
    
    def invalidate_org_cache(self, org_id: int) -> int:
        """Invalidate all cache entries for an organization"""
        patterns = [
            f"org:*:{org_id}*",
            f"material:*:{org_id}:*",
            f"supplier:*:{org_id}:*",
            f"rfq:*:{org_id}:*",
            f"quote:*:{org_id}:*"
        ]
        
        total_deleted = 0
        for pattern in patterns:
            total_deleted += self.invalidate_pattern(pattern)
        
        return total_deleted
    
    def get_cache_stats(self) -> Dict:
        """Get Redis cache statistics"""
        try:
            info = self.redis.info()
            return {
                'used_memory': info.get('used_memory_human'),
                'connected_clients': info.get('connected_clients'),
                'total_commands_processed': info.get('total_commands_processed'),
                'keyspace_hits': info.get('keyspace_hits'),
                'keyspace_misses': info.get('keyspace_misses'),
                'hit_rate': info.get('keyspace_hits', 0) / max(
                    info.get('keyspace_hits', 0) + info.get('keyspace_misses', 0), 1
                )
            }
        except RedisError:
            return {}
    
    def health_check(self) -> bool:
        """Check Redis connection health"""
        try:
            return self.redis.ping()
        except RedisError:
            return False


# =====================================================================
# REDIS CONFIGURATION RECOMMENDATIONS
# =====================================================================

REDIS_CONFIG = """
# Redis Configuration for AI Pricing Agent
# Optimized for high performance and data persistence

# Memory Management
maxmemory 4gb
maxmemory-policy allkeys-lru

# Persistence Configuration
save 900 1      # Save if at least 1 key changed in 900 seconds
save 300 10     # Save if at least 10 keys changed in 300 seconds  
save 60 10000   # Save if at least 10000 keys changed in 60 seconds

# AOF Configuration for better durability
appendonly yes
appendfsync everysec
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb

# Network and Connection Settings
timeout 300
tcp-keepalive 300
tcp-backlog 511

# Performance Settings
databases 16
hash-max-ziplist-entries 512
hash-max-ziplist-value 64
list-max-ziplist-size -2
set-max-intset-entries 512
zset-max-ziplist-entries 128
zset-max-ziplist-value 64

# Security Settings
requirepass your_redis_password_here
rename-command FLUSHDB ""
rename-command FLUSHALL ""
rename-command KEYS ""

# Logging
loglevel notice
logfile "/var/log/redis/redis-server.log"

# Client Output Buffer Limits
client-output-buffer-limit normal 0 0 0
client-output-buffer-limit slave 256mb 64mb 60
client-output-buffer-limit pubsub 32mb 8mb 60
"""

# Example usage and integration patterns
if __name__ == "__main__":
    # Initialize cache
    cache = RedisCache(host='localhost', port=6379, password='your_password')
    
    # Example usage patterns
    
    # Cache user session
    user_data = {
        'user_id': 123,
        'org_id': 456,
        'email': 'user@example.com',
        'permissions': ['read_materials', 'create_rfq']
    }
    cache.cache_user_session('session_abc123', user_data)
    
    # Cache latest pricing
    price_data = {
        'price': 150.50,
        'currency': 'USD',
        'supplier_id': 789,
        'recorded_at': datetime.now().isoformat()
    }
    cache.cache_latest_price(456, 101, 789, price_data)
    
    # Rate limiting example
    rate_limit_result = cache.check_rate_limit(123, 'api/pricing', 100, 3600)
    print(f"Rate limit: {rate_limit_result}")
    
    # Get cache statistics
    stats = cache.get_cache_stats()
    print(f"Cache stats: {stats}")