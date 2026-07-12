import logging

from django.db import transaction
from django.db.models.signals import (
    pre_save,
    post_save,
    post_delete,
)
from django.dispatch import receiver
from django.core.exceptions import ValidationError

from .models import (
    AcademicYear,
    ExamTerm,
    TeacherSubjectAssignment,
    ClassRoutine,
)




logger = logging.getLogger(__name__)




def log_event(level, message):
    """
    Centralized logging helper.

    Keeps logging standardized across signals.
    """

    if level == "info":
        logger.info(message)

    elif level == "warning":
        logger.warning(message)

    elif level == "error":
        logger.error(message)

    else:
        logger.debug(message)




@receiver(post_save, sender=AcademicYear)
def academic_year_audit_log(
    sender,
    instance,
    created,
    **kwargs
):
    """
    Production-grade audit logging.
    """

    action = "CREATED" if created else "UPDATED"

    transaction.on_commit(
        lambda: log_event(
            "info",
            (
                f"AcademicYear {action}: "
                f"{instance.name}"
            )
        )
    )


@receiver(post_delete, sender=AcademicYear)
def academic_year_delete_log(sender, instance, **kwargs):
    """
    Logs academic year deletion events.
    """

    transaction.on_commit(
        lambda: log_event(
            "warning",
            (
                f"AcademicYear DELETED: "
                f"{instance.name}"
            )
        )
    )



# TEACHER SUBJECT ASSIGNMENT SIGNALS



@receiver(post_save, sender=TeacherSubjectAssignment)
def assignment_audit_log(sender, instance, created, **kwargs):

    action = "CREATED" if created else "UPDATED"

    teacher = getattr(instance, "teacher", None)
    user = getattr(getattr(teacher, "user", None), "username", None)
    username = user or "deleted-user"

    class_subject = getattr(instance, "class_subject", None)
    subject_name = getattr(getattr(class_subject, "subject", None), "name", None)
    subject_name = subject_name or "deleted-subject"

    transaction.on_commit(
        lambda: log_event(
            "info",
            f"TeacherAssignment {action}: {username} | {subject_name}"
        )
    )


@receiver(post_delete, sender=TeacherSubjectAssignment)
def assignment_delete_log(sender, instance, **kwargs):

    teacher = getattr(instance, "teacher", None)
    user = getattr(getattr(teacher, "user", None), "username", None)
    username = user or "deleted-user"

    transaction.on_commit(
        lambda: log_event(
            "warning",
            f"TeacherAssignment DELETED: {username}"
        )
    )



# CLASS ROUTINE SIGNALS



@receiver(post_save, sender=ClassRoutine)
def routine_audit_log(
    sender,
    instance,
    created,
    **kwargs
):
    """
    Audit logs for timetable events.
    """

    action = "CREATED" if created else "UPDATED"

    transaction.on_commit(
        lambda: log_event(
            "info",
            (
                f"ClassRoutine {action}: "
                f"{instance.section} | "
                f"{instance.day} | "
                f"{instance.start_time}"
            )
        )
    )


@receiver(post_delete, sender=ClassRoutine)
def routine_delete_log(sender, instance, **kwargs):
    """
    Logs routine deletion events.
    """

    transaction.on_commit(
        lambda: log_event(
            "warning",
            (
                f"ClassRoutine DELETED: "
                f"{instance.section} | "
                f"{instance.day}"
            )
        )
    )


# ─────────────────────────────────────────────────────────────────────────────
#  EXAM TERM — RESULT PUBLISH EVENT
# ─────────────────────────────────────────────────────────────────────────────

@receiver(pre_save, sender=ExamTerm)
def _capture_exam_term_old_published(sender, instance, **kwargs):
    """Store the previous is_published value so post_save can detect the flip."""
    try:
        instance._was_published = ExamTerm.objects.get(pk=instance.pk).is_published
    except ExamTerm.DoesNotExist:
        instance._was_published = False


@receiver(post_save, sender=ExamTerm)
def exam_term_result_publish_notification(sender, instance, created, **kwargs):
    """
    When ExamTerm.is_published flips False → True, fire a notification to
    all affected students and their parents.
    """
    was = getattr(instance, "_was_published", False)
    if not created and not was and instance.is_published:
        def _notify():
            try:
                from notifications.services import notify_exam_results_published
                notify_exam_results_published(instance)
            except Exception as exc:
                logger.exception(
                    "exam_term_result_publish_notification failed: %s", exc
                )
        transaction.on_commit(_notify)

    action = "CREATED" if created else "UPDATED"
    transaction.on_commit(
        lambda: log_event(
            "info",
            f"ExamTerm {action}: {instance.name} | published={instance.is_published}"
        )
    )