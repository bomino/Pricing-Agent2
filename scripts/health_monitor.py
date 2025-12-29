#!/usr/bin/env python3
"""
Health monitoring script for the Pricing Agent system.
Performs comprehensive health checks and reports status.
"""

import argparse
import asyncio
import json
import logging
import time
import sys
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import aiohttp
import psutil
from prometheus_client.parser import text_string_to_metric_families


@dataclass
class HealthCheck:
    """Represents a health check result"""
    name: str
    status: str  # 'healthy', 'unhealthy', 'warning'
    message: str
    response_time: float
    timestamp: str
    details: Optional[Dict[str, Any]] = None


@dataclass
class SystemMetrics:
    """System-level metrics"""
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    network_connections: int
    uptime_seconds: float


class HealthMonitor:
    """Health monitoring system for Pricing Agent"""
    
    def __init__(self, base_url: str, environment: str, timeout: int = 30):
        self.base_url = base_url.rstrip('/')
        self.environment = environment
        self.timeout = timeout
        self.session: Optional[aiohttp.ClientSession] = None
        self.logger = logging.getLogger(__name__)
        
    async def __aenter__(self):
        """Async context manager entry"""
        connector = aiohttp.TCPConnector(limit_per_host=10, limit=100)
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        self.session = aiohttp.ClientSession(connector=connector, timeout=timeout)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()

    async def check_endpoint(self, endpoint: str, expected_status: int = 200) -> HealthCheck:
        """Check a single HTTP endpoint"""
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()
        
        try:
            async with self.session.get(url) as response:
                response_time = time.time() - start_time
                
                if response.status == expected_status:
                    try:
                        data = await response.json()
                        return HealthCheck(
                            name=f"endpoint_{endpoint.replace('/', '_')}",
                            status='healthy',
                            message=f'Endpoint {endpoint} is responding correctly',
                            response_time=response_time,
                            timestamp=datetime.now(timezone.utc).isoformat(),
                            details=data if isinstance(data, dict) else None
                        )
                    except json.JSONDecodeError:
                        text = await response.text()
                        return HealthCheck(
                            name=f"endpoint_{endpoint.replace('/', '_')}",
                            status='healthy',
                            message=f'Endpoint {endpoint} is responding (non-JSON)',
                            response_time=response_time,
                            timestamp=datetime.now(timezone.utc).isoformat(),
                            details={'response_text': text[:200]}
                        )
                else:
                    return HealthCheck(
                        name=f"endpoint_{endpoint.replace('/', '_')}",
                        status='unhealthy',
                        message=f'Endpoint {endpoint} returned status {response.status}',
                        response_time=response_time,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        details={'status_code': response.status}
                    )
                    
        except asyncio.TimeoutError:
            response_time = time.time() - start_time
            return HealthCheck(
                name=f"endpoint_{endpoint.replace('/', '_')}",
                status='unhealthy',
                message=f'Endpoint {endpoint} timed out',
                response_time=response_time,
                timestamp=datetime.now(timezone.utc).isoformat(),
                details={'error': 'timeout'}
            )
        except Exception as e:
            response_time = time.time() - start_time
            return HealthCheck(
                name=f"endpoint_{endpoint.replace('/', '_')}",
                status='unhealthy',
                message=f'Endpoint {endpoint} error: {str(e)}',
                response_time=response_time,
                timestamp=datetime.now(timezone.utc).isoformat(),
                details={'error': str(e)}
            )

    async def check_django_health(self) -> List[HealthCheck]:
        """Check Django application health"""
        checks = []
        
        # Basic health endpoint
        checks.append(await self.check_endpoint('/health/'))
        
        # API health
        checks.append(await self.check_endpoint('/api/v1/'))
        
        # Admin health (might be restricted)
        admin_check = await self.check_endpoint('/admin/', expected_status=302)
        if admin_check.status == 'unhealthy' and 'status_code' in admin_check.details:
            if admin_check.details['status_code'] == 302:
                admin_check.status = 'healthy'
                admin_check.message = 'Admin endpoint is accessible (redirect to login)'
        checks.append(admin_check)
        
        return checks

    async def check_fastapi_health(self) -> List[HealthCheck]:
        """Check FastAPI ML service health"""
        checks = []
        
        # Health endpoint
        checks.append(await self.check_endpoint('/ml/health'))
        
        # Ready endpoint
        checks.append(await self.check_endpoint('/ml/ready'))
        
        # API docs (if available)
        docs_check = await self.check_endpoint('/ml/docs')
        if docs_check.status == 'unhealthy' and 'status_code' in docs_check.details:
            if docs_check.details['status_code'] == 404:
                docs_check.status = 'warning'
                docs_check.message = 'API docs not available (likely disabled in production)'
        checks.append(docs_check)
        
        # Metrics endpoint
        checks.append(await self.check_endpoint('/ml/metrics'))
        
        return checks

    async def check_prometheus_metrics(self) -> List[HealthCheck]:
        """Check Prometheus metrics availability"""
        checks = []
        
        # Try to get metrics from various endpoints
        metrics_endpoints = ['/metrics', '/ml/metrics']
        
        for endpoint in metrics_endpoints:
            try:
                url = f"{self.base_url}{endpoint}"
                start_time = time.time()
                
                async with self.session.get(url) as response:
                    response_time = time.time() - start_time
                    
                    if response.status == 200:
                        text = await response.text()
                        
                        # Parse Prometheus metrics
                        try:
                            metrics = list(text_string_to_metric_families(text))
                            metric_count = len(metrics)
                            
                            checks.append(HealthCheck(
                                name=f"prometheus_metrics_{endpoint.replace('/', '_')}",
                                status='healthy',
                                message=f'Metrics available with {metric_count} metric families',
                                response_time=response_time,
                                timestamp=datetime.now(timezone.utc).isoformat(),
                                details={'metric_families': metric_count}
                            ))
                        except Exception as e:
                            checks.append(HealthCheck(
                                name=f"prometheus_metrics_{endpoint.replace('/', '_')}",
                                status='warning',
                                message=f'Metrics endpoint responding but parsing failed: {str(e)}',
                                response_time=response_time,
                                timestamp=datetime.now(timezone.utc).isoformat(),
                                details={'parse_error': str(e)}
                            ))
                    else:
                        checks.append(HealthCheck(
                            name=f"prometheus_metrics_{endpoint.replace('/', '_')}",
                            status='unhealthy',
                            message=f'Metrics endpoint returned status {response.status}',
                            response_time=time.time() - start_time,
                            timestamp=datetime.now(timezone.utc).isoformat(),
                            details={'status_code': response.status}
                        ))
                        
            except Exception as e:
                checks.append(HealthCheck(
                    name=f"prometheus_metrics_{endpoint.replace('/', '_')}",
                    status='unhealthy',
                    message=f'Metrics endpoint error: {str(e)}',
                    response_time=0.0,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    details={'error': str(e)}
                ))
        
        return checks

    def get_system_metrics(self) -> SystemMetrics:
        """Get system-level metrics"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Disk usage (root partition)
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            
            # Network connections
            connections = len(psutil.net_connections())
            
            # System uptime
            boot_time = psutil.boot_time()
            uptime_seconds = time.time() - boot_time
            
            return SystemMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                disk_percent=disk_percent,
                network_connections=connections,
                uptime_seconds=uptime_seconds
            )
        except Exception as e:
            self.logger.warning(f"Failed to get system metrics: {e}")
            return SystemMetrics(
                cpu_percent=0.0,
                memory_percent=0.0,
                disk_percent=0.0,
                network_connections=0,
                uptime_seconds=0.0
            )

    async def check_database_connectivity(self) -> HealthCheck:
        """Check database connectivity through the application"""
        # This would typically check a database status endpoint
        return await self.check_endpoint('/health/database')

    async def check_redis_connectivity(self) -> HealthCheck:
        """Check Redis connectivity through the application"""
        return await self.check_endpoint('/health/redis')

    async def check_celery_workers(self) -> HealthCheck:
        """Check Celery worker status"""
        return await self.check_endpoint('/health/celery')

    async def run_comprehensive_health_check(self) -> Dict[str, Any]:
        """Run all health checks"""
        start_time = time.time()
        all_checks = []
        
        self.logger.info("Starting comprehensive health check...")
        
        try:
            # Django health checks
            django_checks = await self.check_django_health()
            all_checks.extend(django_checks)
            
            # FastAPI health checks
            fastapi_checks = await self.check_fastapi_health()
            all_checks.extend(fastapi_checks)
            
            # Prometheus metrics
            metrics_checks = await self.check_prometheus_metrics()
            all_checks.extend(metrics_checks)
            
            # Infrastructure checks
            db_check = await self.check_database_connectivity()
            all_checks.append(db_check)
            
            redis_check = await self.check_redis_connectivity()
            all_checks.append(redis_check)
            
            celery_check = await self.check_celery_workers()
            all_checks.append(celery_check)
            
        except Exception as e:
            self.logger.error(f"Error during health checks: {e}")
            all_checks.append(HealthCheck(
                name="health_check_error",
                status='unhealthy',
                message=f"Health check process error: {str(e)}",
                response_time=0.0,
                timestamp=datetime.now(timezone.utc).isoformat(),
                details={'error': str(e)}
            ))
        
        # Get system metrics
        system_metrics = self.get_system_metrics()
        
        # Calculate overall health
        healthy_count = sum(1 for check in all_checks if check.status == 'healthy')
        warning_count = sum(1 for check in all_checks if check.status == 'warning')
        unhealthy_count = sum(1 for check in all_checks if check.status == 'unhealthy')
        total_checks = len(all_checks)
        
        if unhealthy_count > 0:
            overall_status = 'unhealthy'
        elif warning_count > 0:
            overall_status = 'warning'
        else:
            overall_status = 'healthy'
        
        health_score = (healthy_count / total_checks * 100) if total_checks > 0 else 0
        
        total_time = time.time() - start_time
        
        return {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'environment': self.environment,
            'base_url': self.base_url,
            'overall_status': overall_status,
            'health_score': round(health_score, 2),
            'summary': {
                'total_checks': total_checks,
                'healthy': healthy_count,
                'warning': warning_count,
                'unhealthy': unhealthy_count
            },
            'checks': [asdict(check) for check in all_checks],
            'system_metrics': asdict(system_metrics),
            'execution_time': round(total_time, 2)
        }


def setup_logging(verbose: bool = False):
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )


async def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description='Health monitoring for Pricing Agent system'
    )
    parser.add_argument(
        '--url', 
        required=True, 
        help='Base URL of the application'
    )
    parser.add_argument(
        '--environment', 
        required=True, 
        choices=['staging', 'production', 'development'],
        help='Environment name'
    )
    parser.add_argument(
        '--timeout', 
        type=int, 
        default=30, 
        help='Request timeout in seconds'
    )
    parser.add_argument(
        '--output-format', 
        choices=['json', 'text'], 
        default='text',
        help='Output format'
    )
    parser.add_argument(
        '--output-file', 
        help='Output file path (default: stdout)'
    )
    parser.add_argument(
        '--verbose', 
        action='store_true', 
        help='Enable verbose logging'
    )
    parser.add_argument(
        '--fail-on-unhealthy', 
        action='store_true',
        help='Exit with non-zero code if any check is unhealthy'
    )
    
    args = parser.parse_args()
    
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    try:
        async with HealthMonitor(args.url, args.environment, args.timeout) as monitor:
            result = await monitor.run_comprehensive_health_check()
            
            # Format output
            if args.output_format == 'json':
                output = json.dumps(result, indent=2)
            else:
                # Text format
                lines = [
                    f"Health Check Report - {args.environment.upper()}",
                    f"Timestamp: {result['timestamp']}",
                    f"Base URL: {result['base_url']}",
                    f"Overall Status: {result['overall_status'].upper()}",
                    f"Health Score: {result['health_score']}%",
                    "",
                    "Summary:",
                    f"  Total Checks: {result['summary']['total_checks']}",
                    f"  Healthy: {result['summary']['healthy']}",
                    f"  Warning: {result['summary']['warning']}",
                    f"  Unhealthy: {result['summary']['unhealthy']}",
                    "",
                    "System Metrics:",
                    f"  CPU Usage: {result['system_metrics']['cpu_percent']:.1f}%",
                    f"  Memory Usage: {result['system_metrics']['memory_percent']:.1f}%",
                    f"  Disk Usage: {result['system_metrics']['disk_percent']:.1f}%",
                    f"  Network Connections: {result['system_metrics']['network_connections']}",
                    f"  Uptime: {result['system_metrics']['uptime_seconds']:.0f}s",
                    "",
                    "Detailed Results:"
                ]
                
                for check in result['checks']:
                    status_symbol = "✓" if check['status'] == 'healthy' else "⚠" if check['status'] == 'warning' else "✗"
                    lines.append(
                        f"  {status_symbol} {check['name']}: {check['message']} "
                        f"({check['response_time']:.3f}s)"
                    )
                
                lines.append(f"\nExecution Time: {result['execution_time']}s")
                output = "\n".join(lines)
            
            # Write output
            if args.output_file:
                with open(args.output_file, 'w') as f:
                    f.write(output)
                logger.info(f"Health check results written to {args.output_file}")
            else:
                print(output)
            
            # Exit with error code if requested and unhealthy
            if args.fail_on_unhealthy and result['overall_status'] == 'unhealthy':
                logger.error("Health check failed - exiting with error code")
                sys.exit(1)
                
    except KeyboardInterrupt:
        logger.info("Health check interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Health check failed with error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())