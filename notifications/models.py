"""
Notification Models
===================
Three notification channels:
  1. Internal  — Principal → Teachers / Staff
  2. Parent     — School   → Parents
  3. Management — System-wide management alerts
"""
import uuid
from django.db import models
from accounts.models import User


class NotificationCategory(models.TextChoices):
    INTERNAL   = "internal",   "Internal (Staff)"
    PARENT     = "parent",     "Parent"
    MANAGEMENT = "management", "Management"


class NotificationPriority(models.TextChoices):
    LOW    = "low",    "Low"
    MEDIUM = "medium", "Medium"
    HIGH   = "high",   "High"
    URGENT = "urgent", "Urgent"


class Notification(models.Model):
    """Core notification record."""

    uuid     = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    category = models.CharField(max_length=20, choices=NotificationCategory.choices, db_index=True)
    priority = models.CharField(max_length=10, choices=NotificationPriority.choices, default=NotificationPriority.MEDIUM)

    sender   = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="sent_notifications")
    title    = models.CharField(max_length=255)
    body     = models.TextField()

    # Optional: target a specific class/section
    target_class   = models.ForeignKey("academics.Class",   null=True, blank=True, on_delete=models.SET_NULL)
    target_section = models.ForeignKey("academics.Section", null=True, blank=True, on_delete=models.SET_NULL)

    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.category.upper()}] {self.title}"


class NotificationRecipient(models.Model):
    """Tracks per-user delivery and read status."""

    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name="recipients")
    user         = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    is_read      = models.BooleanField(default=False)
    read_at      = models.DateTimeField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("notification", "user")
        ordering = ["-created_at"]

    def __str__(self):
        status = "Read" if self.is_read else "Unread"
        return f"{self.user.username} — {self.notification.title} [{status}]"
