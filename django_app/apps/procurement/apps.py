from django.apps import AppConfig


class ProcurementConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.procurement'
    verbose_name = 'Procurement'
    
    def ready(self):
        # Import signal handlers
        try:
            import apps.procurement.signals  # noqa F401
        except ImportError:
            pass