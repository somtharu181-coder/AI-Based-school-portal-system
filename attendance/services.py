import logging
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from .models import StudentAttendance, StaffAttendance, AttendanceStatus
from students.models import StudentProfile
from staff.models import StaffProfile

logger = logging.getLogger(__name__)



# STUDENT ATTENDANCE: MARK SINGLE ENTRY

@transaction.atomic
def mark_student_attendance(student_id, status, date=None, marked_by=None, remarks=None):

    try:

        if status not in AttendanceStatus.values:
            raise ValidationError("Invalid attendance status")

        student = StudentProfile.objects.get(student_id=student_id)

        date = date or timezone.now().date()

        # Prevent duplicate entry
        attendance, created = StudentAttendance.objects.update_or_create(
            student=student,
            date=date,
            defaults={
                "status": status,
                "marked_by": marked_by,
                "remarks": remarks,
            }
        )

        logger.info(
            f"[STUDENT ATTENDANCE SERVICE] "
            f"Student={student.student_id} Date={date} Status={status}"
        )

        return attendance, created

    except Exception as e:
        logger.error(f"[MARK STUDENT ATTENDANCE ERROR] {str(e)}")
        raise



# STAFF ATTENDANCE: MARK SINGLE ENTRY

@transaction.atomic
def mark_staff_attendance(staff_id, status, date=None, marked_by=None, remarks=None):

    try:

        if status not in AttendanceStatus.values:
            raise ValidationError("Invalid attendance status")

        staff = StaffProfile.objects.get(staff_id=staff_id)

        date = date or timezone.now().date()

        attendance, created = StaffAttendance.objects.update_or_create(
            staff=staff,
            date=date,
            defaults={
                "status": status,
                "marked_by": marked_by,
                "remarks": remarks,
            }
        )

        logger.info(
            f"[STAFF ATTENDANCE SERVICE] "
            f"Staff={staff.staff_id} Date={date} Status={status}"
        )

        return attendance, created

    except Exception as e:
        logger.error(f"[MARK STAFF ATTENDANCE ERROR] {str(e)}")
        raise



# BULK STUDENT ATTENDANCE MARKING (CLASS WISE)

@transaction.atomic
def bulk_mark_student_attendance(students_data, date=None, marked_by=None):

    """
    students_data format:
    [
        {"student_id": "STU-001", "status": "present"},
        {"student_id": "STU-002", "status": "absent"},
    ]
    """

    try:

        date = date or timezone.now().date()
        results = []

        for item in students_data:

            attendance, created = mark_student_attendance(
                student_id=item["student_id"],
                status=item["status"],
                date=date,
                marked_by=marked_by
            )

            results.append(attendance)

        logger.info(f"[BULK STUDENT ATTENDANCE] Count={len(results)}")

        return results

    except Exception as e:
        logger.error(f"[BULK STUDENT ATTENDANCE ERROR] {str(e)}")
        raise



# ATTENDANCE SUMMARY (FOR REPORTING / DASHBOARD)

def get_student_attendance_summary(student_id, start_date=None, end_date=None):

    try:

        qs = StudentAttendance.objects.filter(
            student__student_id=student_id
        )

        if start_date:
            qs = qs.filter(date__gte=start_date)

        if end_date:
            qs = qs.filter(date__lte=end_date)

        summary = {
            "present": qs.filter(status="present").count(),
            "absent": qs.filter(status="absent").count(),
            "late": qs.filter(status="late").count(),
            "half_day": qs.filter(status="half_day").count(),
            "total": qs.count(),
        }

        return summary

    except Exception as e:
        logger.error(f"[ATTENDANCE SUMMARY ERROR] {str(e)}")
        return {}



# STAFF ATTENDANCE SUMMARY

def get_staff_attendance_summary(staff_id, start_date=None, end_date=None):

    try:

        qs = StaffAttendance.objects.filter(
            staff__staff_id=staff_id
        )

        if start_date:
            qs = qs.filter(date__gte=start_date)

        if end_date:
            qs = qs.filter(date__lte=end_date)

        return {
            "present": qs.filter(status="present").count(),
            "absent": qs.filter(status="absent").count(),
            "late": qs.filter(status="late").count(),
            "total": qs.count(),
        }

    except Exception as e:
        logger.error(f"[STAFF ATTENDANCE SUMMARY ERROR] {str(e)}")
        return {}