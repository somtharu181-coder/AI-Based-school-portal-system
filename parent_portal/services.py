from django.db.models import Q
from .models import ParentProfile, OnlineMeeting, SchoolLetter
from academics.models import StudentMark
from attendance.models import StudentAttendance, AttendanceStatus


def get_parent_profile(user):
    return ParentProfile.objects.filter(user=user).select_related("user").prefetch_related(
        "children__section__class_obj"
    ).first()


def get_children(parent_profile):
    return parent_profile.children.select_related("section__class_obj", "user").all()


def get_child_marks(student):
    return StudentMark.objects.filter(student=student).select_related(
        "exam_term", "class_subject__subject"
    ).order_by("exam_term__start_date")


def get_child_attendance_summary(student):
    total   = StudentAttendance.objects.filter(student=student).count()
    present = StudentAttendance.objects.filter(
        student=student,
        status__in=[AttendanceStatus.PRESENT, AttendanceStatus.LATE]
    ).count()
    return {
        "total":   total,
        "present": present,
        "absent":  total - present,
        "pct":     round(present / total * 100, 1) if total else 0,
    }


def get_upcoming_meetings(student=None):
    from django.utils import timezone
    qs = OnlineMeeting.objects.filter(
        status__in=["scheduled", "live"],
        scheduled_at__gte=timezone.now()
    )
    if student:
        class_obj = student.section.class_obj
        qs = qs.filter(Q(target_class=class_obj) | Q(target_class__isnull=True))
    return qs.order_by("scheduled_at")


def get_school_letters(student=None):
    qs = SchoolLetter.objects.filter(is_published=True)
    if student:
        class_obj = student.section.class_obj
        qs = qs.filter(Q(target_class=class_obj) | Q(target_class__isnull=True))
    return qs


def create_meeting(host, title, description, meeting_url, scheduled_at, target_class=None):
    return OnlineMeeting.objects.create(
        host=host, title=title, description=description,
        meeting_url=meeting_url, scheduled_at=scheduled_at,
        target_class=target_class,
    )


def publish_letter(issued_by, title, body, target_class=None):
    return SchoolLetter.objects.create(
        issued_by=issued_by, title=title, body=body,
        target_class=target_class, is_published=True,
    )
