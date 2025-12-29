"""
Celery configuration for async processing
"""
import os
from celery import Celery
from django.conf import settings

# Set the default Django settings module for the 'celery' program
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pricing_agent.settings_local')

# Create Celery app
app = Celery('pricing_agent')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs
app.autodiscover_tasks()

# Configure Celery beat schedule for periodic tasks
app.conf.beat_schedule = {
    'check-price-anomalies': {
        'task': 'apps.analytics.tasks.detect_price_anomalies',
        'schedule': 3600.0,  # Every hour
    },
    'calculate-savings-opportunities': {
        'task': 'apps.analytics.tasks.calculate_savings_opportunities',
        'schedule': 86400.0,  # Daily
    },
    'generate-daily-reports': {
        'task': 'apps.analytics.tasks.generate_daily_reports',
        'schedule': 86400.0,  # Daily at midnight
    },
}

@app.task(bind=True)
def debug_task(self):
    """Debug task to test Celery is working"""
    print(f'Request: {self.request!r}')