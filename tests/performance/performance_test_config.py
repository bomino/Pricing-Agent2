"""
Performance test configuration and utilities.
"""
import os
import json
import time
import psutil
import requests
from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime


@dataclass
class PerformanceThresholds:
    """Performance test thresholds."""
    max_response_time_ms: int = 200
    max_95th_percentile_ms: int = 500
    max_error_rate_percent: float = 1.0
    min_throughput_rps: float = 50.0
    max_cpu_percent: float = 80.0
    max_memory_mb: int = 1024


@dataclass
class TestScenario:
    """Performance test scenario configuration."""
    name: str
    description: str
    users: int
    spawn_rate: int
    run_time_seconds: int
    host: str
    user_classes: List[str]
    weight_distribution: Optional[Dict[str, int]] = None


class PerformanceTestConfig:
    """Configuration for performance tests."""
    
    # Test scenarios
    SCENARIOS = {
        "smoke": TestScenario(
            name="Smoke Test",
            description="Basic functionality test with minimal load",
            users=5,
            spawn_rate=1,
            run_time_seconds=60,
            host="http://localhost:8000",
            user_classes=["DjangoAPIUser"]
        ),
        
        "load": TestScenario(
            name="Load Test",
            description="Normal load test with expected user volume",
            users=50,
            spawn_rate=5,
            run_time_seconds=300,
            host="http://localhost:8000",
            user_classes=["LightLoad", "NormalLoad", "HeavyLoad"],
            weight_distribution={"LightLoad": 3, "NormalLoad": 5, "HeavyLoad": 2}
        ),
        
        "stress": TestScenario(
            name="Stress Test",
            description="High load test to find breaking points",
            users=200,
            spawn_rate=10,
            run_time_seconds=600,
            host="http://localhost:8000",
            user_classes=["NormalLoad", "HeavyLoad", "SpikeLoad"],
            weight_distribution={"NormalLoad": 3, "HeavyLoad": 5, "SpikeLoad": 2}
        ),
        
        "spike": TestScenario(
            name="Spike Test",
            description="Sudden load increase test",
            users=100,
            spawn_rate=50,  # Rapid spawn
            run_time_seconds=300,
            host="http://localhost:8000",
            user_classes=["SpikeLoad"]
        ),
        
        "volume": TestScenario(
            name="Volume Test",
            description="Large data volume processing test",
            users=30,
            spawn_rate=3,
            run_time_seconds=900,
            host="http://localhost:8000",
            user_classes=["DatabaseLoadUser"]
        ),
        
        "ml_service": TestScenario(
            name="ML Service Test",
            description="ML prediction service performance test",
            users=20,
            spawn_rate=2,
            run_time_seconds=300,
            host="http://localhost:8001",
            user_classes=["MLServiceUser"]
        ),
        
        "endurance": TestScenario(
            name="Endurance Test",
            description="Long-running test for memory leaks and stability",
            users=25,
            spawn_rate=1,
            run_time_seconds=3600,  # 1 hour
            host="http://localhost:8000",
            user_classes=["LightLoad", "NormalLoad"],
            weight_distribution={"LightLoad": 7, "NormalLoad": 3}
        )
    }
    
    # Performance thresholds by scenario
    THRESHOLDS = {
        "smoke": PerformanceThresholds(
            max_response_time_ms=500,
            max_95th_percentile_ms=1000,
            max_error_rate_percent=0.0,
            min_throughput_rps=10.0
        ),
        
        "load": PerformanceThresholds(
            max_response_time_ms=200,
            max_95th_percentile_ms=500,
            max_error_rate_percent=1.0,
            min_throughput_rps=50.0,
            max_cpu_percent=70.0,
            max_memory_mb=1024
        ),
        
        "stress": PerformanceThresholds(
            max_response_time_ms=1000,
            max_95th_percentile_ms=2000,
            max_error_rate_percent=5.0,
            min_throughput_rps=30.0,
            max_cpu_percent=90.0,
            max_memory_mb=2048
        ),
        
        "spike": PerformanceThresholds(
            max_response_time_ms=2000,
            max_95th_percentile_ms=5000,
            max_error_rate_percent=10.0,
            min_throughput_rps=20.0,
            max_cpu_percent=95.0
        ),
        
        "volume": PerformanceThresholds(
            max_response_time_ms=1000,
            max_95th_percentile_ms=3000,
            max_error_rate_percent=2.0,
            min_throughput_rps=10.0,
            max_memory_mb=3072
        ),
        
        "ml_service": PerformanceThresholds(
            max_response_time_ms=500,
            max_95th_percentile_ms=1000,
            max_error_rate_percent=0.5,
            min_throughput_rps=20.0,
            max_cpu_percent=85.0,
            max_memory_mb=2048
        ),
        
        "endurance": PerformanceThresholds(
            max_response_time_ms=300,
            max_95th_percentile_ms=800,
            max_error_rate_percent=1.5,
            min_throughput_rps=20.0,
            max_cpu_percent=60.0,
            max_memory_mb=1536
        )
    }


