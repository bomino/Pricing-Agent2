"""
Gunicorn configuration for FastAPI ML Service
"""

import multiprocessing
import os

# Server socket
bind = "0.0.0.0:8001"
backlog = 2048

# Worker processes - fewer for ML service to preserve memory
workers = max(1, multiprocessing.cpu_count())
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
max_requests = 500  # Lower for ML service
max_requests_jitter = 50
preload_app = True
timeout = 120  # Longer timeout for ML predictions
keepalive = 2

# Memory management for ML models
max_requests = 500  # Restart workers more frequently to prevent memory leaks
max_requests_jitter = 50

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Logging
accesslog = "/app/logs/gunicorn_access.log"
errorlog = "/app/logs/gunicorn_error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = 'pricing_agent_ml'

# Server mechanics
daemon = False
pidfile = '/tmp/gunicorn_ml.pid'
user = 'mluser'
group = 'mlgroup'
tmp_upload_dir = None

# Worker timeout for ML operations
timeout = 120
graceful_timeout = 30

# Development settings (overridden by environment)
if os.getenv('DEBUG', 'False').lower() == 'true':
    reload = True
    loglevel = 'debug'
    workers = 1  # Single worker for development

# GPU settings
if os.getenv('USE_GPU', 'False').lower() == 'true':
    workers = 1  # Single worker for GPU to avoid conflicts

# Health check worker setup
def when_ready(server):
    """Called just after the server is started."""
    server.log.info("ML Service is ready. Spawning workers")

def worker_int(worker):
    """Called just after a worker exited on SIGINT or SIGQUIT."""
    worker.log.info("ML worker received INT or QUIT signal")

def pre_fork(server, worker):
    """Called just before a worker is forked."""
    server.log.info("ML Worker spawned (pid: %s)", worker.pid)

def post_fork(server, worker):
    """Called just after a worker has been forked."""
    server.log.info("ML Worker spawned (pid: %s)", worker.pid)

def post_worker_init(worker):
    """Called just after a worker has initialized the application."""
    worker.log.info("ML Worker initialized (pid: %s)", worker.pid)
    # Load ML models here if needed
    
def worker_abort(worker):
    """Called when a worker received the SIGABRT signal."""
    worker.log.info("ML Worker aborted (pid: %s)", worker.pid)

# Custom worker class for ML service
class MLUvicornWorker:
    """Custom worker class for ML operations"""
    pass