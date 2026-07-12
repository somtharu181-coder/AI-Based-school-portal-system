from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test

from students.models import StudentProfile
from .services import run_analytics_for_all_students, run_analytics_for_student
from .presentation_helpers import (
    build_subject_prediction_table,
    build_term_forecast,
    build_subject_ranking,
    build_performance_insights,
    build_student_outlook,
    build_subject_timeline,
    build_teacher_summary,
    build_principal_summary,
    build_human_recommendations,
    build_subject_teacher_advice,
    build_teacher_own_recommendations,
    build_study_timetable,
)


# ROLE CHECKERS


def _is_admin(user):
    return user.is_authenticated and user.role.lower() == "admin"


def _is_admin_or_staff(user):
    return user.is_authenticated and user.role.lower() in ("admin", "staff")



# 1. ADMIN / TEACHER — ANALYTICS DASHBOARD

@login_required
@user_passes_test(_is_admin_or_staff)
def analytics_dashboard(request):
    result = run_analytics_for_all_students()
    all_data = result.get("data", [])
    high_risk_count   = sum(1 for d in all_data if d.get("analytics", {}).get("risk_level") == "high")
    medium_risk_count = sum(1 for d in all_data if d.get("analytics", {}).get("risk_level") == "medium")
    low_risk_count    = sum(1 for d in all_data if d.get("analytics", {}).get("risk_level") == "low")
    context = {
        "total_students":    result.get("total_students", 0),
        "data":              all_data,
        "message":           result.get("message", ""),
        "high_risk_count":   high_risk_count,
        "medium_risk_count": medium_risk_count,
        "low_risk_count":    low_risk_count,
    }
    return render(request, "analytics/analytics_dashboard.html", context)



# 2. STUDENT DETAIL — FULL AI REPORT

@login_required
def student_analytics_detail(request, student_id):
    """Admin/Staff can view any student. Students can only view their own."""
    # IDOR fix: students can only see their own report
    if request.user.role.lower() == "student":
        try:
            from students.models import StudentProfile as _SP
            own_profile = _SP.objects.get(user=request.user)
        except Exception:
            from django.http import Http404
            raise Http404
        if str(own_profile.id) != str(student_id):
            from django.http import Http404
            raise Http404
    student = get_object_or_404(StudentProfile, id=student_id)
    result  = run_analytics_for_student(student_id)

    predictions     = result.get("predictions", [])
    recommendations = result.get("recommendations", [])
    analytics       = result.get("analytics", {})

    context = {
        "student":         student,
        "analytics":       analytics,
        "recommendations": recommendations,
        "predictions":     predictions,
        "message":         result.get("message", ""),
        "error":           result.get("error", False),
        "back_url":        "analytics:analytics_dashboard",
       
        "subject_table":    build_subject_prediction_table(predictions),
        "term_forecast":    build_term_forecast(predictions, analytics),
        "subject_ranking":  build_subject_ranking(predictions),
        "insights":         build_performance_insights(predictions, recommendations),
        "outlook":          build_student_outlook(predictions, analytics),
        "subject_timeline": build_subject_timeline(predictions),
        "human_recs":       build_human_recommendations(student, predictions, analytics, recommendations),
        "study_timetable":  build_study_timetable(student, predictions, analytics),
    }
    return render(request, "analytics/student_detail.html", context)



@login_required
def my_ai_report(request):
    try:
        student = StudentProfile.objects.get(user=request.user)
    except StudentProfile.DoesNotExist:
        messages.error(request, "No student profile linked to your account.")
        return redirect("accounts:student_dashboard")

    result          = run_analytics_for_student(student.id)
    predictions     = result.get("predictions", [])
    recommendations = result.get("recommendations", [])
    analytics       = result.get("analytics", {})

    context = {
        
        "student":         student,
        "analytics":       analytics,
        "recommendations": recommendations,
        "predictions":     predictions,
        "message":         result.get("message", ""),
        "error":           result.get("error", False),
        "back_url":        "accounts:student_dashboard",
    
        "subject_table":    build_subject_prediction_table(predictions),
        "term_forecast":    build_term_forecast(predictions, analytics),
        "subject_ranking":  build_subject_ranking(predictions),
        "insights":         build_performance_insights(predictions, recommendations),
        "outlook":          build_student_outlook(predictions, analytics),
        "subject_timeline": build_subject_timeline(predictions),
        "human_recs":       build_human_recommendations(student, predictions, analytics, recommendations),
        "study_timetable":  build_study_timetable(student, predictions, analytics),
    }
    return render(request, "analytics/student_detail.html", context)


# 4. TEACHER VIEW  (NEW)

@login_required
@user_passes_test(_is_admin_or_staff)
def teacher_analytics_view(request):
    """
    Teacher / Admin view: subject-wise prediction summary, at-risk subjects,
    most improved subjects, declining subjects, recommended interventions,
    and student risk distribution chart.
    If the logged-in user is a teacher (staff role), only their assigned
    subjects are shown and they see personalised recommendations.
    """
    from staff.models import StaffProfile

    result      = run_analytics_for_all_students()
    all_data    = result.get("data", [])

    # Get staff profile for filtering (None for admin — sees all)
    staff_profile = None
    if request.user.role.lower() == "staff":
        try:
            staff_profile = StaffProfile.objects.get(user=request.user)
        except StaffProfile.DoesNotExist:
            pass

    teacher_data       = build_teacher_summary(all_data, staff_profile=staff_profile)
    own_recommendations = build_teacher_own_recommendations(staff_profile, all_data) if staff_profile else []

    context = {
        "teacher_data":        teacher_data,
        "own_recommendations": own_recommendations,
        "is_filtered":         staff_profile is not None,
        "back_url":            "analytics:analytics_dashboard",
    }
    return render(request, "analytics/teacher_analytics.html", context)


# 5. PRINCIPAL VIEW  (NEW)

@login_required
@user_passes_test(_is_admin_or_staff)
def principal_analytics_view(request):
    """
    Principal / Admin view: school-wide prediction summary, class-wise GPA
    forecast, class-wise risk distribution, top improving classes, classes
    needing attention.
    Aggregates existing outputs only — no new algorithm.
    """
    result         = run_analytics_for_all_students()
    all_data       = result.get("data", [])
    principal_data = build_principal_summary(all_data)

    context = {
        "principal_data":        principal_data,
        "subject_teacher_advice": build_subject_teacher_advice(all_data),
        "back_url":              "analytics:analytics_dashboard",
    }
    return render(request, "analytics/principal_analytics.html", context)
