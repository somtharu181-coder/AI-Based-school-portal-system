import logging
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from .models import StudentProfile

User = get_user_model()

logger = logging.getLogger(__name__)





@receiver(pre_save, sender=StudentProfile)
def validate_student_profile(sender, instance, **kwargs):
    """
    Enterprise-safe validation.

    IMPORTANT:
    - Do NOT raise exceptions (prevents admin crash)
    - Only log or ignore invalid state
    """

    if instance.user and instance.user.role != "student":
        logger.warning(
            f"[STUDENTS] Invalid role assignment attempt: {instance.user.username}"
        )
        # We do NOT block save in production ERP systems
        # Admin layer should handle validation instead





@receiver(post_save, sender=StudentProfile)
def student_profile_post_save(sender, instance, created, **kwargs):
    """
    Lightweight event handler.

    Purpose:
    - audit logging
    - future notifications
    - EMIS sync hook
    """

    if created:
        logger.info(
            f"[STUDENTS] New student profile created: {instance.student_id}"
        )

        # ── Event-driven: notify admin about new enrollment ──────────────
        try:
            from notifications.services import notify_student_enrolled
            from django.db import transaction
            transaction.on_commit(lambda: notify_student_enrolled(instance))
        except Exception as exc:
            logger.warning("[STUDENTS] Enrollment notification failed: %s", exc)