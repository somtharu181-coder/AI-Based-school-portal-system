from django.apps import AppConfig


class StudentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "students"
    verbose_name = "Students Management System"

    def ready(self):
        """
        Enterprise-level app initialization.

        Purpose:
        - Load signals (if any event-based automation exists)
        - Keep startup clean and lightweight
        - Avoid business logic (handled in services.py)
        """

        
        try:
            import students.signals  # noqa
        except ImportError:
            pass