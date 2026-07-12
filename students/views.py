from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
import re

from .models import StudentProfile
from .forms import StudentProfileForm, StudentStatusForm
from django.http import JsonResponse
from academics.models import Class, Section, AcademicYear


# ── Role checks ────────────────────────────────────────────────────────────────

def is_admin(user):
    return user.is_authenticated and hasattr(user, "role") and user.role == "admin"


def is_admin_or_staff(user):
    return user.is_authenticated and hasattr(user, "role") and user.role in ("admin", "staff")


# ── Natural sort helper ────────────────────────────────────────────────────────

def _natural_sort_key(cls):
    """
    Sort order: pure-text names first (ECD, Nursery, KG),
    then by first number found (1, Class 1, 2, Class 2, … 10, Class 10).
    """
    nums = re.findall(r'\d+', cls.name.strip())
    if not nums:
        return (0, 0, cls.name.strip().lower())
    return (1, int(nums[0]), cls.name.strip().lower())


def _sorted_classes():
    """Return all Class objects sorted by natural order of their name."""
    return sorted(Class.objects.all(), key=_natural_sort_key)


# ── STUDENT LIST ───────────────────────────────────────────────────────────────

@login_required
@user_passes_test(is_admin_or_staff)
def student_list(request):

    students = StudentProfile.objects.select_related(
        "user",
        "section",
        "section__class_obj",
        "academic_year",
    ).all().order_by("section__class_obj__name", "section__name", "roll_number")

    class_id      = request.GET.get("class")
    year_id       = request.GET.get("year")
    section_id    = request.GET.get("section")
    religion_type = request.GET.get("religion_type")
    search_query  = request.GET.get("q", "").strip()

    if class_id:
        students = students.filter(section__class_obj_id=class_id)
    if year_id:
        students = students.filter(academic_year_id=year_id)
    if section_id:
        students = students.filter(section_id=section_id)
    if religion_type:
        students = students.filter(religion_type=religion_type)
    if search_query:
        students = students.filter(name__icontains=search_query)

    # Only load sections for the chosen class to populate the section dropdown
    if class_id:
        sections = Section.objects.filter(class_obj_id=class_id).order_by("name")
    else:
        sections = Section.objects.none()

    context = {
        "students":     students,
        "classes":      _sorted_classes(),
        "years":        AcademicYear.objects.all(),
        "sections":     Section.objects.select_related("class_obj").all(),
        "filter_sections": sections,
        "search_query": search_query,
        "selected_class":   class_id,
        "selected_year":    year_id,
        "selected_section": section_id,
        "selected_religion": religion_type,
    }
    return render(request, "students/student_list.html", context)


# ── AJAX: get sections for a class ────────────────────────────────────────────

def get_sections(request):
    class_id = request.GET.get("class_id")
    if not class_id:
        return JsonResponse({"sections": []})
    sections = Section.objects.filter(class_obj_id=class_id).order_by("name")
    return JsonResponse({"sections": list(sections.values("id", "name"))})


# ── CREATE STUDENT ─────────────────────────────────────────────────────────────

@login_required
@user_passes_test(is_admin)
def create_student(request):
    form = StudentProfileForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "Student created successfully.")
            return redirect("students:student_list")
    return render(request, "students/create_student.html", {
        "form":    form,
        "classes": _sorted_classes(),
    })


# ── UPDATE STUDENT ─────────────────────────────────────────────────────────────

@login_required
@user_passes_test(is_admin)
def update_student(request, pk):
    student = get_object_or_404(StudentProfile, pk=pk)
    form = StudentProfileForm(request.POST or None, instance=student)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "Student updated successfully.")
            return redirect("students:student_list")
    return render(request, "students/update_student.html", {
        "form":    form,
        "student": student,
    })


# ── DELETE STUDENT ─────────────────────────────────────────────────────────────

@login_required
@user_passes_test(is_admin)
def delete_student(request, pk):
    student = get_object_or_404(StudentProfile, pk=pk)
    if request.method == "POST":
        student.delete()
        messages.success(request, "Student deleted successfully.")
        return redirect("students:student_list")
    return render(request, "students/confirm_delete.html", {"student": student})


# ── STUDENT STATUS UPDATE ──────────────────────────────────────────────────────

@login_required
@user_passes_test(is_admin)
def update_student_status(request, pk):
    student = get_object_or_404(StudentProfile, pk=pk)
    form = StudentStatusForm(request.POST or None, instance=student)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "Status updated successfully.")
            return redirect("students:student_list")
    return render(request, "students/update_status.html", {
        "form":    form,
        "student": student,
    })


# ── STUDENT DETAIL ─────────────────────────────────────────────────────────────

@login_required
def student_detail(request, pk):
    student = get_object_or_404(StudentProfile, pk=pk)
    return render(request, "students/student_detail.html", {"student": student})


