from django.db import models
from django.utils import timezone

from accounts.models import User
from students.models import StudentProfile
from staff.models import StaffProfile



# ATTENDANCE STATUS (STANDARDIZED)

class AttendanceStatus(models.TextChoices):
    PRESENT = "present", "Present"
    ABSENT = "absent", "Absent"
    LATE = "late", "Late"
    HALF_DAY = "half_day", "Half Day"
    HOLIDAY = "holiday", "Holiday"



# BASE ATTENDANCE MODEL (COMMON STRUCTURE)

class BaseAttendance(models.Model):

    date = models.DateField(default=timezone.now)
    status = models.CharField(
        max_length=20,
        choices=AttendanceStatus.choices
    )

    marked_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="%(class)s_marked_by"
    )

    remarks = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True



# STUDENT ATTENDANCE

class StudentAttendance(BaseAttendance):

    student = models.ForeignKey(
        StudentProfile,
        on_delete=models.CASCADE,
        related_name="attendances"
    )

    class Meta:
        unique_together = ("student", "date")
        ordering = ["-date", "student"]

    def __str__(self):
        return f"{self.student.student_id} - {self.date} - {self.status}"



# STAFF ATTENDANCE

class StaffAttendance(BaseAttendance):

    staff = models.ForeignKey(
        StaffProfile,
        on_delete=models.CASCADE,
        related_name="attendances"
    )

    class Meta:
        unique_together = ("staff", "date")
        ordering = ["-date", "staff"]

    def __str__(self):
        return f"{self.staff.staff_id} - {self.date} - {self.status}"