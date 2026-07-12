import logging
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from .models import StaffProfile


# LOGGER SETUP (PRODUCTION SAFE)

logger = logging.getLogger(__name__)



# STAFF CREATED / UPDATED SIGNAL

@receiver(post_save, sender=StaffProfile)
def staff_profile_post_save(sender, instance, created, **kwargs):

    try:

        if created:
            # -----------------------------------------
            # STAFF CREATED EVENT
            # -----------------------------------------

            logger.info(
                f"[STAFF CREATED] ID={instance.staff_id} USER={instance.user.username}"
            )

            # Future Hooks (SAFE PLACEHOLDERS)
            # These will work for both Template + React systems

            # 1. Notification system hook
            # send_notification(event="staff_created", user_id=instance.user.id)

            # 2. Audit log hook
            # create_audit_log(action="CREATE_STAFF", ref_id=instance.staff_id)

            # 3. EMIS sync hook
            # emis_sync_staff(instance.staff_id)

        else:
            # -----------------------------------------
            # STAFF UPDATED EVENT
            # -----------------------------------------

            logger.info(
                f"[STAFF UPDATED] ID={instance.staff_id} USER={instance.user.username}"
            )

            # Example future hooks
            # track_staff_changes(instance)

    except Exception as e:

        logger.error(
            f"[STAFF SIGNAL ERROR] ID={instance.staff_id} ERROR={str(e)}"
        )



# STAFF DELETE SIGNAL

@receiver(pre_delete, sender=StaffProfile)
def staff_profile_pre_delete(sender, instance, **kwargs):

    try:

        logger.warning(
            f"[STAFF DELETED] ID={instance.staff_id} USER={instance.user.username}"
        )

        # Future cleanup hooks
        # delete_related_attendance(instance)
        # remove_from_emis(instance.staff_id)

    except Exception as e:

        logger.error(
            f"[STAFF DELETE ERROR] ID={instance.staff_id} ERROR={str(e)}"
        )