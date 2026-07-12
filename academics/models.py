import uuid

from django.db import models
from django.db.models import Q, F
from django.core.exceptions import ValidationError



# BASE MODEL

class BaseModel(models.Model):

    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True



# ACADEMIC YEAR

class AcademicYear(BaseModel):

    name = models.CharField(max_length=20, unique=True, db_index=True)
    start_date = models.DateField()
    end_date = models.DateField()

    is_current = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ["-start_date"]

    def clean(self):
        if self.start_date >= self.end_date:
            raise ValidationError("End date must be greater than start date.")

    def save(self, *args, **kwargs):
        if self.is_current:
            AcademicYear.objects.exclude(pk=self.pk).update(is_current=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name



# SUBJECT

class Subject(BaseModel):

    code = models.CharField(max_length=20, unique=True, db_index=True)
    name = models.CharField(max_length=100, unique=True, db_index=True)
    description = models.TextField(blank=True)
    credit_hours = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.code} - {self.name}"


# CLASS (IMPORT SAFE - STRING FK)

class Class(BaseModel):

    name = models.CharField(max_length=50, unique=True, db_index=True)

    class Meta:
        ordering = ["id"]
        verbose_name_plural = "Classes"

    def __str__(self):
        return self.name



# SECTION

class Section(BaseModel):

    class_obj = models.ForeignKey(
        Class,
        on_delete=models.CASCADE,
        related_name="sections"
    )

    name = models.CharField(max_length=10)
    def clean(self):
        self.name = self.name.upper()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["class_obj", "name"],
                name="uq_class_section"
            )
        ]
        ordering = ["class_obj", "name"]

    def __str__(self):
        return f"{self.class_obj} - {self.name}"



# CLASS SUBJECT

class ClassSubject(BaseModel):

    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name="class_subjects",
        db_index=True
    )

    class_obj= models.ForeignKey(
        Class,
        on_delete=models.CASCADE,
        related_name="class_subjects",
        db_index=True
    )

    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name="assigned_classes",
        db_index=True
    )

    is_optional = models.BooleanField(default=False)

    full_marks = models.PositiveIntegerField(default=100)
    pass_marks = models.PositiveIntegerField(default=40)

    def __str__(self):
        return (f"{self.class_obj.name} - "f"{self.subject.name}")

    class Meta:
        ordering = ["class_obj", "subject"]

        constraints = [
            models.UniqueConstraint(
                fields=["academic_year", "class_obj", "subject"],
                name="uq_academic_class_subject_year"
            ),
            models.CheckConstraint(
                condition=Q(pass_marks__lte=F("full_marks")),
                name="chk_pass_marks_lte_full_marks"
            ),
            models.CheckConstraint(
                condition=Q(full_marks__gt=0),
                name="chk_full_marks_positive"
            ),
            models.CheckConstraint(
                condition=Q(pass_marks__gte=0),
                name="chk_pass_marks_non_negative"
            ),
        ]


# TEACHER ASSIGNMENT (IMPORT SAFE FIX)

class TeacherSubjectAssignment(BaseModel):

    teacher = models.ForeignKey(
        "staff.StaffProfile",
        on_delete=models.CASCADE,
        related_name="teacher_subject_assignments"
    )

    class_subject = models.ForeignKey(
        ClassSubject,
        on_delete=models.CASCADE,
        related_name="teacher_assignments"
    )

    section = models.ForeignKey(
        Section,
        on_delete=models.CASCADE,
        related_name="teacher_assignments"
    )

    remarks = models.TextField(
        blank=True
    )


    is_class_teacher = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["teacher", "class_subject", "section"],
                name="unique_teacher_assignment"
            )
        ]



# WEEKDAYS

class WeekDay(models.TextChoices):
    SUNDAY = "sunday", "Sunday"
    MONDAY = "monday", "Monday"
    TUESDAY = "tuesday", "Tuesday"
    WEDNESDAY = "wednesday", "Wednesday"
    THURSDAY = "thursday", "Thursday"
    FRIDAY = "friday", "Friday"
    SATURDAY = "saturday", "Saturday"



# ROUTINE

class ClassRoutine(BaseModel):

    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name="routines",
        db_index=True
    )

    class_subject = models.ForeignKey(
        ClassSubject,
        on_delete=models.CASCADE,
        related_name="routines"
    )

    teacher = models.ForeignKey(
        "staff.StaffProfile",
        on_delete=models.SET_NULL,
        null=True,
        related_name="class_routines"
    )

    section = models.ForeignKey(
        Section,
        on_delete=models.CASCADE,
        related_name="routines",
        db_index=True
    )

    day = models.CharField(max_length=20, choices=WeekDay.choices, db_index=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    room = models.CharField(
        max_length=50,
        blank=True
    )

    def clean(self):

        if self.start_time >= self.end_time:
            raise ValidationError(
                "End time must be greater than start time.")

    class Meta:
        ordering = ["day", "start_time"]

        constraints = [
            models.UniqueConstraint(
                fields=["academic_year", "section", "day", "start_time"],
                name="unique_section_routine"
            ),
            models.CheckConstraint(
                condition=Q(end_time__gt=F("start_time")),
                name="valid_routine_time"
            ),
        ]


# EXAM TERM


class ExamTerm(BaseModel):

    class TermType(models.TextChoices):

        FIRST = "first", "First Term"
        SECOND = "second", "Second Term"
        THIRD = "third", "Third Term"
        FINAL = "final", "Final Exam"

    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name="exam_terms",
        db_index=True
    )

    name = models.CharField(
        max_length=100,
        db_index=True
    )

    term_type = models.CharField(
        max_length=20,
        choices=TermType.choices,
        db_index=True
    )

    start_date = models.DateField()

    end_date = models.DateField()

    is_published = models.BooleanField(
        default=False,
        db_index=True
    )

    class Meta:

        ordering = ["start_date"]

        constraints = [

            models.UniqueConstraint(
                fields=[
                    "academic_year",
                    "name"
                ],
                name="unique_exam_term_per_year"
            ),
        ]

    def clean(self):

        if self.start_date >= self.end_date:

            raise ValidationError(
                "End date must be greater than start date."
            )

    def __str__(self):

        return (
            f"{self.name} "
            f"({self.academic_year.name})"
        )

class StudentMark(BaseModel):

    student = models.ForeignKey(
        "students.StudentProfile",
        on_delete=models.CASCADE,
        related_name="marks",
        db_index=True
    )

    exam_term = models.ForeignKey(
        ExamTerm,
        on_delete=models.CASCADE,
        related_name="marks",
        db_index=True
    )

    class_subject = models.ForeignKey(
        ClassSubject,
        on_delete=models.CASCADE,
        related_name="student_marks",
        db_index=True
    )

    theory_marks = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0
    )

    practical_marks = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0
    )

    total_marks = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0
    )

    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0
    )

    grade = models.CharField(
        max_length=5,
        blank=True
    )

    gpa = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0
    )

    is_absent = models.BooleanField(default=False)

    remarks = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "exam_term", "class_subject"],
                name="unique_student_subject_mark"
            )
        ]

    def __str__(self):
        return f"{self.student} - {self.class_subject}"