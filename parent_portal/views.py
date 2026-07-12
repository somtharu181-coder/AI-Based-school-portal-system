import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse

from .services import (
    get_parent_profile, get_children, get_child_marks,
    get_child_attendance_summary, get_upcoming_meetings,
    get_school_letters, create_meeting, publish_letter,
)
from .models import OnlineMeeting, SchoolLetter
from academics.models import Class, Section

logger = logging.getLogger(__name__)


def is_parent(user):
    return user.is_authenticated and user.role == "parent"


# ─────────────────────────────────────────────────────────────────────────────
#  PARENT DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    if not is_parent(request.user):
        return redirect("accounts:login")
    profile = get_parent_profile(request.user)
    if not profile:
        return render(request, "parent_portal/no_profile.html")

    children = get_children(profile)
    selected_id = request.GET.get("child")
    selected = marks = attendance = meetings = letters = None
    child_recs = child_recs_parent_steps = child_timetable = None

    if children.exists():
        selected = children.filter(pk=selected_id).first() if selected_id else children.first()
        if selected:
            marks      = get_child_marks(selected)
            attendance = get_child_attendance_summary(selected)
            meetings   = get_upcoming_meetings(selected)
            letters    = get_school_letters(selected)

            try:
                from analytics.services import run_analytics_for_student
                from analytics.presentation_helpers import (
                    build_human_recommendations, build_study_timetable,
                )
                result      = run_analytics_for_student(selected.id)
                child_recs  = build_human_recommendations(
                    selected,
                    result.get("predictions", []),
                    result.get("analytics", {}),
                    result.get("recommendations", []),
                )
                child_timetable = build_study_timetable(
                    selected, result.get("predictions", []), result.get("analytics", {})
                )
            except Exception:
                logger.exception("Analytics pipeline failed for student %s", selected.id)

    from notifications.services import get_notifications_for_user, unread_count
    notifs = get_notifications_for_user(request.user)[:5]

    return render(request, "parent_portal/dashboard.html", {
        "profile":    profile,
        "children":   children,
        "selected":   selected,
        "marks":      marks,
        "attendance": attendance,
        "meetings":   meetings,
        "letters":    letters,
        "notifs":     notifs,
        "unread":     unread_count(request.user),
        "child_recs":               child_recs,
        "child_recs_parent_steps":  child_recs_parent_steps,
        "child_timetable":          child_timetable,
    })


# ─────────────────────────────────────────────────────────────────────────────
#  MEETINGS
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def meetings_view(request):
    all_meetings = OnlineMeeting.objects.all().order_by("-scheduled_at")
    return render(request, "parent_portal/meetings.html", {"meetings": all_meetings})


@login_required
def create_meeting_view(request):
    if request.user.role not in ("admin", "staff"):
        return redirect("parent_portal:dashboard")

    if request.method == "POST":
        title        = request.POST.get("title", "").strip()
        description  = request.POST.get("description", "").strip()
        meeting_url  = request.POST.get("meeting_url", "").strip()
        scheduled_at = request.POST.get("scheduled_at", "").strip()
        class_id     = request.POST.get("target_class") or None
        section_id   = request.POST.get("target_section") or None

        # audience
        audience_types     = request.POST.getlist("audience_types")
        specific_staff_ids = [int(x) for x in request.POST.getlist("specific_staff") if x]
        specific_user_ids  = [int(x) for x in request.POST.getlist("specific_users") if x]
        notify_attendees   = request.POST.get("send_notification") == "1"

        if not title or not scheduled_at:
            messages.error(request, "Title and date/time are required.")
        else:
            cls = Class.objects.filter(pk=class_id).first()   if class_id   else None
            sec = Section.objects.filter(pk=section_id).first() if section_id else None

            meeting = create_meeting(
                request.user, title, description, meeting_url, scheduled_at, cls
            )

            # ── Event-driven notification ─────────────────────────────────
            if notify_attendees:
                try:
                    from notifications.services import create_notification
                    from notifications.models import NotificationCategory
                    import datetime

                    try:
                        from django.utils.dateparse import parse_datetime
                        dt = parse_datetime(scheduled_at)
                        sched_str = dt.strftime("%d %b %Y, %H:%M") if dt else scheduled_at
                    except Exception:
                        sched_str = scheduled_at

                    body_parts = [
                        f"An online meeting has been scheduled.",
                        f"\nTitle: {title}",
                        f"Date & Time: {sched_str}",
                    ]
                    if description:
                        body_parts.append(f"Details: {description}")
                    if meeting_url:
                        body_parts.append(f"Join Link: {meeting_url}")

                    # default to parents if no audience selected
                    if not audience_types:
                        audience_types = ["parents"]

                    create_notification(
                        sender=request.user,
                        category=NotificationCategory.PARENT,
                        title=f"Meeting Scheduled: {title}",
                        body="\n".join(body_parts),
                        priority="medium",
                        target_class=cls,
                        target_section=sec,
                        audience_types=audience_types,
                        specific_staff_ids=specific_staff_ids or None,
                        specific_user_ids=specific_user_ids or None,
                    )
                    messages.success(request, f"Meeting scheduled and notifications sent.")
                except Exception as exc:
                    logger.exception("Meeting notification failed: %s", exc)
                    messages.success(request, "Meeting scheduled. Notification delivery failed.")
            else:
                messages.success(request, "Meeting scheduled.")

            return redirect("parent_portal:meetings")

    from academics.services import sorted_classes
    from staff.models import StaffProfile

    return render(request, "parent_portal/create_meeting.html", {
        "classes":      sorted_classes(),
        "sections":     Section.objects.select_related("class_obj").order_by("class_obj__id", "name"),
        "staff_list":   StaffProfile.objects.select_related("user").filter(is_active=True).order_by("designation", "user__username"),
        "sections_json": _sections_json(),
    })


