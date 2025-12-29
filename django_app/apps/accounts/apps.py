from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.accounts'
    verbose_name = 'Accounts'
    
    def ready(self):
        # Import signal handlers
        try:
            import apps.accounts.signals  # noqa F401
        except ImportError:
            pass