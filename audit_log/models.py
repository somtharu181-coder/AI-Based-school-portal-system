"""
Audit Log Models
================
Provides a centralised, tamper-evident audit trail for:
  - User authentication events (login / logout / failed attempts)
  - Permission denials
  - Admin actions (create / update / delete on key models)
  - Security events (password change, role change)

Designed to be append-only from application code.
"""

from django.db import models
from django.conf import settings


class AuditEvent(models.TextChoices):
    # Auth
    LOGIN_SUCCESS  = "login_success",  "Login Success"
    LOGIN_FAILED   = "login_failed",   "Login Failed"
    LOGOUT         = "logout",         "Logout"
    PASSWORD_RESET = "password_reset", "Password Reset"
    PASSWORD_CHANGE = "password_change", "Password Change"
    # Access control
    PERMISSION_DENIED = "permission_denied", "Permission Denied"
    # Data operations
    RECORD_CREATED = "record_created", "Record Created"
    RECORD_UPDATED = "record_updated", "Record Updated"
    RECORD_DELETED = "record_deleted", "Record Deleted"
    # System
    BULK_ACTION    = "bulk_action",   "Bulk Action"
    RESULT_REBUILT = "result_rebuilt", "Result Rebuilt"
    PDF_GENERATED  = "pdf_generated",  "PDF Generated"


class AuditLog(models.Model):
    """
    Central audit log entry.

    Fields are intentionally simple to maximise write throughput and
    ensure entries are never silently dropped.
    """

    # Who performed the action (null = anonymous / system)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        db_index=True,
    )

    event     = models.CharField(max_length=50, choices=AuditEvent.choices, db_index=True)
    # Human-readable description
    detail    = models.TextField(blank=True)

    # Affected object reference (optional)
    model_name  = models.CharField(max_length=100, blank=True)
    object_id   = models.CharField(max_length=100, blank=True)
    object_repr = models.CharField(max_length=255, blank=True)

    # Request metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    # Outcome
    success = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["event", "created_at"], name="audit_event_ts_idx"),
            models.Index(fields=["user", "created_at"],  name="audit_user_ts_idx"),
            models.Index(fields=["model_name", "object_id"], name="audit_obj_idx"),
        ]
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"

    def __str__(self):
        username = self.user.username if self.user else "anonymous"
        return f"[{self.event}] {username} @ {self.created_at:%Y-%m-%d %H:%M:%S}"