# ─────────────────────────────────────────────────────────────────────────────
#  LETTERS
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def letters_view(request):
    all_letters = SchoolLetter.objects.filter(is_published=True).order_by("-issued_at")
    return render(request, "parent_portal/letters.html", {"letters": all_letters})


@login_required
def publish_letter_view(request):
    if request.user.role not in ("admin", "staff"):
        return redirect("parent_portal:dashboard")

    if request.method == "POST":
        title    = request.POST.get("title", "").strip()
        body     = request.POST.get("body", "").strip()
        class_id = request.POST.get("target_class") or None
        section_id = request.POST.get("target_section") or None

        audience_types     = request.POST.getlist("audience_types")
        specific_staff_ids = [int(x) for x in request.POST.getlist("specific_staff") if x]
        specific_user_ids  = [int(x) for x in request.POST.getlist("specific_users") if x]
        notify_recipients  = request.POST.get("send_notification") == "1"

        if not title or not body:
            messages.error(request, "Title and content are required.")
        else:
            cls = Class.objects.filter(pk=class_id).first()   if class_id   else None
            sec = Section.objects.filter(pk=section_id).first() if section_id else None

            letter = publish_letter(request.user, title, body, cls)

            if notify_recipients:
                try:
                    from notifications.services import create_notification
                    from notifications.models import NotificationCategory

                    if not audience_types:
                        audience_types = ["parents"]

                    create_notification(
                        sender=request.user,
                        category=NotificationCategory.PARENT,
                        title=f"New School Letter: {title}",
                        body=(
                            f"A new letter has been published.\n\n"
                            f"{body[:400]}{'...' if len(body) > 400 else ''}"
                        ),
                        priority="medium",
                        target_class=cls,
                        target_section=sec,
                        audience_types=audience_types,
                        specific_staff_ids=specific_staff_ids or None,
                        specific_user_ids=specific_user_ids or None,
                    )
                    messages.success(request, "Letter published and notifications sent.")
                except Exception as exc:
                    logger.exception("Letter notification failed: %s", exc)
                    messages.success(request, "Letter published. Notification delivery failed.")
            else:
                messages.success(request, "Letter published.")

            return redirect("parent_portal:letters")

    from academics.services import sorted_classes
    from staff.models import StaffProfile

    return render(request, "parent_portal/publish_letter.html", {
        "classes":       sorted_classes(),
        "sections":      Section.objects.select_related("class_obj").order_by("class_obj__id", "name"),
        "staff_list":    StaffProfile.objects.select_related("user").filter(is_active=True).order_by("designation", "user__username"),
        "sections_json": _sections_json(),
    })


# ─────────────────────────────────────────────────────────────────────────────
#  AJAX helper: sections for a given class
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def ajax_sections(request):
    class_id = request.GET.get("class_id")
    if not class_id:
        return JsonResponse({"sections": []})
    secs = Section.objects.filter(
        class_obj_id=class_id
    ).order_by("name").values("id", "name")
    return JsonResponse({"sections": list(secs)})


def _sections_json():
    """Serialise all sections grouped by class for JS filtering."""
    import json
    result = {}
    for sec in Section.objects.select_related("class_obj").order_by("class_obj__id", "name"):
        cid = str(sec.class_obj_id)
        result.setdefault(cid, []).append({"id": sec.id, "name": sec.name})
    return json.dumps(result)
