import uuid
from django.db import models
from accounts.models import User


class QuizSession(models.Model):
    """One quiz attempt by a student."""
    uuid      = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    student   = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE, related_name="quiz_sessions")
    subject   = models.ForeignKey("academics.Subject", on_delete=models.SET_NULL, null=True, blank=True)
    class_obj = models.ForeignKey("academics.Class",   on_delete=models.SET_NULL, null=True)
    score     = models.IntegerField(default=0)
    total     = models.IntegerField(default=0)
    completed = models.BooleanField(default=False)
    started_at  = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.student} | {self.subject} | {self.score}/{self.total}"

    @property
    def percentage(self):
        return round(self.score / self.total * 100, 1) if self.total else 0


class Question(models.Model):
    """AI-generated question stored per session."""
    session    = models.ForeignKey(QuizSession, on_delete=models.CASCADE, related_name="questions")
    text       = models.TextField()
    option_a   = models.CharField(max_length=300)
    option_b   = models.CharField(max_length=300)
    option_c   = models.CharField(max_length=300)
    option_d   = models.CharField(max_length=300)
    correct    = models.CharField(max_length=1, choices=[("A","A"),("B","B"),("C","C"),("D","D")])
    chosen     = models.CharField(max_length=1, blank=True)
    is_correct = models.BooleanField(null=True)
    chapter    = models.CharField(max_length=100, blank=True)
    order      = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.text[:60]
