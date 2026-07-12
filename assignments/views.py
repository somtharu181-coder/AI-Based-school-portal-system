import functools
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from .models import Assignment, Submission
from .services import (create_assignment, get_assignments_for_teacher,
                       get_assignments_for_student, submit_assignment,
                       check_submission, get_submissions_for_assignment)
from academics.models import ClassSubject, Section


def _is_staff_or_admin(user):
    return user.is_authenticated and user.role.lower() in ("admin", "staff")

def _is_student(user):
    return user.is_authenticated and user.role.lower() == "student"

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

def _require_not_principal(view_func):
    """Block principals from assignment write views."""
    @functools.wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if _is_principal(request.user):
            messages.warning(request, "Principals have read-only access. Assignment management is for teachers and admins.")
            return redirect("accounts:principal_dashboard")
        return view_func(request, *args, **kwargs)
    return _wrapped


@login_required
@user_passes_test(_is_staff_or_admin)
def teacher_dashboard(request):
    assignments = get_assignments_for_teacher(request.user)
    return render(request, "assignments/teacher_dashboard.html", {"assignments": assignments})


@login_required
@user_passes_test(_is_staff_or_admin)
@_require_not_principal
def create(request):
    if request.method == "POST":
        cs  = get_object_or_404(ClassSubject, pk=request.POST.get("class_subject"))
        sec = get_object_or_404(Section, pk=request.POST.get("section"))
        create_assignment(request.user, cs, sec,
                          request.POST.get("title"), request.POST.get("description"),
                          request.POST.get("due_date"), int(request.POST.get("max_marks", 10)))
        messages.success(request, "Assignment created.")
        return redirect("assignments:teacher_dashboard")
    subjects = ClassSubject.objects.select_related("class_obj", "subject").all()
    sections = Section.objects.select_related("class_obj").all()
    return render(request, "assignments/create.html", {"subjects": subjects, "sections": sections})


@login_required
@user_passes_test(_is_staff_or_admin)
@_require_not_principal
def check(request, pk):
    assignment = get_object_or_404(Assignment, pk=pk)
    # Only the assignment's teacher (or admin) can grade submissions
    if request.user.role.lower() != "admin" and assignment.teacher != request.user:
        messages.error(request, "You can only grade your own assignments.")
        return redirect("assignments:teacher_dashboard")
    submissions = get_submissions_for_assignment(pk)
    if request.method == "POST":
        sub_pk = request.POST.get("submission_id")
        check_submission(sub_pk, request.user,
                         request.POST.get("marks"), request.POST.get("grade"),
                         request.POST.get("feedback", ""))
        messages.success(request, "Submission checked.")
    return render(request, "assignments/check.html", {"assignment": assignment, "submissions": submissions})


@login_required
@user_passes_test(_is_student)
def student_list(request):
    from students.models import StudentProfile
    try:
        sp = StudentProfile.objects.get(user=request.user)
    except StudentProfile.DoesNotExist:
        return redirect("accounts:student_dashboard")
    assignments = get_assignments_for_student(sp)
    return render(request, "assignments/student_list.html", {"assignments": assignments})


@login_required
@user_passes_test(_is_student)
def submit(request, pk):
    assignment = get_object_or_404(Assignment, pk=pk)
    from students.models import StudentProfile
    try:
        sp = StudentProfile.objects.get(user=request.user)
    except StudentProfile.DoesNotExist:
        return redirect("accounts:student_dashboard")
    # Prevent submission to closed assignments
    if assignment.status == Assignment.Status.CLOSED:
        messages.error(request, "This assignment is closed and no longer accepting submissions.")
        return redirect("assignments:student_list")
    if assignment.due_date < timezone.now().date():
        messages.warning(request, "This assignment is past its due date.")
    if request.method == "POST":
        submit_assignment(assignment, sp, request.POST.get("answer", ""))
        messages.success(request, "Assignment submitted.")
        return redirect("assignments:student_list")
    existing = Submission.objects.filter(assignment=assignment, student=sp).first()
    return render(request, "assignments/submit.html", {"assignment": assignment, "existing": existing})
