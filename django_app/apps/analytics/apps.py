from django.apps import AppConfig


class AnalyticsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.analytics'
    verbose_name = 'Analytics'
    
    def ready(self):
        # Import signal handlers
        try:
            import apps.analytics.signals  # noqa F401
        except ImportError:
            pass