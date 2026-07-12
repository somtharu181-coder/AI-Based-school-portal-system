"""
Notification Services
=====================
All business logic lives here. Views and signals call these functions only.

Audience resolution supports:
  - role-wide blasts  (all parents, all staff, all students, all admins)
  - class-filtered    (parents/students of a specific class)
  - section-filtered  (parents/students of a specific section)
  - specific users    (hand-picked list of User PKs)
  - combined          (union of multiple audience groups)

Event-driven helpers fire automatically from signals:
  - notify_exam_results_published  ← ExamTerm.is_published flips True
  - notify_meeting_created         ← OnlineMeeting created
  - notify_letter_published        ← SchoolLetter created/published
  - notify_student_enrolled        ← StudentProfile created
  - notify_attendance_alert        ← called from attendance signal
"""

import logging
from django.utils import timezone
from django.db import transaction

from accounts.models import User
from .models import Notification, NotificationRecipient, NotificationCategory

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  AUDIENCE RESOLUTION
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_audience(
    audience_types=None,
    target_class=None,
    target_section=None,
    specific_user_ids=None,
    specific_staff_ids=None,
):
    """
    Resolve a combined recipient queryset from one or more audience targets.

    Parameters
    ----------
    audience_types : list[str]
        Any combination of: 'parents', 'students', 'teachers', 'staff',
        'committee', 'admin', 'all_staff'
    target_class   : Class instance or None   → filter students/parents by class
    target_section : Section instance or None → filter students/parents by section
    specific_user_ids  : list[int] → include exact user PKs
    specific_staff_ids : list[int] → StaffProfile PKs → resolved to User PKs

    Returns
    -------
    list[User] — deduplicated
    """
    from accounts.models import User

    audience_types = audience_types or []
    ids = set()

    for atype in audience_types:
        atype = atype.lower().strip()

        if atype in ("parents", "parent"):
            qs = User.objects.filter(role="parent")
            if target_class:
                from students.models import StudentProfile
                student_ids = StudentProfile.objects.filter(
                    section__class_obj=target_class
                ).values_list("user_id", flat=True)
                qs = User.objects.filter(
                    role="parent",
                    parent_profile__children__user_id__in=student_ids,
                ).distinct()
            elif target_section:
                from students.models import StudentProfile
                student_ids = StudentProfile.objects.filter(
                    section=target_section
                ).values_list("user_id", flat=True)
                qs = User.objects.filter(
                    role="parent",
                    parent_profile__children__user_id__in=student_ids,
                ).distinct()
            ids.update(qs.values_list("id", flat=True))

        elif atype in ("students", "student"):
            qs = User.objects.filter(role="student")
            if target_class:
                from students.models import StudentProfile
                student_user_ids = StudentProfile.objects.filter(
                    section__class_obj=target_class,
                    user__isnull=False,
                ).values_list("user_id", flat=True)
                qs = qs.filter(id__in=student_user_ids)
            elif target_section:
                from students.models import StudentProfile
                student_user_ids = StudentProfile.objects.filter(
                    section=target_section,
                    user__isnull=False,
                ).values_list("user_id", flat=True)
                qs = qs.filter(id__in=student_user_ids)
            ids.update(qs.values_list("id", flat=True))

        elif atype in ("teachers", "teacher"):
            from staff.models import StaffProfile, Designation
            teacher_user_ids = StaffProfile.objects.filter(
                designation=Designation.TEACHER,
                is_active=True,
            ).values_list("user_id", flat=True)
            if target_class:
                # teachers assigned to this class
                from academics.models import TeacherSubjectAssignment
                assigned_ids = TeacherSubjectAssignment.objects.filter(
                    class_subject__class_obj=target_class
                ).values_list("teacher__user_id", flat=True)
                teacher_user_ids = list(set(teacher_user_ids) & set(assigned_ids))
            ids.update(teacher_user_ids)

        elif atype in ("staff", "all_staff"):
            ids.update(
                User.objects.filter(role="staff").values_list("id", flat=True)
            )

        elif atype in ("committee", "management", "principal"):
            from staff.models import StaffProfile, Designation
            committee_desig = [
                Designation.PRINCIPAL,
                Designation.VICE_PRINCIPAL,
                Designation.ADMIN_STAFF,
            ]
            committee_ids = StaffProfile.objects.filter(
                designation__in=committee_desig, is_active=True
            ).values_list("user_id", flat=True)
            ids.update(committee_ids)

        elif atype in ("admin", "admins"):
            ids.update(
                User.objects.filter(role="admin").values_list("id", flat=True)
            )

    # specific hand-picked users
    if specific_user_ids:
        ids.update(specific_user_ids)

    # specific staff profiles → their user PKs
    if specific_staff_ids:
        from staff.models import StaffProfile
        u_ids = StaffProfile.objects.filter(
            pk__in=specific_staff_ids
        ).values_list("user_id", flat=True)
        ids.update(u_ids)

    if not ids:
        return User.objects.none()
    return User.objects.filter(id__in=ids)


