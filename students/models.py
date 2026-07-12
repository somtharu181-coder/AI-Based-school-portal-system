from django.db import models
from accounts.models import User
from academics.models import AcademicYear
from academics.models import Section
import uuid


# STUDENT PROFILE (ENTERPRISE LEVEL)

class StudentProfile(models.Model):

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        GRADUATED = "graduated", "Graduated"
        DROPPED = "dropped", "Dropped"

    class ReligionType(models.TextChoices):
        RELIGIOUS = "religious", "Religious"
        NON_RELIGIOUS = "non_religious", "Non Religious"

    class GenderType(models.TextChoices):
        MALE = "male", "Male"
        FEMALE = "female", "Female"
        OTHER = "other", "Other"

    section = models.ForeignKey(Section, on_delete=models.PROTECT)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="student_profile",
        null=True,
        blank=True
    )

    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="students"
    )

    student_id = models.CharField(max_length=50, unique=True,blank=True, editable=False)
    def save(self, *args, **kwargs):
        if not self.student_id:
            org_id = "42019"

            self.student_id = (
                f"{org_id}"
                f"{self.section.class_obj.id}"
                f"{self.section.id}"
                f"{self.roll_number}"
            )
        super().save(*args, **kwargs)

    roll_number = models.CharField(max_length=20)

    religion_type = models.CharField(
        max_length=20,
        choices=ReligionType.choices,
        default=ReligionType.NON_RELIGIOUS
    )

    name = models.CharField(max_length=100, blank=True, null=True, db_index=True)

    gender = models.CharField(
        max_length=10,
        choices=GenderType.choices,
        default=GenderType.MALE
    )

    email = models.EmailField(unique=True, blank=True, null=True)

    date_of_birth = models.DateField(null=True, blank=True)
    admission_date = models.DateField(auto_now_add=True)

    temporary_address = models.TextField(blank=True, null=True)
    permanent_address = models.TextField(blank=True, null=True)
    father_name = models.CharField(max_length=100, blank=True, null=True)
    mother_name = models.CharField(max_length=100, blank=True, null=True)
    telephone_number = models.CharField(max_length=15, blank=True, null=True)

    guardian_name = models.CharField(max_length=100, blank=True, null=True)
    guardian_phone = models.CharField(max_length=15, blank=True, null=True)
    

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["section", "roll_number"]
        indexes = [
            models.Index(fields=["status"], name="student_status_idx"),
            models.Index(fields=["section", "status"], name="student_section_status_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["section", "roll_number", "academic_year"],
                name="stu_uq_section_roll"
            )
        ]

    def __str__(self):
        return f"{self.name or 'Student'} | {self.section} | Roll {self.roll_number}"