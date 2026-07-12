from django.apps import AppConfig


class StaffConfig(AppConfig):

    
    # DEFAULT PRIMARY KEY TYPE
    
    default_auto_field = "django.db.models.BigAutoField"

    
    # APP NAME
    
    name = "staff"

    
    # ADMIN DISPLAY NAME
    
    verbose_name = "Staff Management"

    
    # APP STARTUP LOGIC
    
    def ready(self):

        """
        Import signals when Django starts.

        This ensures:
        - automatic event registration
        - notification hooks
        - audit logging
        - future EMIS integrations
        - async task triggers
        - scalable ERP automation

        Signals are imported here intentionally
        to avoid circular imports and ensure
        Django app registry is fully loaded.
        """

        try:
            import staff.signals  # noqa

        except ImportError:
            pass