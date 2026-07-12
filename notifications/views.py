import logging
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse

from .services import (
    create_notification, get_notifications_for_user,
    mark_as_read, unread_count,
)
from .models import Notification, NotificationCategory, NotificationPriority
from academics.models import Class, Section

logger = logging.getLogger(__name__)


@login_required
def inbox(request):
    items = get_notifications_for_user(request.user)
    return render(request, "notifications/inbox.html", {
        "items":      items,
        "unread":     unread_count(request.user),
        "categories": NotificationCategory.choices,
    })


@login_required
def mark_read(request, pk=None):
    mark_as_read(request.user, notification_id=pk)
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"unread": unread_count(request.user)})
    return redirect("notifications:inbox")


@login_required
def send(request):
    if request.user.role not in ("admin", "staff"):
        messages.error(request, "You are not authorised to send notifications.")
        return redirect("notifications:inbox")

    if request.method == "POST":
        category           = request.POST.get("category", NotificationCategory.INTERNAL)
        title              = request.POST.get("title", "").strip()
        body               = request.POST.get("body", "").strip()
        priority           = request.POST.get("priority", "medium")
        class_id           = request.POST.get("target_class") or None
        section_id         = request.POST.get("target_section") or None
        audience_types     = request.POST.getlist("audience_types")
        specific_staff_ids = [int(x) for x in request.POST.getlist("specific_staff") if x]
        specific_user_ids  = [int(x) for x in request.POST.getlist("specific_users") if x]

        if not title or not body:
            messages.error(request, "Title and message body are required.")
        else:
            cls = Class.objects.filter(pk=class_id).first()     if class_id   else None
            sec = Section.objects.filter(pk=section_id).first() if section_id else None

            if not audience_types:
                # default by category
                if category == NotificationCategory.INTERNAL:
                    audience_types = ["all_staff"]
                elif category == NotificationCategory.PARENT:
                    audience_types = ["parents"]
                elif category == NotificationCategory.MANAGEMENT:
                    audience_types = ["admin"]

            notif = create_notification(
                sender=request.user,
                category=category,
                title=title,
                body=body,
                priority=priority,
                target_class=cls,
                target_section=sec,
                audience_types=audience_types,
                specific_staff_ids=specific_staff_ids or None,
                specific_user_ids=specific_user_ids or None,
            )

            recipient_count = notif.recipients.count()
            messages.success(
                request,
                f"Notification sent to {recipient_count} recipient{'s' if recipient_count != 1 else ''}."
            )
            return redirect("notifications:inbox")

    from academics.services import sorted_classes
    from staff.models import StaffProfile
    import json

    # Build sections JSON for JS cascade
    sections_by_class = {}
    for sec in Section.objects.select_related("class_obj").order_by("class_obj__id", "name"):
        cid = str(sec.class_obj_id)
        sections_by_class.setdefault(cid, []).append({"id": sec.id, "name": sec.name})

    return render(request, "notifications/send.html", {
        "categories":      NotificationCategory.choices,
        "priorities":      NotificationPriority.choices,
        "classes":         sorted_classes(),
        "sections":        Section.objects.select_related("class_obj").order_by("class_obj__id", "name"),
        "staff_list":      StaffProfile.objects.select_related("user").filter(is_active=True).order_by("designation", "user__username"),
        "sections_json":   json.dumps(sections_by_class),
    })