class SystemMonitor:
    """Monitor system resources during performance tests."""
    
    def __init__(self):
        self.monitoring = False
        self.metrics = []
        self.processes = []
    
    def start_monitoring(self, processes_to_monitor: List[str] = None):
        """Start monitoring system resources."""
        self.monitoring = True
        self.processes = processes_to_monitor or ["python", "postgres", "redis-server", "nginx"]
        
        print("Starting system monitoring...")
        self._monitor_loop()
    
    def stop_monitoring(self):
        """Stop monitoring and return collected metrics."""
        self.monitoring = False
        return self.metrics
    
    def _monitor_loop(self):
        """Monitor system resources in a loop."""
        while self.monitoring:
            timestamp = datetime.now()
            
            # System-wide metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Network metrics
            network = psutil.net_io_counters()
            
            metric = {
                'timestamp': timestamp.isoformat(),
                'system': {
                    'cpu_percent': cpu_percent,
                    'memory_percent': memory.percent,
                    'memory_used_mb': memory.used / (1024 * 1024),
                    'memory_available_mb': memory.available / (1024 * 1024),
                    'disk_percent': (disk.used / disk.total) * 100,
                    'network_bytes_sent': network.bytes_sent,
                    'network_bytes_recv': network.bytes_recv
                },
                'processes': {}
            }
            
            # Process-specific metrics
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info']):
                try:
                    if any(process_name in proc.info['name'] for process_name in self.processes):
                        metric['processes'][proc.info['name']] = {
                            'pid': proc.info['pid'],
                            'cpu_percent': proc.info['cpu_percent'],
                            'memory_mb': proc.info['memory_info'].rss / (1024 * 1024)
                        }
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            self.metrics.append(metric)
            time.sleep(5)  # Monitor every 5 seconds
    
    def save_metrics(self, filename: str):
        """Save collected metrics to file."""
        with open(filename, 'w') as f:
            json.dump(self.metrics, f, indent=2)
        
        print(f"System metrics saved to {filename}")


