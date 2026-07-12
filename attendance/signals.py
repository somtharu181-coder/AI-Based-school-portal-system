import logging
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from .models import StudentAttendance, StaffAttendance

logger = logging.getLogger(__name__)



# STUDENT ATTENDANCE SIGNAL

@receiver(post_save, sender=StudentAttendance)
def student_attendance_post_save(sender, instance, created, **kwargs):

    try:

        if created:

            # -----------------------------------------
            # NEW ATTENDANCE MARKED
            # -----------------------------------------
            logger.info(
                f"[STUDENT ATTENDANCE CREATED] "
                f"Student={instance.student.student_id} "
                f"Date={instance.date} "
                f"Status={instance.status}"
            )

            # FUTURE INTEGRATIONS (SAFE HOOKS)
            # ------------------------------------------------
            # send_notification(student=instance.student, status=instance.status)
            # create_audit_log(action="STUDENT_ATTENDANCE_MARKED")
            # emis_sync_attendance(instance)

        else:

            # -----------------------------------------
            # ATTENDANCE UPDATED
            # -----------------------------------------
            logger.info(
                f"[STUDENT ATTENDANCE UPDATED] "
                f"Student={instance.student.student_id} "
                f"Date={instance.date}"
            )

    except Exception as e:
        logger.error(f"[STUDENT ATTENDANCE SIGNAL ERROR] {str(e)}")



# STAFF ATTENDANCE SIGNAL

@receiver(post_save, sender=StaffAttendance)
def staff_attendance_post_save(sender, instance, created, **kwargs):

    try:

        if created:

            logger.info(
                f"[STAFF ATTENDANCE CREATED] "
                f"Staff={instance.staff.staff_id} "
                f"Date={instance.date} "
                f"Status={instance.status}"
            )

            # FUTURE HOOKS
            # send_staff_notification(...)
            # audit_log(...)
            # payroll_sync_if_absent(instance)

        else:

            logger.info(
                f"[STAFF ATTENDANCE UPDATED] "
                f"Staff={instance.staff.staff_id} "
                f"Date={instance.date}"
            )

    except Exception as e:
        logger.error(f"[STAFF ATTENDANCE SIGNAL ERROR] {str(e)}")



# DELETE SIGNALS (AUDIT SAFETY)

@receiver(pre_delete, sender=StudentAttendance)
def student_attendance_pre_delete(sender, instance, **kwargs):

    logger.warning(
        f"[STUDENT ATTENDANCE DELETED] "
        f"Student={instance.student.student_id} "
        f"Date={instance.date}"
    )


@receiver(pre_delete, sender=StaffAttendance)
def staff_attendance_pre_delete(sender, instance, **kwargs):

    logger.warning(
        f"[STAFF ATTENDANCE DELETED] "
        f"Staff={instance.staff.staff_id} "
        f"Date={instance.date}"
    )