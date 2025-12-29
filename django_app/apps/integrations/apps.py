from django.apps import AppConfig


class IntegrationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.integrations'
    verbose_name = 'Integrations'
    
    def ready(self):
        # Import signal handlers
        try:
            import apps.integrations.signals  # noqa F401
        except ImportError:
            pass