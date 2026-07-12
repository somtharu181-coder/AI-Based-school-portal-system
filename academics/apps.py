from django.apps import AppConfig
import logging


logger = logging.getLogger(__name__)


class AcademicsConfig(AppConfig):
    """
    Enterprise-level configuration for Academics app.

    Responsibilities:
    - App initialization
    - Signal registration
    - Startup safety
    - Deployment-safe loading
    - Scalable architecture support
    """

    default_auto_field = "django.db.models.BigAutoField"

    name = "academics"

    verbose_name = "Academic Management System"

    def ready(self):
        """
        Executes when Django starts.

        Used for:
        - signal registration
        - startup hooks
        - future event systems
        - scalable initialization logic

        Safe for:
        - production deployment
        - Docker
        - Celery
        - Gunicorn
        - testing environments
        """

        try:
            import academics.signals

            logger.info(
                "Academics signals loaded successfully."
            )

        except ImportError as e:

            logger.warning(
                f"Academics signals could not be loaded: {e}"
            )

        except Exception as e:

            logger.exception(
                f"Unexpected error while loading academics signals: {e}"
            )