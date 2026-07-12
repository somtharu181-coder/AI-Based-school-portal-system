import uuid
from django.db import models
from accounts.models import User


class ParentProfile(models.Model):
    """Links a parent User to one or more StudentProfiles."""
    uuid     = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user     = models.OneToOneField(User, on_delete=models.CASCADE, related_name="parent_profile")
    children = models.ManyToManyField("students.StudentProfile", related_name="parents", blank=True)
    phone    = models.CharField(max_length=15, blank=True)
    address  = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Parent: {self.user.get_full_name() or self.user.username}"


class OnlineMeeting(models.Model):
    """School-arranged online meetings that parents can join."""
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        LIVE      = "live",      "Live"
        ENDED     = "ended",     "Ended"
        CANCELLED = "cancelled", "Cancelled"

    uuid        = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    title       = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    host        = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="hosted_meetings")
    meeting_url = models.URLField(blank=True, help_text="Zoom / Google Meet / Teams link")
    scheduled_at = models.DateTimeField()
    status      = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED)
    target_class = models.ForeignKey("academics.Class", null=True, blank=True, on_delete=models.SET_NULL)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-scheduled_at"]

    def __str__(self):
        return self.title


class SchoolLetter(models.Model):
    """Official letters from school published to parents."""
    uuid       = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    title      = models.CharField(max_length=255)
    body       = models.TextField()
    issued_by  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="issued_letters")
    target_class = models.ForeignKey("academics.Class", null=True, blank=True, on_delete=models.SET_NULL)
    is_published = models.BooleanField(default=False)
    issued_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-issued_at"]

    def __str__(self):
        return self.title