# ─────────────────────────────────────────────────────────────────────────────
#  CORE CREATE + FANOUT
# ─────────────────────────────────────────────────────────────────────────────

@transaction.atomic
def create_notification(
    sender,
    category,
    title,
    body,
    priority="medium",
    target_class=None,
    target_section=None,
    recipients=None,
    # new audience-builder params
    audience_types=None,
    specific_user_ids=None,
    specific_staff_ids=None,
):
    """
    Create a Notification and fan-out NotificationRecipient rows.

    If `recipients` is given explicitly it takes priority.
    Otherwise audience is resolved via `audience_types`.
    Falls back to category-based resolution for backward compatibility.
    """
    notif = Notification.objects.create(
        sender=sender,
        category=category,
        title=title,
        body=body,
        priority=priority,
        target_class=target_class,
        target_section=target_section,
    )

    if recipients is not None:
        # explicit queryset / list passed in
        resolved = recipients
    elif audience_types:
        resolved = _resolve_audience(
            audience_types=audience_types,
            target_class=target_class,
            target_section=target_section,
            specific_user_ids=specific_user_ids,
            specific_staff_ids=specific_staff_ids,
        )
    else:
        # legacy category-based fallback
        resolved = _legacy_recipients_for_category(category, target_class, target_section)

    bulk = [
        NotificationRecipient(notification=notif, user=u)
        for u in resolved
    ]
    NotificationRecipient.objects.bulk_create(bulk, ignore_conflicts=True)
    logger.info(
        "[NOTIFICATION] '%s' sent to %d recipients (category=%s)",
        title, len(bulk), category,
    )
    return notif


def _legacy_recipients_for_category(category, target_class=None, target_section=None):
    """Backward-compat: resolve by old category enum."""
    if category == NotificationCategory.INTERNAL:
        return User.objects.filter(role__in=["staff", "admin"])
    elif category == NotificationCategory.PARENT:
        qs = User.objects.filter(role="parent")
        if target_class:
            from students.models import StudentProfile
            student_ids = StudentProfile.objects.filter(
                section__class_obj=target_class
            ).values_list("user_id", flat=True)
            qs = User.objects.filter(
                role="parent",
                parent_profile__children__user_id__in=student_ids,
            ).distinct()
        return qs
    elif category == NotificationCategory.MANAGEMENT:
        return User.objects.filter(role="admin")
    return User.objects.none()


# ─────────────────────────────────────────────────────────────────────────────
#  QUERY HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def get_notifications_for_user(user, unread_only=False):
    qs = NotificationRecipient.objects.filter(user=user).select_related(
        "notification__sender"
    )
    if unread_only:
        qs = qs.filter(is_read=False)
    return qs


def mark_as_read(user, notification_id=None):
    qs = NotificationRecipient.objects.filter(user=user, is_read=False)
    if notification_id:
        qs = qs.filter(notification_id=notification_id)
    qs.update(is_read=True, read_at=timezone.now())


def unread_count(user) -> int:
    return NotificationRecipient.objects.filter(user=user, is_read=False).count()


# ─────────────────────────────────────────────────────────────────────────────
#  EVENT-DRIVEN HELPERS  (called from signals / services)
# ─────────────────────────────────────────────────────────────────────────────

def notify_exam_results_published(exam_term, triggered_by=None):
    """
    Fire when ExamTerm.is_published flips True.
    Notifies:
      - all students in every class that has marks for this term
      - all parents of those students
    """
    try:
        from academics.models import StudentMark
        from students.models import StudentProfile

        # which classes have marks for this term?
        class_ids = StudentMark.objects.filter(
            exam_term=exam_term
        ).values_list(
            "student__section__class_obj_id", flat=True
        ).distinct()

        # collect all affected student users + their parents
        student_users = User.objects.filter(
            role="student",
            student_profile__section__class_obj_id__in=class_ids,
        ).distinct()

        parent_users = User.objects.filter(
            role="parent",
            parent_profile__children__section__class_obj_id__in=class_ids,
        ).distinct()

        recipients = (student_users | parent_users).distinct()

        system_sender = _get_system_sender()
        create_notification(
            sender=triggered_by or system_sender,
            category=NotificationCategory.PARENT,
            title=f"Results Published: {exam_term.name}",
            body=(
                f"The results for {exam_term.name} ({exam_term.academic_year.name}) "
                f"have been published. Log in to view your results."
            ),
            priority="high",
            recipients=recipients,
        )
        logger.info("[EVENT] Result publish notification sent for ExamTerm %s", exam_term)
    except Exception as exc:
        logger.exception("[EVENT] notify_exam_results_published failed: %s", exc)


