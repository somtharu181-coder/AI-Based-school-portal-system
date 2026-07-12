import uuid
from django.db import models
from accounts.models import User


class Assignment(models.Model):
    class Status(models.TextChoices):
        DRAFT     = "draft",     "Draft"
        PUBLISHED = "published", "Published"
        CLOSED    = "closed",    "Closed"

    uuid          = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    class_subject = models.ForeignKey("academics.ClassSubject", on_delete=models.CASCADE, related_name="assignments")
    section       = models.ForeignKey("academics.Section",      on_delete=models.CASCADE, related_name="assignments")
    teacher       = models.ForeignKey(User, on_delete=models.CASCADE, related_name="given_assignments")
    title         = models.CharField(max_length=255)
    description   = models.TextField()
    due_date      = models.DateField()
    max_marks     = models.PositiveIntegerField(default=10)
    status        = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} — {self.class_subject}"


class Submission(models.Model):
    class Grade(models.TextChoices):
        EXCELLENT = "excellent", "Excellent"
        GOOD      = "good",      "Good"
        AVERAGE   = "average",   "Average"
        POOR      = "poor",      "Poor"
        PENDING   = "pending",   "Pending"

    uuid       = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name="submissions")
    student    = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE, related_name="submissions")
    answer     = models.TextField(blank=True)
    marks      = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    grade      = models.CharField(max_length=20, choices=Grade.choices, default=Grade.PENDING)
    feedback   = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    checked_at   = models.DateTimeField(null=True, blank=True)
    checked_by   = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="checked_submissions")

    class Meta:
        unique_together = ("assignment", "student")
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.student} → {self.assignment.title}"
