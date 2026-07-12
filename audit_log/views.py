"""
Audit Log Views
===============
Admin-only interface to browse the audit log.
"""

from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render
from django.core.paginator import Paginator

from .models import AuditLog, AuditEvent


def _is_admin(user):
    return user.is_authenticated and user.role.lower() == "admin"


@login_required
@user_passes_test(_is_admin)
def audit_log_list(request):
    logs = AuditLog.objects.select_related("user").all()

    # Filters
    event_filter   = request.GET.get("event", "")
    user_filter    = request.GET.get("user", "").strip()
    success_filter = request.GET.get("success", "")
    date_from      = request.GET.get("date_from", "")
    date_to        = request.GET.get("date_to", "")

    if event_filter:
        logs = logs.filter(event=event_filter)
    if user_filter:
        logs = logs.filter(user__username__icontains=user_filter)
    if success_filter in ("true", "false"):
        logs = logs.filter(success=(success_filter == "true"))
    if date_from:
        logs = logs.filter(created_at__date__gte=date_from)
    if date_to:
        logs = logs.filter(created_at__date__lte=date_to)

    paginator = Paginator(logs, 50)
    page      = request.GET.get("page", 1)
    page_obj  = paginator.get_page(page)

    return render(request, "audit_log/audit_log_list.html", {
        "page_obj":      page_obj,
        "events":        AuditEvent.choices,
        "event_filter":  event_filter,
        "user_filter":   user_filter,
        "success_filter": success_filter,
        "date_from":     date_from,
        "date_to":       date_to,
        "total_count":   logs.count(),
    })
