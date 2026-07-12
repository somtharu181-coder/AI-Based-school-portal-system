"""
Audit Log Services
==================
Thin service layer for creating audit log entries.
All writes are fire-and-forget — errors are caught and logged to
the standard Python logger so they never interrupt application flow.
"""

import logging
from .models import AuditLog, AuditEvent

logger = logging.getLogger("audit_log")


def _get_ip(request) -> str:
    """Extract real client IP from request, honouring X-Forwarded-For."""
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def log_event(
    *,
    event: str,
    request=None,
    user=None,
    detail: str = "",
    model_name: str = "",
    object_id: str = "",
    object_repr: str = "",
    success: bool = True,
) -> None:
    """
    Create an AuditLog entry. Safe to call from any context.

    Parameters
    ----------
    event       : AuditEvent value string
    request     : Django HttpRequest (optional, used to extract IP / user)
    user        : User instance (overrides request.user if provided)
    detail      : Free-text description
    model_name  : Name of the affected model (e.g. "StudentProfile")
    object_id   : PK/ID of the affected object
    object_repr : Human-readable representation of the object
    success     : Whether the action succeeded
    """
    try:
        resolved_user = user
        ip = ""
        ua = ""

        if request is not None:
            ip = _get_ip(request)
            ua = request.META.get("HTTP_USER_AGENT", "")[:500]
            if resolved_user is None and request.user.is_authenticated:
                resolved_user = request.user

        AuditLog.objects.create(
            user=resolved_user,
            event=event,
            detail=detail[:2000],
            model_name=model_name[:100],
            object_id=str(object_id)[:100],
            object_repr=str(object_repr)[:255],
            ip_address=ip or None,
            user_agent=ua,
            success=success,
        )
    except Exception as exc:
        logger.exception("Failed to write audit log entry: %s", exc)


# ── Convenience helpers ────────────────────────────────────────────────────────

def log_login_success(request, user) -> None:
    log_event(
        event=AuditEvent.LOGIN_SUCCESS,
        request=request,
        user=user,
        detail=f"User '{user.username}' logged in successfully.",
        success=True,
    )


def log_login_failed(request, username: str) -> None:
    log_event(
        event=AuditEvent.LOGIN_FAILED,
        request=request,
        detail=f"Failed login attempt for username '{username}'.",
        success=False,
    )


def log_logout(request, user) -> None:
    log_event(
        event=AuditEvent.LOGOUT,
        request=request,
        user=user,
        detail=f"User '{user.username}' logged out.",
        success=True,
    )


def log_password_change(request, user, reset_by=None) -> None:
    if reset_by and reset_by != user:
        detail = f"Password for '{user.username}' was reset by admin '{reset_by.username}'."
        event  = AuditEvent.PASSWORD_RESET
    else:
        detail = f"User '{user.username}' changed their own password."
        event  = AuditEvent.PASSWORD_CHANGE
    log_event(
        event=event,
        request=request,
        user=reset_by or user,
        detail=detail,
        model_name="User",
        object_id=str(user.pk),
        object_repr=str(user),
        success=True,
    )


def log_record_created(request, instance, extra: str = "") -> None:
    log_event(
        event=AuditEvent.RECORD_CREATED,
        request=request,
        detail=f"Created {type(instance).__name__}: {instance}. {extra}".strip(),
        model_name=type(instance).__name__,
        object_id=str(getattr(instance, "pk", "")),
        object_repr=str(instance)[:255],
        success=True,
    )


def log_record_updated(request, instance, extra: str = "") -> None:
    log_event(
        event=AuditEvent.RECORD_UPDATED,
        request=request,
        detail=f"Updated {type(instance).__name__}: {instance}. {extra}".strip(),
        model_name=type(instance).__name__,
        object_id=str(getattr(instance, "pk", "")),
        object_repr=str(instance)[:255],
        success=True,
    )


def log_record_deleted(request, instance, extra: str = "") -> None:
    log_event(
        event=AuditEvent.RECORD_DELETED,
        request=request,
        detail=f"Deleted {type(instance).__name__}: {instance}. {extra}".strip(),
        model_name=type(instance).__name__,
        object_id=str(getattr(instance, "pk", "")),
        object_repr=str(instance)[:255],
        success=True,
    )


def log_permission_denied(request, detail: str = "") -> None:
    log_event(
        event=AuditEvent.PERMISSION_DENIED,
        request=request,
        detail=detail or "Permission denied.",
        success=False,
    )
