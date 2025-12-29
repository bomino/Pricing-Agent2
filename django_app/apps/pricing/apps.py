from django.apps import AppConfig


class PricingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.pricing'
    verbose_name = 'Pricing'
    
    def ready(self):
        # Import signal handlers
        try:
            import apps.pricing.signals  # noqa F401
        except ImportError:
            pass