class PerformanceTestRunner:
    """Run and manage performance tests."""
    
    def __init__(self):
        self.config = PerformanceTestConfig()
        self.monitor = SystemMonitor()
    
    def run_scenario(self, scenario_name: str, output_dir: str = "test_results"):
        """Run a specific test scenario."""
        if scenario_name not in self.config.SCENARIOS:
            raise ValueError(f"Unknown scenario: {scenario_name}")
        
        scenario = self.config.SCENARIOS[scenario_name]
        thresholds = self.config.THRESHOLDS[scenario_name]
        
        print(f"Running {scenario.name}...")
        print(f"Description: {scenario.description}")
        print(f"Configuration: {scenario.users} users, {scenario.spawn_rate} spawn rate, {scenario.run_time_seconds}s duration")
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Start system monitoring
        self.monitor.start_monitoring()
        
        # Build locust command
        cmd = self._build_locust_command(scenario, output_dir)
        
        try:
            # Run the test
            print(f"Executing: {cmd}")
            result = os.system(cmd)
            
            if result == 0:
                print("Performance test completed successfully")
            else:
                print("Performance test failed")
        
        finally:
            # Stop monitoring and save metrics
            metrics = self.monitor.stop_monitoring()
            metrics_file = os.path.join(output_dir, f"{scenario_name}_system_metrics.json")
            self.monitor.save_metrics(metrics_file)
        
        # Analyze results
        self._analyze_results(scenario_name, output_dir, thresholds)
    
    def _build_locust_command(self, scenario: TestScenario, output_dir: str) -> str:
        """Build locust command line."""
        cmd_parts = [
            "locust",
            "-f", "tests/performance/locustfile.py",
            "--host", scenario.host,
            "--users", str(scenario.users),
            "--spawn-rate", str(scenario.spawn_rate),
            "--run-time", f"{scenario.run_time_seconds}s",
            "--headless",
            "--html", os.path.join(output_dir, f"{scenario.name.lower().replace(' ', '_')}_report.html"),
            "--csv", os.path.join(output_dir, f"{scenario.name.lower().replace(' ', '_')}")
        ]
        
        return " ".join(cmd_parts)
    
    def _analyze_results(self, scenario_name: str, output_dir: str, thresholds: PerformanceThresholds):
        """Analyze test results against thresholds."""
        print("\n" + "="*50)
        print(f"PERFORMANCE ANALYSIS: {scenario_name.upper()}")
        print("="*50)
        
        # Load CSV results (simplified analysis)
        stats_file = os.path.join(output_dir, f"{scenario_name.lower().replace(' ', '_')}_stats.csv")
        
        if os.path.exists(stats_file):
            with open(stats_file, 'r') as f:
                lines = f.readlines()
                if len(lines) > 1:  # Has data
                    # Parse the aggregated stats line
                    stats_line = lines[-1]  # Last line is usually the aggregate
                    print(f"Results file found: {stats_file}")
                    # Add detailed analysis here
        
        print("\nThreshold Analysis:")
        print(f"Max Response Time: {thresholds.max_response_time_ms}ms")
        print(f"Max 95th Percentile: {thresholds.max_95th_percentile_ms}ms")
        print(f"Max Error Rate: {thresholds.max_error_rate_percent}%")
        print(f"Min Throughput: {thresholds.min_throughput_rps} RPS")
        
        # Load system metrics for analysis
        metrics_file = os.path.join(output_dir, f"{scenario_name}_system_metrics.json")
        if os.path.exists(metrics_file):
            with open(metrics_file, 'r') as f:
                metrics = json.load(f)
                
            if metrics:
                # Analyze CPU usage
                cpu_values = [m['system']['cpu_percent'] for m in metrics]
                max_cpu = max(cpu_values)
                avg_cpu = sum(cpu_values) / len(cpu_values)
                
                print(f"\nSystem Resource Analysis:")
                print(f"Max CPU Usage: {max_cpu:.1f}% (threshold: {thresholds.max_cpu_percent}%)")
                print(f"Avg CPU Usage: {avg_cpu:.1f}%")
                
                # Analyze memory usage
                memory_values = [m['system']['memory_used_mb'] for m in metrics]
                max_memory = max(memory_values)
                avg_memory = sum(memory_values) / len(memory_values)
                
                print(f"Max Memory Usage: {max_memory:.1f}MB (threshold: {thresholds.max_memory_mb}MB)")
                print(f"Avg Memory Usage: {avg_memory:.1f}MB")
                
                # Check thresholds
                issues = []
                if max_cpu > thresholds.max_cpu_percent:
                    issues.append(f"CPU usage exceeded threshold: {max_cpu:.1f}% > {thresholds.max_cpu_percent}%")
                
                if max_memory > thresholds.max_memory_mb:
                    issues.append(f"Memory usage exceeded threshold: {max_memory:.1f}MB > {thresholds.max_memory_mb}MB")
                
                if issues:
                    print(f"\n❌ PERFORMANCE ISSUES DETECTED:")
                    for issue in issues:
                        print(f"  - {issue}")
                else:
                    print(f"\n✅ ALL SYSTEM THRESHOLDS PASSED")
    
    def run_all_scenarios(self):
        """Run all defined test scenarios."""
        for scenario_name in self.config.SCENARIOS.keys():
            print(f"\n{'='*60}")
            print(f"RUNNING SCENARIO: {scenario_name.upper()}")
            print(f"{'='*60}")
            
            try:
                self.run_scenario(scenario_name)
            except Exception as e:
                print(f"Error running scenario {scenario_name}: {e}")
                continue
    
    def create_custom_scenario(self, name: str, users: int, spawn_rate: int, 
                             run_time: int, host: str, user_classes: List[str]):
        """Create a custom test scenario."""
        scenario = TestScenario(
            name=name,
            description=f"Custom scenario: {name}",
            users=users,
            spawn_rate=spawn_rate,
            run_time_seconds=run_time,
            host=host,
            user_classes=user_classes
        )
        
        self.config.SCENARIOS[name] = scenario
        
        # Create default thresholds
        self.config.THRESHOLDS[name] = PerformanceThresholds()
        
        print(f"Custom scenario '{name}' created successfully")


def main():
    """Main function for running performance tests."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run performance tests")
    parser.add_argument("--scenario", help="Specific scenario to run")
    parser.add_argument("--list", action="store_true", help="List available scenarios")
    parser.add_argument("--all", action="store_true", help="Run all scenarios")
    parser.add_argument("--output-dir", default="test_results", help="Output directory for results")
    
    args = parser.parse_args()
    
    runner = PerformanceTestRunner()
    
    if args.list:
        print("Available scenarios:")
        for name, scenario in runner.config.SCENARIOS.items():
            print(f"  {name}: {scenario.description}")
        return
    
    if args.all:
        runner.run_all_scenarios()
    elif args.scenario:
        runner.run_scenario(args.scenario, args.output_dir)
    else:
        print("Please specify --scenario, --all, or --list")


if __name__ == "__main__":
    main()