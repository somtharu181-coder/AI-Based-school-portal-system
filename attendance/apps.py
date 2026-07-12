from django.apps import AppConfig


class AttendanceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "attendance"
    verbose_name = "Attendance Management"

    
    def ready(self):
        """
        This is executed when Django starts.
        Used ONLY for:
        - registering signals
        - startup configurations
        """

        import attendance.signals  # noqa