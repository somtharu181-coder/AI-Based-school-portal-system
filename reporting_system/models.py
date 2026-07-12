import uuid
from django.db import models
from django.db.models import Sum, Avg, F
from django.core.exceptions import ValidationError



# BASE MODEL

class BaseModel(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True



# STUDENT RESULT (FINAL RESULT PER EXAM)

class StudentResult(BaseModel):

    student = models.ForeignKey(
        "students.StudentProfile",
        on_delete=models.CASCADE,
        related_name="results"
    )

    exam_term = models.ForeignKey(
        "academics.ExamTerm",
        on_delete=models.CASCADE,
        related_name="results"
    )

    total_obtained_marks = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    total_full_marks = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    gpa = models.DecimalField(max_digits=3, decimal_places=2, default=0)

    grade = models.CharField(max_length=5, blank=True)
    rank = models.PositiveIntegerField(null=True, blank=True)

    is_pass = models.BooleanField(default=True)

    class Meta:
        unique_together = ("student", "exam_term")
        ordering = ["-percentage"]

    def __str__(self):
        return f"{self.student} - {self.exam_term}"



# SUBJECT RESULT (PER SUBJECT RESULT)

class SubjectResult(BaseModel):

    student_result = models.ForeignKey(
        StudentResult,
        on_delete=models.CASCADE,
        related_name="subject_results"
    )

    class_subject = models.ForeignKey(
        "academics.ClassSubject",
        on_delete=models.CASCADE
    )

    theory_marks = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    practical_marks = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    total_marks = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    grade = models.CharField(max_length=5, blank=True)
    is_pass = models.BooleanField(default=True)

    class Meta:
        unique_together = ("student_result", "class_subject")



# RESULT CALCULATION LOG (AUDIT OF RESULT ENGINE)

class ResultCalculationLog(BaseModel):

    student = models.ForeignKey(
        "students.StudentProfile",
        on_delete=models.CASCADE
    )

    exam_term = models.ForeignKey(
        "academics.ExamTerm",
        on_delete=models.CASCADE
    )

    action = models.CharField(max_length=100)  # generated / updated / recalculated

    total_marks = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    gpa = models.DecimalField(max_digits=3, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)



# CLASS RESULT SUMMARY (CLASS TOPPER / ANALYTICS)

class ClassResultSummary(BaseModel):

    academic_year = models.ForeignKey(
        "academics.AcademicYear",
        on_delete=models.CASCADE
    )

    class_obj = models.ForeignKey(
        "academics.Class",
        on_delete=models.CASCADE
    )

    exam_term = models.ForeignKey(
        "academics.ExamTerm",
        on_delete=models.CASCADE
    )

    average_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    highest_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    lowest_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    total_students = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("academic_year", "class_obj", "exam_term")



# TRANSCRIPT (FINAL YEAR REPORT)

class StudentTranscript(BaseModel):

    student = models.ForeignKey(
        "students.StudentProfile",
        on_delete=models.CASCADE,
        related_name="transcripts"
    )

    academic_year = models.ForeignKey(
        "academics.AcademicYear",
        on_delete=models.CASCADE
    )

    total_gpa = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    final_grade = models.CharField(max_length=5, blank=True)

    remarks = models.TextField(blank=True)

    is_promoted = models.BooleanField(default=True)

    class Meta:
        unique_together = ("student", "academic_year")



# REPORT GENERATION HISTORY

class ReportGenerationLog(BaseModel):

    student = models.ForeignKey(
        "students.StudentProfile",
        on_delete=models.CASCADE
    )

    generated_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True
    )

    report_type = models.CharField(
        max_length=50,
        choices=[
            ("result", "Result"),
            ("transcript", "Transcript"),
            ("class_report", "Class Report"),
        ]
    )

    status = models.CharField(
        max_length=20,
        choices=[
            ("generated", "Generated"),
            ("updated", "Updated"),
        ]
    )