# ── MY PROFILE (student sees their own) ───────────────────────────────────────

@login_required
def my_profile(request):
    try:
        student = StudentProfile.objects.get(user=request.user)
        return render(request, "students/student_detail.html", {"student": student})
    except StudentProfile.DoesNotExist:
        messages.error(request, "No student profile is linked to your account.")
        return redirect("accounts:student_dashboard")


# ── PROMOTE STUDENT ────────────────────────────────────────────────────────────

@login_required
@user_passes_test(is_admin)
def promote_student(request, pk):
    """Move student to the next class (natural sort order)."""
    student = get_object_or_404(StudentProfile, pk=pk)

    if request.method == "POST":
        all_classes = _sorted_classes()
        current_class = student.section.class_obj
        class_ids = [c.id for c in all_classes]

        try:
            idx = class_ids.index(current_class.id)
        except ValueError:
            messages.error(request, "Current class not found in sorted list.")
            return redirect("students:student_list")

        if idx >= len(all_classes) - 1:
            messages.warning(
                request,
                f"{student.name or student.student_id} is already in the highest "
                f"class ({current_class.name}). Cannot promote further."
            )
            return redirect("students:student_list")

        next_class = all_classes[idx + 1]

        # Keep same section name if it exists in next class
        next_section = (
            Section.objects.filter(class_obj=next_class, name=student.section.name).first()
            or Section.objects.filter(class_obj=next_class).first()
        )

        if not next_section:
            messages.error(
                request,
                f"No sections found in {next_class.name}. "
                "Please create sections for that class first."
            )
            return redirect("students:student_list")

        current_year = AcademicYear.objects.filter(is_current=True).first()
        old_class = student.section.class_obj.name
        student.section = next_section
        if current_year:
            student.academic_year = current_year
        student.status = StudentProfile.Status.ACTIVE
        student.save()

        messages.success(
            request,
            f"✓ {student.name or student.student_id} promoted from "
            f"{old_class} → {next_class.name} (Section {next_section.name})."
        )

    return redirect("students:student_list")


# ── DOUBLE PROMOTE ─────────────────────────────────────────────────────────────

@login_required
@user_passes_test(is_admin)
def double_promote_student(request, pk):
    """Skip one class, move student two levels up."""
    student = get_object_or_404(StudentProfile, pk=pk)

    if request.method == "POST":
        all_classes = _sorted_classes()
        current_class = student.section.class_obj
        class_ids = [c.id for c in all_classes]

        try:
            idx = class_ids.index(current_class.id)
        except ValueError:
            messages.error(request, "Current class not found.")
            return redirect("students:student_list")

        if idx >= len(all_classes) - 2:
            messages.warning(
                request,
                f"{student.name or student.student_id} cannot be double-promoted — "
                "not enough classes above."
            )
            return redirect("students:student_list")

        target_class = all_classes[idx + 2]
        target_section = (
            Section.objects.filter(class_obj=target_class, name=student.section.name).first()
            or Section.objects.filter(class_obj=target_class).first()
        )

        if not target_section:
            messages.error(request, f"No sections found in {target_class.name}.")
            return redirect("students:student_list")

        current_year = AcademicYear.objects.filter(is_current=True).first()
        old_class    = student.section.class_obj.name
        skipped_class = all_classes[idx + 1].name

        # Guard: roll-number conflict in target section + year
        conflict = StudentProfile.objects.filter(
            section=target_section,
            roll_number=student.roll_number,
            academic_year=current_year,
        ).exclude(pk=student.pk).exists()

        if conflict:
            messages.error(
                request,
                f"Roll number {student.roll_number} already exists in "
                f"{target_class.name} — {target_section.name}. "
                "Please update the roll number before double-promoting."
            )
            return redirect("students:student_list")

        student.section = target_section
        if current_year:
            student.academic_year = current_year
        student.status = StudentProfile.Status.ACTIVE
        student.save()

        messages.success(
            request,
            f"⚡ {student.name or student.student_id} double-promoted from "
            f"{old_class} → {target_class.name} (skipped {skipped_class})."
        )

    return redirect("students:student_list")


# ── FAIL STUDENT ───────────────────────────────────────────────────────────────

@login_required
@user_passes_test(is_admin)
def fail_student(request, pk):
    """Student stays in the same class; academic year updated to current."""
    student = get_object_or_404(StudentProfile, pk=pk)

    if request.method == "POST":
        current_year = AcademicYear.objects.filter(is_current=True).first()
        if current_year:
            student.academic_year = current_year
        student.status = StudentProfile.Status.ACTIVE
        student.save()

        messages.warning(
            request,
            f"⚠ {student.name or student.student_id} has been marked as FAILED and "
            f"will repeat {student.section.class_obj.name} — {student.section.name} "
            f"in {current_year.name if current_year else 'current year'}."
        )

    return redirect("students:student_list")
