"""
Audit Log Signals
=================
Connects Django auth signals to the audit log service so login / logout
events are captured automatically without modifying any view.
"""

import logging
from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.dispatch import receiver
from .services import log_event, AuditEvent

logger = logging.getLogger("audit_log")


@receiver(user_logged_in)
def _on_login(sender, request, user, **kwargs):
    try:
        from .services import _get_ip
        ip = _get_ip(request) if request else None
        ua = request.META.get("HTTP_USER_AGENT", "")[:500] if request else ""
        from .models import AuditLog
        AuditLog.objects.create(
            user=user,
            event=AuditEvent.LOGIN_SUCCESS,
            detail=f"User '{user.username}' (role={user.role}) logged in.",
            ip_address=ip or None,
            user_agent=ua,
            success=True,
        )
    except Exception as exc:
        logger.exception("Audit signal login error: %s", exc)


@receiver(user_logged_out)
def _on_logout(sender, request, user, **kwargs):
    if user is None:
        return
    try:
        from .services import _get_ip
        from .models import AuditLog
        ip = _get_ip(request) if request else None
        ua = request.META.get("HTTP_USER_AGENT", "")[:500] if request else ""
        AuditLog.objects.create(
            user=user,
            event=AuditEvent.LOGOUT,
            detail=f"User '{user.username}' logged out.",
            ip_address=ip or None,
            user_agent=ua,
            success=True,
        )
    except Exception as exc:
        logger.exception("Audit signal logout error: %s", exc)


@receiver(user_login_failed)
def _on_login_failed(sender, credentials, request, **kwargs):
    try:
        from .services import _get_ip
        from .models import AuditLog
        ip = _get_ip(request) if request else None
        ua = request.META.get("HTTP_USER_AGENT", "")[:500] if request else ""
        username = credentials.get("username", "unknown")
        AuditLog.objects.create(
            user=None,
            event=AuditEvent.LOGIN_FAILED,
            detail=f"Failed login attempt for username '{username}'.",
            ip_address=ip or None,
            user_agent=ua,
            success=False,
        )
    except Exception as exc:
        logger.exception("Audit signal login_failed error: %s", exc)