def notify_meeting_created(meeting, triggered_by=None):
    """
    Fire when an OnlineMeeting is created.
    Notifies parents (and optionally students) of the target class (or all if no class).
    """
    try:
        system_sender = _get_system_sender()
        audience = ["parents"]
        scheduled = meeting.scheduled_at.strftime("%d %b %Y, %H:%M") if meeting.scheduled_at else "TBD"

        create_notification(
            sender=triggered_by or system_sender,
            category=NotificationCategory.PARENT,
            title=f"Meeting Scheduled: {meeting.title}",
            body=(
                f"An online meeting has been scheduled.\n\n"
                f"Title: {meeting.title}\n"
                f"Date & Time: {scheduled}\n"
                f"{'Details: ' + meeting.description if meeting.description else ''}"
            ),
            priority="medium",
            audience_types=audience,
            target_class=meeting.target_class,
        )
        logger.info("[EVENT] Meeting notification sent: %s", meeting.title)
    except Exception as exc:
        logger.exception("[EVENT] notify_meeting_created failed: %s", exc)


def notify_letter_published(letter, triggered_by=None):
    """
    Fire when a SchoolLetter is published.
    Notifies parents of the target class (or all parents if no class).
    """
    try:
        system_sender = _get_system_sender()
        create_notification(
            sender=triggered_by or system_sender,
            category=NotificationCategory.PARENT,
            title=f"New School Letter: {letter.title}",
            body=(
                f"A new letter has been published by the school.\n\n"
                f"{letter.body[:300]}{'...' if len(letter.body) > 300 else ''}"
            ),
            priority="medium",
            audience_types=["parents"],
            target_class=letter.target_class,
        )
        logger.info("[EVENT] Letter notification sent: %s", letter.title)
    except Exception as exc:
        logger.exception("[EVENT] notify_letter_published failed: %s", exc)


def notify_student_enrolled(student_profile, triggered_by=None):
    """
    Fire when a new StudentProfile is created.
    Notifies admin users about the new enrollment.
    """
    try:
        system_sender = _get_system_sender()
        create_notification(
            sender=triggered_by or system_sender,
            category=NotificationCategory.MANAGEMENT,
            title="New Student Enrolled",
            body=(
                f"A new student has been enrolled.\n"
                f"Name: {student_profile.name or 'N/A'}\n"
                f"Class: {student_profile.section.class_obj.name} — "
                f"Section {student_profile.section.name}\n"
                f"Roll No: {student_profile.roll_number}"
            ),
            priority="low",
            audience_types=["admin"],
        )
        logger.info("[EVENT] Enrollment notification: %s", student_profile)
    except Exception as exc:
        logger.exception("[EVENT] notify_student_enrolled failed: %s", exc)


def notify_attendance_alert(student_profile, attendance_pct, triggered_by=None):
    """
    Fire when a student's attendance drops below 75%.
    Notifies their parents.
    """
    try:
        if attendance_pct >= 75:
            return  # only alert for low attendance

        system_sender = _get_system_sender()
        parent_users = User.objects.filter(
            role="parent",
            parent_profile__children=student_profile,
        ).distinct()

        if not parent_users.exists():
            return

        create_notification(
            sender=triggered_by or system_sender,
            category=NotificationCategory.PARENT,
            title=f"Attendance Alert: {student_profile.name or 'Your Child'}",
            body=(
                f"This is an alert regarding the attendance of "
                f"{student_profile.name or 'your child'}.\n\n"
                f"Current attendance: {attendance_pct:.1f}%\n"
                f"Minimum required: 75%\n\n"
                f"Please ensure regular attendance to avoid academic issues."
            ),
            priority="high",
            recipients=parent_users,
        )
        logger.info(
            "[EVENT] Attendance alert sent for student %s (%.1f%%)",
            student_profile, attendance_pct,
        )
    except Exception as exc:
        logger.exception("[EVENT] notify_attendance_alert failed: %s", exc)


def _get_system_sender():
    """Return a system/admin user as the default sender for automated notifications."""
    return User.objects.filter(role="admin", is_active=True).order_by("id").first()
