import json
import functools

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.http import JsonResponse

from rest_framework import viewsets, status as drf_status
from rest_framework.decorators import action
from rest_framework.response import Response

from .services import (
    mark_student_attendance,
    mark_staff_attendance,
    bulk_mark_student_attendance,
    get_student_attendance_summary,
    get_staff_attendance_summary,
)
from .models import StudentAttendance, StaffAttendance, AttendanceStatus
from students.models import StudentProfile
from staff.models import StaffProfile
from academics.models import Class, Section, AcademicYear, TeacherSubjectAssignment



# ROLE HELPERS

def is_admin_or_staff(user):
    return user.is_authenticated and user.role.lower() in ("admin", "staff")

def is_admin(user):
    return user.is_authenticated and user.role.lower() == "admin"


def _is_principal(user):
    if not user.is_authenticated or user.role != "staff":
        return False
    try:
        from staff.models import StaffProfile, Designation
        return StaffProfile.objects.filter(
            user=user, designation=Designation.PRINCIPAL
        ).exists()
    except Exception:
        return False


def require_write_role(view_func):
    """Block principals from attendance write views."""
    @functools.wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if _is_principal(request.user):
            messages.warning(
                request,
                "Principals have read-only access to attendance records."
            )
            return redirect("accounts:principal_dashboard")
        return view_func(request, *args, **kwargs)
    return _wrapped



# 1. MARK STUDENT ATTENDANCE (HTML — CLASS WISE)

@login_required
@user_passes_test(is_admin_or_staff)
@require_write_role
def mark_student_attendance_view(request):
    """
    - Admin: sees ALL sections.
    - Staff (teacher): sees ONLY sections where they are the class teacher
      (is_class_teacher=True in TeacherSubjectAssignment).
    """

    today    = timezone.now().date()
    is_admin = request.user.role.lower() == "admin"

    # ── Determine which sections this user may access ──
    if is_admin:
        allowed_sections = Section.objects.select_related("class_obj").all()
    else:
        # Get the StaffProfile for the logged-in user
        try:
            staff_profile = StaffProfile.objects.get(user=request.user)
        except StaffProfile.DoesNotExist:
            # Staff user has no StaffProfile yet — show all sections so they
            # can still take attendance (admin-equivalent fallback)
            allowed_sections = Section.objects.select_related("class_obj").all()
            classes = Class.objects.filter(
                id__in=allowed_sections.values_list("class_obj_id", flat=True).distinct()
            )
            from academics.services import sorted_classes as _sc
            classes = _sc(classes)
            messages.warning(
                request,
                "No staff profile is linked to your account. "
                "Showing all sections. Ask admin to create your staff profile."
            )
            # Skip the class-teacher filter and render with all sections
            return render(request, "attendance/mark_student_attendance.html", {
                "classes":           classes,
                "sections":          allowed_sections,
                "students":          [],
                "selected_section":  None,
                "date":              str(today),
                "existing_map":      {},
                "existing_map_json": "{}",
                "status_choices":    AttendanceStatus.choices,
                "today":             str(today),
                "is_admin":          False,
            })

        # Only sections where this teacher is the class teacher
        assigned_section_ids = TeacherSubjectAssignment.objects.filter(
            teacher=staff_profile,
            is_class_teacher=True,
        ).values_list("section_id", flat=True).distinct()

        allowed_sections = Section.objects.filter(
            id__in=assigned_section_ids
        ).select_related("class_obj")

    # Classes that have at least one allowed section (for the class dropdown)
    allowed_class_ids = allowed_sections.values_list("class_obj_id", flat=True).distinct()
    from academics.services import sorted_classes as _sc
    classes = _sc(Class.objects.filter(id__in=allowed_class_ids))

    selected_section = None
    students         = []
    existing_map     = {}

    section_id = request.GET.get("section_id") or request.POST.get("section_id")
    date_str   = request.GET.get("date") or request.POST.get("date") or str(today)

    if section_id:
        # Security: ensure the requested section is in the allowed set
        selected_section = allowed_sections.filter(pk=section_id).first()
        if not selected_section:
            messages.error(
                request,
                "You are not authorised to take attendance for that section."
            )
            return redirect("attendance:mark_student_attendance")

        students = StudentProfile.objects.filter(
            section=selected_section, status="active"
        ).select_related("user")

        existing = StudentAttendance.objects.filter(
            student__in=students, date=date_str
        )
        existing_map = {a.student_id: a.status for a in existing}

    if request.method == "POST" and selected_section:
        date_val = request.POST.get("date", str(today))
        saved = 0
        for student in students:
            status_val = request.POST.get(f"status_{student.id}", "absent")
            try:
                mark_student_attendance(
                    student_id=student.student_id,
                    status=status_val,
                    date=date_val,
                    marked_by=request.user,
                )
                saved += 1
            except Exception as e:
                messages.error(request, f"Error for {student}: {e}")

        messages.success(request, f"Attendance saved for {saved} students.")
        return redirect("attendance:mark_student_attendance")

    return render(request, "attendance/mark_student_attendance.html", {
        "classes":           classes,
        "sections":          allowed_sections,
        "students":          students,
        "selected_section":  selected_section,
        "date":              date_str,
        "existing_map":      existing_map,
        "existing_map_json": json.dumps({str(k): v for k, v in existing_map.items()}),
        "status_choices":    AttendanceStatus.choices,
        "today":             str(today),
        "is_admin":          is_admin,
    })



