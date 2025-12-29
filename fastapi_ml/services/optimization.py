"""
Performance Optimization Service for ML Models
"""
import asyncio
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime, timedelta
import structlog
import time
from concurrent.futures import ThreadPoolExecutor
import redis.asyncio as redis
import json
from functools import wraps, lru_cache
import hashlib
import pickle

from ..config import settings

logger = structlog.get_logger()


class CacheManager:
    """Intelligent caching for ML predictions and features"""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis_client = redis_client
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'errors': 0
        }
        
        # Cache TTL configurations
        self.cache_ttls = {
            'prediction': settings.PREDICTION_CACHE_TTL,
            'feature': settings.FEATURE_CACHE_TTL,
            'model_metadata': settings.MODEL_CACHE_TTL,
            'batch_result': 3600,  # 1 hour
            'market_data': 1800,   # 30 minutes
        }
    
    def cache_key_hash(self, base_key: str, data: Any) -> str:
        """Generate consistent cache key with hash"""
        data_str = json.dumps(data, sort_keys=True, default=str)
        data_hash = hashlib.md5(data_str.encode()).hexdigest()[:8]
        return f"{base_key}:{data_hash}"
    
    async def get(self, key: str, deserializer: str = 'json') -> Optional[Any]:
        """Get value from cache with deserialization"""
        try:
            cached_value = await self.redis_client.get(key)
            
            if cached_value is None:
                self.cache_stats['misses'] += 1
                return None
            
            self.cache_stats['hits'] += 1
            
            if deserializer == 'json':
                return json.loads(cached_value)
            elif deserializer == 'pickle':
                return pickle.loads(cached_value)
            else:
                return cached_value
                
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            self.cache_stats['errors'] += 1
            return None
    
    async def set(self, 
                  key: str, 
                  value: Any, 
                  ttl: Optional[int] = None,
                  serializer: str = 'json'):
        """Set value in cache with serialization"""
        try:
            if serializer == 'json':
                serialized_value = json.dumps(value, default=str)
            elif serializer == 'pickle':
                serialized_value = pickle.dumps(value)
            else:
                serialized_value = str(value)
            
            if ttl:
                await self.redis_client.setex(key, ttl, serialized_value)
            else:
                await self.redis_client.set(key, serialized_value)
            
            self.cache_stats['sets'] += 1
            
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            self.cache_stats['errors'] += 1
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        try:
            result = await self.redis_client.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics"""
        total_requests = self.cache_stats['hits'] + self.cache_stats['misses']
        hit_rate = self.cache_stats['hits'] / total_requests if total_requests > 0 else 0
        
        return {
            **self.cache_stats,
            'hit_rate': hit_rate,
            'total_requests': total_requests
        }
    
    def cache_decorator(self, cache_type: str, ttl: Optional[int] = None):
        """Decorator for caching function results"""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Create cache key from function name and arguments
                cache_key = self.cache_key_hash(
                    f"{cache_type}:{func.__name__}",
                    {'args': args, 'kwargs': kwargs}
                )
                
                # Try to get from cache
                cached_result = await self.get(cache_key)
                if cached_result is not None:
                    return cached_result
                
                # Execute function
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                # Cache result
                cache_ttl = ttl or self.cache_ttls.get(cache_type, 300)
                await self.set(cache_key, result, cache_ttl)
                
                return result
            
            return wrapper
        return decorator


class BatchProcessor:
    """Optimized batch processing for ML predictions"""
    
    def __init__(self, max_batch_size: int = settings.MAX_BATCH_SIZE):
        self.max_batch_size = max_batch_size
        self.processing_stats = {
            'batches_processed': 0,
            'total_items': 0,
            'avg_batch_time': 0,
            'throughput': 0  # items per second
        }
        
        # Thread pool for CPU-bound operations
        self.thread_pool = ThreadPoolExecutor(max_workers=4)
    
    async def process_batch_optimized(self, 
                                    items: List[Any], 
                                    processor_func,
                                    chunk_size: Optional[int] = None) -> List[Any]:
        """Process batch with automatic chunking and optimization"""
        start_time = time.time()
        
        if chunk_size is None:
            chunk_size = min(self.max_batch_size, len(items))
        
        # Split into chunks
        chunks = [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]
        
        # Process chunks concurrently
        semaphore = asyncio.Semaphore(5)  # Limit concurrent chunks
        
        async def process_chunk(chunk):
            async with semaphore:
                if asyncio.iscoroutinefunction(processor_func):
                    return await processor_func(chunk)
                else:
                    # Run CPU-bound function in thread pool
                    loop = asyncio.get_event_loop()
                    return await loop.run_in_executor(self.thread_pool, processor_func, chunk)
        
        # Execute all chunks
        results = await asyncio.gather(*[process_chunk(chunk) for chunk in chunks])
        
        # Flatten results
        flattened_results = []
        for chunk_results in results:
            if isinstance(chunk_results, list):
                flattened_results.extend(chunk_results)
            else:
                flattened_results.append(chunk_results)
        
        # Update statistics
        processing_time = time.time() - start_time
        self.processing_stats['batches_processed'] += 1
        self.processing_stats['total_items'] += len(items)
        self.processing_stats['avg_batch_time'] = (
            (self.processing_stats['avg_batch_time'] * (self.processing_stats['batches_processed'] - 1) + processing_time) /
            self.processing_stats['batches_processed']
        )
        self.processing_stats['throughput'] = len(items) / processing_time if processing_time > 0 else 0
        
        logger.info(
            "Batch processing completed",
            items=len(items),
            chunks=len(chunks),
            processing_time=f"{processing_time:.2f}s",
            throughput=f"{self.processing_stats['throughput']:.1f} items/s"
        )
        
        return flattened_results
    
    async def adaptive_batch_size(self, 
                                historical_times: List[float],
                                target_latency: float = 5.0) -> int:
        """Dynamically adjust batch size based on performance"""
        if not historical_times:
            return self.max_batch_size // 2
        
        avg_time = np.mean(historical_times[-10:])  # Last 10 batches
        
        if avg_time > target_latency:
            # Reduce batch size if too slow
            new_batch_size = max(10, int(self.max_batch_size * 0.8))
        elif avg_time < target_latency * 0.5:
            # Increase batch size if too fast
            new_batch_size = min(self.max_batch_size, int(self.max_batch_size * 1.2))
        else:
            new_batch_size = self.max_batch_size
        
        logger.debug(
            "Adaptive batch size adjustment",
            avg_time=avg_time,
            target_latency=target_latency,
            new_batch_size=new_batch_size
        )
        
        return new_batch_size


class ModelLoadBalancer:
    """Load balancer for multiple model instances"""
    
    def __init__(self):
        self.model_instances = {}
        self.instance_stats = {}
        self.routing_strategy = 'round_robin'  # round_robin, weighted, least_loaded
        self.current_index = 0
    
    def register_model_instance(self, 
                              model_name: str, 
                              instance_id: str, 
                              model_instance: Any,
                              weight: float = 1.0):
        """Register a model instance"""
        if model_name not in self.model_instances:
            self.model_instances[model_name] = {}
            self.instance_stats[model_name] = {}
        
        self.model_instances[model_name][instance_id] = {
            'instance': model_instance,
            'weight': weight,
            'active': True
        }
        
        self.instance_stats[model_name][instance_id] = {
            'requests': 0,
            'total_time': 0,
            'avg_latency': 0,
            'error_count': 0,
            'last_used': datetime.utcnow()
        }
        
        logger.info(
            "Model instance registered",
            model_name=model_name,
            instance_id=instance_id,
            weight=weight
        )
    
    async def get_model_instance(self, model_name: str) -> Tuple[str, Any]:
        """Get optimal model instance based on load balancing strategy"""
        if model_name not in self.model_instances:
            raise ValueError(f"No instances registered for model: {model_name}")
        
        active_instances = {
            iid: info for iid, info in self.model_instances[model_name].items()
            if info['active']
        }
        
        if not active_instances:
            raise ValueError(f"No active instances for model: {model_name}")
        
        if self.routing_strategy == 'round_robin':
            instance_ids = list(active_instances.keys())
            instance_id = instance_ids[self.current_index % len(instance_ids)]
            self.current_index += 1
            
        elif self.routing_strategy == 'weighted':
            weights = [info['weight'] for info in active_instances.values()]
            instance_id = np.random.choice(
                list(active_instances.keys()), 
                p=weights/np.sum(weights)
            )
            
        elif self.routing_strategy == 'least_loaded':
            # Choose instance with lowest average latency
            min_latency = float('inf')
            instance_id = None
            
            for iid, stats in self.instance_stats[model_name].items():
                if iid in active_instances and stats['avg_latency'] < min_latency:
                    min_latency = stats['avg_latency']
                    instance_id = iid
        
        else:
            # Default to first available instance
            instance_id = list(active_instances.keys())[0]
        
        instance_info = active_instances[instance_id]
        return instance_id, instance_info['instance']
    
    async def record_request(self, 
                           model_name: str, 
                           instance_id: str, 
                           latency: float,
                           success: bool = True):
        """Record request statistics for load balancing"""
        if model_name in self.instance_stats and instance_id in self.instance_stats[model_name]:
            stats = self.instance_stats[model_name][instance_id]
            
            stats['requests'] += 1
            stats['total_time'] += latency
            stats['avg_latency'] = stats['total_time'] / stats['requests']
            stats['last_used'] = datetime.utcnow()
            
            if not success:
                stats['error_count'] += 1
                
                # Deactivate instance if error rate too high
                error_rate = stats['error_count'] / stats['requests']
                if error_rate > 0.1:  # 10% error rate threshold
                    self.model_instances[model_name][instance_id]['active'] = False
                    logger.warning(
                        "Model instance deactivated due to high error rate",
                        model_name=model_name,
                        instance_id=instance_id,
                        error_rate=error_rate
                    )
    
    async def get_load_stats(self) -> Dict[str, Any]:
        """Get load balancing statistics"""
        stats = {}
        
        for model_name in self.model_instances:
            model_stats = {
                'total_instances': len(self.model_instances[model_name]),
                'active_instances': sum(
                    1 for info in self.model_instances[model_name].values()
                    if info['active']
                ),
                'instance_details': {}
            }
            
            for instance_id, instance_stats in self.instance_stats[model_name].items():
                model_stats['instance_details'][instance_id] = {
                    'requests': instance_stats['requests'],
                    'avg_latency': instance_stats['avg_latency'],
                    'error_count': instance_stats['error_count'],
                    'active': self.model_instances[model_name][instance_id]['active']
                }
            
            stats[model_name] = model_stats
        
        return stats


class PerformanceOptimizer:
    """Main performance optimization coordinator"""
    
    def __init__(self, redis_client: redis.Redis):
        self.cache_manager = CacheManager(redis_client)
        self.batch_processor = BatchProcessor()
        self.load_balancer = ModelLoadBalancer()
        self.redis_client = redis_client
        
        # Performance metrics
        self.metrics = {
            'total_predictions': 0,
            'cache_hits': 0,
            'avg_response_time': 0,
            'throughput': 0,
            'error_rate': 0
        }
        
        # Optimization settings
        self.optimization_config = {
            'enable_caching': True,
            'enable_batch_optimization': True,
            'enable_load_balancing': True,
            'cache_warming_enabled': True,
            'auto_scaling_enabled': False
        }
    
    async def optimize_prediction_request(self,
                                        model_name: str,
                                        prediction_func,
                                        request_data: Any,
                                        use_cache: bool = True) -> Tuple[Any, Dict[str, Any]]:
        """Optimize single prediction request"""
        start_time = time.time()
        optimization_metadata = {
            'cache_hit': False,
            'load_balanced': False,
            'processing_time': 0,
            'optimizations_applied': []
        }
        
        try:
            # Try cache first if enabled
            if use_cache and self.optimization_config['enable_caching']:
                cache_key = self.cache_manager.cache_key_hash(
                    f"prediction:{model_name}", request_data
                )
                
                cached_result = await self.cache_manager.get(cache_key)
                if cached_result is not None:
                    optimization_metadata['cache_hit'] = True
                    optimization_metadata['optimizations_applied'].append('cache')
                    optimization_metadata['processing_time'] = time.time() - start_time
                    
                    self.metrics['cache_hits'] += 1
                    return cached_result, optimization_metadata
            
            # Use load balancer if enabled
            if self.optimization_config['enable_load_balancing']:
                try:
                    instance_id, model_instance = await self.load_balancer.get_model_instance(model_name)
                    result = await prediction_func(model_instance, request_data)
                    
                    optimization_metadata['load_balanced'] = True
                    optimization_metadata['optimizations_applied'].append('load_balancing')
                    
                    # Record load balancer stats
                    processing_time = time.time() - start_time
                    await self.load_balancer.record_request(
                        model_name, instance_id, processing_time, success=True
                    )
                    
                except ValueError:
                    # Fall back to direct prediction if no load balancer instances
                    result = await prediction_func(None, request_data)
            else:
                result = await prediction_func(None, request_data)
            
            # Cache result if caching enabled
            if use_cache and self.optimization_config['enable_caching']:
                cache_key = self.cache_manager.cache_key_hash(
                    f"prediction:{model_name}", request_data
                )
                await self.cache_manager.set(
                    cache_key, result, self.cache_manager.cache_ttls['prediction']
                )
                optimization_metadata['optimizations_applied'].append('caching')
            
            optimization_metadata['processing_time'] = time.time() - start_time
            self.metrics['total_predictions'] += 1
            
            return result, optimization_metadata
            
        except Exception as e:
            # Record error for load balancer if applicable
            if optimization_metadata['load_balanced']:
                instance_id = 'unknown'  # Would need to track this better
                await self.load_balancer.record_request(
                    model_name, instance_id, time.time() - start_time, success=False
                )
            
            logger.error(f"Prediction optimization failed: {e}")
            raise
    
    async def optimize_batch_predictions(self,
                                       model_name: str,
                                       batch_prediction_func,
                                       batch_data: List[Any],
                                       use_cache: bool = True) -> Tuple[List[Any], Dict[str, Any]]:
        """Optimize batch prediction requests"""
        start_time = time.time()
        optimization_metadata = {
            'batch_size': len(batch_data),
            'cache_hits': 0,
            'batch_optimized': False,
            'processing_time': 0,
            'optimizations_applied': []
        }
        
        try:
            results = []
            uncached_items = []
            cache_map = {}
            
            # Check cache for each item if enabled
            if use_cache and self.optimization_config['enable_caching']:
                for i, item in enumerate(batch_data):
                    cache_key = self.cache_manager.cache_key_hash(
                        f"prediction:{model_name}", item
                    )
                    cached_result = await self.cache_manager.get(cache_key)
                    
                    if cached_result is not None:
                        cache_map[i] = cached_result
                        optimization_metadata['cache_hits'] += 1
                    else:
                        uncached_items.append((i, item))
                
                if optimization_metadata['cache_hits'] > 0:
                    optimization_metadata['optimizations_applied'].append('partial_caching')
            else:
                uncached_items = [(i, item) for i, item in enumerate(batch_data)]
            
            # Process uncached items
            if uncached_items:
                uncached_data = [item for _, item in uncached_items]
                
                if self.optimization_config['enable_batch_optimization']:
                    # Use optimized batch processing
                    batch_results = await self.batch_processor.process_batch_optimized(
                        uncached_data, 
                        lambda batch: batch_prediction_func(batch)
                    )
                    optimization_metadata['batch_optimized'] = True
                    optimization_metadata['optimizations_applied'].append('batch_optimization')
                else:
                    # Process sequentially
                    batch_results = []
                    for item in uncached_data:
                        result = await batch_prediction_func([item])
                        batch_results.extend(result if isinstance(result, list) else [result])
                
                # Cache new results
                if use_cache and self.optimization_config['enable_caching']:
                    for (original_idx, item), result in zip(uncached_items, batch_results):
                        cache_key = self.cache_manager.cache_key_hash(
                            f"prediction:{model_name}", item
                        )
                        await self.cache_manager.set(
                            cache_key, result, self.cache_manager.cache_ttls['prediction']
                        )
                    
                    optimization_metadata['optimizations_applied'].append('result_caching')
                
                # Map results back to original positions
                result_map = {}
                for (original_idx, _), result in zip(uncached_items, batch_results):
                    result_map[original_idx] = result
                
                cache_map.update(result_map)
            
            # Reconstruct results in original order
            results = [cache_map[i] for i in range(len(batch_data))]
            
            optimization_metadata['processing_time'] = time.time() - start_time
            self.metrics['total_predictions'] += len(batch_data)
            self.metrics['cache_hits'] += optimization_metadata['cache_hits']
            
            logger.info(
                "Batch prediction optimized",
                batch_size=len(batch_data),
                cache_hits=optimization_metadata['cache_hits'],
                processing_time=f"{optimization_metadata['processing_time']:.2f}s",
                optimizations=optimization_metadata['optimizations_applied']
            )
            
            return results, optimization_metadata
            
        except Exception as e:
            logger.error(f"Batch prediction optimization failed: {e}")
            raise
    
    async def warm_cache(self, model_name: str, common_requests: List[Any]):
        """Pre-populate cache with common requests"""
        if not self.optimization_config['cache_warming_enabled']:
            return
        
        logger.info(f"Warming cache for {model_name} with {len(common_requests)} requests")
        
        # This would typically predict common requests and cache results
        # Implementation depends on your specific use case
        for request in common_requests:
            cache_key = self.cache_manager.cache_key_hash(
                f"prediction:{model_name}", request
            )
            
            # Check if already cached
            if await self.cache_manager.get(cache_key) is None:
                # Would make actual prediction here and cache result
                # For now, just mark as warmed
                placeholder_result = {"warmed": True, "timestamp": datetime.utcnow().isoformat()}
                await self.cache_manager.set(
                    cache_key, placeholder_result, self.cache_manager.cache_ttls['prediction']
                )
    
    async def get_optimization_metrics(self) -> Dict[str, Any]:
        """Get comprehensive optimization metrics"""
        cache_stats = await self.cache_manager.get_stats()
        load_balancer_stats = await self.load_balancer.get_load_stats()
        
        total_requests = self.metrics['total_predictions']
        cache_hit_rate = self.metrics['cache_hits'] / total_requests if total_requests > 0 else 0
        
        return {
            'overall_metrics': {
                'total_predictions': self.metrics['total_predictions'],
                'cache_hit_rate': cache_hit_rate,
                'avg_response_time': self.metrics['avg_response_time'],
                'throughput': self.batch_processor.processing_stats['throughput']
            },
            'cache_metrics': cache_stats,
            'batch_processing_metrics': self.batch_processor.processing_stats,
            'load_balancer_metrics': load_balancer_stats,
            'optimization_config': self.optimization_config
        }
    
    async def auto_tune_performance(self):
        """Automatically tune performance settings based on metrics"""
        metrics = await self.get_optimization_metrics()
        
        # Adjust cache TTL based on hit rate
        cache_hit_rate = metrics['overall_metrics']['cache_hit_rate']
        if cache_hit_rate < 0.3:
            # Low hit rate, increase TTL
            for cache_type in self.cache_manager.cache_ttls:
                self.cache_manager.cache_ttls[cache_type] = int(
                    self.cache_manager.cache_ttls[cache_type] * 1.2
                )
            logger.info("Increased cache TTL due to low hit rate")
        
        elif cache_hit_rate > 0.8:
            # High hit rate, can afford to reduce TTL for fresher data
            for cache_type in self.cache_manager.cache_ttls:
                self.cache_manager.cache_ttls[cache_type] = int(
                    self.cache_manager.cache_ttls[cache_type] * 0.9
                )
            logger.info("Decreased cache TTL due to high hit rate")
        
        # Adjust batch size based on throughput
        throughput = metrics['batch_processing_metrics']['throughput']
        if throughput < 50:  # items per second
            # Reduce batch size for better latency
            self.batch_processor.max_batch_size = max(
                10, int(self.batch_processor.max_batch_size * 0.8)
            )
            logger.info("Reduced batch size to improve latency")
        
        elif throughput > 200:
            # Increase batch size for better throughput
            self.batch_processor.max_batch_size = min(
                settings.MAX_BATCH_SIZE,
                int(self.batch_processor.max_batch_size * 1.1)
            )
            logger.info("Increased batch size to improve throughput")
    
    async def enable_optimization(self, optimization_type: str, enabled: bool = True):
        """Enable or disable specific optimizations"""
        if optimization_type in self.optimization_config:
            self.optimization_config[optimization_type] = enabled
            logger.info(f"Optimization {optimization_type} {'enabled' if enabled else 'disabled'}")
        else:
            logger.warning(f"Unknown optimization type: {optimization_type}")
    
    async def clear_cache(self, pattern: Optional[str] = None):
        """Clear cache entries matching pattern"""
        try:
            if pattern:
                keys = await self.redis_client.keys(pattern)
                if keys:
                    await self.redis_client.delete(*keys)
                    logger.info(f"Cleared {len(keys)} cache entries matching pattern: {pattern}")
            else:
                await self.redis_client.flushdb()
                logger.info("Cleared entire cache")
                
            # Reset cache stats
            self.cache_manager.cache_stats = {
                'hits': 0,
                'misses': 0,
                'sets': 0,
                'errors': 0
            }
            
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")