from django.apps import AppConfig


class ReportingSystemConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "reporting_system"
    verbose_name = "Reporting System (Result Engine)"

    def ready(self):
        # Import signals to ensure they are registered
        import reporting_system.signals  # noqa