# 2. VIEW STUDENT ATTENDANCE RECORDS

@login_required
@user_passes_test(is_admin_or_staff)
def student_attendance_list(request):
    """
    List all student attendance records with filters.
    """

    records = StudentAttendance.objects.select_related(
        "student", "student__section", "marked_by"
    ).order_by("-date")

    # Filters
    section_id = request.GET.get("section")
    date_from  = request.GET.get("date_from")
    date_to    = request.GET.get("date_to")
    status_f   = request.GET.get("status")

    if section_id:
        records = records.filter(student__section_id=section_id)
    if date_from:
        records = records.filter(date__gte=date_from)
    if date_to:
        records = records.filter(date__lte=date_to)
    if status_f:
        records = records.filter(status=status_f)

    return render(request, "attendance/student_attendance_list.html", {
        "records":        records[:200],   # cap at 200 rows
        "sections":       Section.objects.select_related("class_obj").all(),
        "status_choices": AttendanceStatus.choices,
        "filters": {
            "section":   section_id,
            "date_from": date_from,
            "date_to":   date_to,
            "status":    status_f,
        },
    })



# 3. MY ATTENDANCE (STUDENT VIEW)

@login_required
def my_attendance_view(request):
    """
    Student sees their own attendance summary + records.
    """

    try:
        student = StudentProfile.objects.get(user=request.user)
    except StudentProfile.DoesNotExist:
        messages.error(request, "No student profile found for your account.")
        return redirect("accounts:student_dashboard")

    records = StudentAttendance.objects.filter(
        student=student
    ).order_by("-date")

    summary = get_student_attendance_summary(student.student_id)

    total   = summary.get("total", 0)
    present = summary.get("present", 0)
    pct     = round((present / total * 100), 1) if total > 0 else 0

    return render(request, "attendance/my_attendance.html", {
        "student":  student,
        "records":  records,
        "summary":  summary,
        "pct":      pct,
    })



# 4. AJAX — GET SECTIONS BY CLASS

def get_sections_by_class(request):
    class_id = request.GET.get("class_id")
    if not class_id:
        return JsonResponse({"sections": []})
    sections = Section.objects.filter(class_obj_id=class_id).values("id", "name")
    return JsonResponse({"sections": list(sections)})



# DRF VIEWSET (API — kept for API consumers)

class AttendanceViewSet(viewsets.ViewSet):

    @action(detail=False, methods=["post"])
    def mark_student(self, request):
        try:
            data = request.data
            attendance, created = mark_student_attendance(
                student_id=data.get("student_id"),
                status=data.get("status"),
                date=data.get("date", timezone.now().date()),
                marked_by=request.user,
                remarks=data.get("remarks"),
            )
            return Response({"status": "success", "created": created,
                             "student_id": attendance.student.student_id})
        except Exception as e:
            return Response({"status": "error", "message": str(e)},
                            status=drf_status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"])
    def mark_staff(self, request):
        try:
            data = request.data
            attendance, created = mark_staff_attendance(
                staff_id=data.get("staff_id"),
                status=data.get("status"),
                date=data.get("date", timezone.now().date()),
                marked_by=request.user,
                remarks=data.get("remarks"),
            )
            return Response({"status": "success", "created": created,
                             "staff_id": attendance.staff.staff_id})
        except Exception as e:
            return Response({"status": "error", "message": str(e)},
                            status=drf_status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"])
    def bulk_student(self, request):
        try:
            data   = request.data.get("students", [])
            result = bulk_mark_student_attendance(
                students_data=data,
                date=request.data.get("date"),
                marked_by=request.user,
            )
            return Response({"status": "success", "marked_count": len(result)})
        except Exception as e:
            return Response({"status": "error", "message": str(e)},
                            status=drf_status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["get"])
    def student_summary(self, request):
        student_id = request.query_params.get("student_id")
        data = get_student_attendance_summary(student_id)
        return Response({"status": "success", "data": data})

    @action(detail=False, methods=["get"])
    def staff_summary(self, request):
        staff_id = request.query_params.get("staff_id")
        data = get_staff_attendance_summary(staff_id)
        return Response({"status": "success", "data": data})
