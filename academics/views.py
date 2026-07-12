import logging
import functools

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from django.db import transaction
from django.core.exceptions import ValidationError

from .services import (
    AcademicYearService,
    SubjectService,
    ClassSubjectService,
    TeacherAssignmentService,
    RoutineService,
    AcademicAnalyticsService,
    sorted_classes,
)

logger = logging.getLogger(__name__)


# ── Permission helpers ─────────────────────────────────────────────────────────

def _is_principal(user):
    """Returns True if the user is a staff member with designation=principal."""
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
    """
    Decorator: blocks principals (read-only) and non-staff/non-admin users
    from data-entry views (marks entry, bulk uploads, class/section/subject
    management, routine creation, teacher assignment).
    Principals are redirected to their own dashboard.
    """
    @functools.wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        if _is_principal(request.user):
            messages.warning(
                request,
                "Principals have read-only access. "
                "Data entry is performed by administrators and teachers."
            )
            return redirect("accounts:principal_dashboard")
        return view_func(request, *args, **kwargs)
    return _wrapped



# DASHBOARD

@login_required
def academic_dashboard(request):

    from .models import Subject, TeacherSubjectAssignment, ClassRoutine

    try:
        data = {
            "total_subjects":     AcademicAnalyticsService.get_total_subjects(),
            "total_assignments":  AcademicAnalyticsService.get_total_teacher_assignments(),
            "total_routines":     AcademicAnalyticsService.get_total_routines(),
            "current_year":       AcademicAnalyticsService.get_current_academic_year(),
            # Popup data
            "subjects":           Subject.objects.all().order_by("name"),
            "teacher_assignments": TeacherSubjectAssignment.objects.select_related(
                "teacher__user", "class_subject__class_obj",
                "class_subject__subject", "section"
            ).all().order_by("class_subject__class_obj__name"),
            "routines":           ClassRoutine.objects.select_related(
                "class_subject__class_obj", "class_subject__subject",
                "teacher__user", "section", "academic_year"
            ).all().order_by("day", "start_time"),
        }

        return render(request, "academics/dashboard.html", data)

    except Exception:
        logger.exception("Dashboard load failed")
        messages.error(request, "Failed to load dashboard")
        return render(request, "academics/dashboard.html", {})



# ACADEMIC YEAR CREATE

@login_required
@require_write_role
def create_academic_year(request):

    if request.method == "POST":
        try:
            with transaction.atomic():
                AcademicYearService.create_academic_year(
                    name=request.POST.get("name"),
                    start_date=request.POST.get("start_date"),
                    end_date=request.POST.get("end_date"),
                    is_current=request.POST.get("is_current") == "on",
                )

            messages.success(request, "Academic year created successfully")
            return redirect("academics:academic_dashboard")

        except ValidationError as e:
            messages.error(request, str(e))
        except Exception:
            logger.exception("Academic year creation failed")
            messages.error(request, "Something went wrong")

    return render(request, "academics/create_academic_year.html")


# SUBJECT CREATE

@login_required
@require_write_role
def create_subject(request):

    if request.method == "POST":
        try:
            with transaction.atomic():
                SubjectService.create_subject(
                    code=request.POST.get("code"),
                    name=request.POST.get("name"),
                    credit_hours=request.POST.get("credit_hours", 1),
                    description=request.POST.get("description"),
                )

            messages.success(request, "Subject created successfully")
            return redirect("academics:academic_dashboard")

        except Exception:
            logger.exception("Subject creation failed")
            messages.error(request, "Error creating subject")

    return render(request, "academics/create_subject.html")



# ASSIGN SUBJECT TO CLASS

@login_required
@require_write_role
def assign_subject_to_class(request):

    from .models import AcademicYear, Class, Subject

    if request.method == "POST":
        try:
            with transaction.atomic():
                ClassSubjectService.assign_subject_to_class(
                    academic_year_id=request.POST.get("academic_year"),
                    class_obj_id=request.POST.get("class_obj"),
                    subject_id=request.POST.get("subject"),
                    full_marks=request.POST.get("full_marks", 100),
                    pass_marks=request.POST.get("pass_marks", 40),
                    is_optional=request.POST.get("is_optional") == "on",
                )

            messages.success(request, "Subject assigned successfully")
            return redirect("academics:academic_dashboard")

        except ValidationError as e:
            messages.error(request, str(e))
        except Exception:
            logger.exception("Assignment failed")
            messages.error(request, "Something went wrong")

    return render(request, "academics/assign_subject.html", {
        "academic_years": AcademicYear.objects.all().order_by("-start_date"),
        "classes":        sorted_classes(),
        "subjects":       Subject.objects.all().order_by("name"),
    })



# TEACHER ASSIGNMENT

@login_required
@require_write_role
def assign_teacher(request):

    from .models import ClassSubject, Section
    from staff.models import StaffProfile

    if request.method == "POST":
        try:
            with transaction.atomic():
                TeacherAssignmentService.assign_teacher(
                    teacher_id=request.POST.get("teacher"),
                    class_subject_id=request.POST.get("class_subject"),
                    section_id=request.POST.get("section"),
                    is_class_teacher=request.POST.get("is_class_teacher") == "on",
                    remarks=request.POST.get("remarks"),
                )

            messages.success(request, "Teacher assigned successfully")
            return redirect("academics:academic_dashboard")

        except ValidationError as e:
            messages.error(request, str(e))
        except Exception:
            logger.exception("Teacher assignment failed")
            messages.error(request, "Error assigning teacher")

    return render(request, "academics/assign_teacher.html", {
        "teachers":       StaffProfile.objects.select_related("user").all().order_by("staff_id"),
        "class_subjects": ClassSubject.objects.select_related("class_obj", "subject").all().order_by("class_obj__name"),
        "sections":       Section.objects.select_related("class_obj").all().order_by("class_obj__name", "name"),
    })



# ROUTINE CREATE

@login_required
@require_write_role
def create_routine(request):

    from .models import AcademicYear, ClassSubject, Section
    from staff.models import StaffProfile

    if request.method == "POST":
        try:
            with transaction.atomic():
                RoutineService.create_routine(
                    academic_year_id=request.POST.get("academic_year"),
                    class_subject_id=request.POST.get("class_subject"),
                    teacher_id=request.POST.get("teacher"),
                    section_id=request.POST.get("section"),
                    day=request.POST.get("day"),
                    start_time=request.POST.get("start_time"),
                    end_time=request.POST.get("end_time"),
                    room=request.POST.get("room"),
                )

            messages.success(request, "Routine created successfully")
            return redirect("academics:academic_dashboard")

        except ValidationError as e:
            messages.error(request, str(e))
        except Exception:
            logger.exception("Routine creation failed")
            messages.error(request, "Error creating routine")

    return render(request, "academics/create_routine.html", {
        "academic_years": AcademicYear.objects.all().order_by("-start_date"),
        "class_subjects": ClassSubject.objects.select_related("class_obj", "subject").all().order_by("class_obj__name"),
        "teachers":       StaffProfile.objects.select_related("user").all().order_by("staff_id"),
        "sections":       Section.objects.select_related("class_obj").all().order_by("class_obj__name", "name"),
        "weekdays":       [("sunday","Sunday"),("monday","Monday"),("tuesday","Tuesday"),
                           ("wednesday","Wednesday"),("thursday","Thursday"),
                           ("friday","Friday"),("saturday","Saturday")],
    })


# EXAM TERM — LIST + CREATE

@login_required
def exam_term_list(request):
    """List all exam terms with option to create new ones."""
    from .models import ExamTerm, AcademicYear

    exam_terms = ExamTerm.objects.select_related(
        "academic_year"
    ).all().order_by("-academic_year__start_date", "start_date")

    return render(request, "academics/exam_term_list.html", {
        "exam_terms":     exam_terms,
        "academic_years": AcademicYear.objects.all().order_by("-start_date"),
        "term_types":     [
            ("first",  "First Term"),
            ("second", "Second Term"),
            ("third",  "Third Term"),
            ("final",  "Final Exam"),
        ],
    })


@login_required
def toggle_exam_term_status(request, pk):
    """Toggle the is_published status of an exam term."""
    from .models import ExamTerm

    if request.method == "POST":
        term = get_object_or_404(ExamTerm, pk=pk)
        term.is_published = not term.is_published
        term.save(update_fields=["is_published"])
        status = "Published" if term.is_published else "Unpublished"
        messages.success(request, f'"{term.name}" has been {status}.')

    return redirect("academics:exam_term_list")


@login_required
def create_exam_term(request):
    """Create a new exam term."""
    from .models import ExamTerm, AcademicYear

    if request.method == "POST":
        try:
            with transaction.atomic():
                academic_year = get_object_or_404(
                    AcademicYear, pk=request.POST.get("academic_year")
                )
                start_date = request.POST.get("start_date")
                end_date   = request.POST.get("end_date")

                if start_date >= end_date:
                    raise ValidationError("End date must be after start date.")

                ExamTerm.objects.create(
                    academic_year=academic_year,
                    name=request.POST.get("name"),
                    term_type=request.POST.get("term_type"),
                    start_date=start_date,
                    end_date=end_date,
                    is_published=request.POST.get("is_published") == "on",
                )
                messages.success(request, "Exam term created successfully.")
                return redirect("academics:exam_term_list")

        except ValidationError as e:
            messages.error(request, str(e))
        except Exception:
            logger.exception("Exam term creation failed")
            messages.error(request, "Something went wrong.")

    return render(request, "academics/create_exam_term.html", {
        "academic_years": AcademicYear.objects.all().order_by("-start_date"),
        "term_types": [
            ("first",  "First Term"),
            ("second", "Second Term"),
            ("third",  "Third Term"),
            ("final",  "Final Exam"),
        ],
    })



# MARKS ENTRY — SELECT CLASS/SECTION/TERM

@login_required
@require_write_role
def marks_entry_select(request):
    """
    Teacher selects class, section and exam term to enter marks.
    """
    from .models import ExamTerm, Section, Class, AcademicYear

    return render(request, "academics/marks_entry_select.html", {
        "classes":    sorted_classes(),
        "sections":   Section.objects.select_related("class_obj").all(),
        "exam_terms": ExamTerm.objects.select_related("academic_year").order_by("-academic_year__start_date"),
    })



# MARKS ENTRY — ENTER MARKS FOR A SECTION + TERM

@login_required
@require_write_role
def marks_entry(request):
    """
    Teacher enters theory + practical marks for every student
    in the selected section for a given exam term.
    """
    from .models import (
        ExamTerm, Section, ClassSubject, StudentMark, AcademicYear
    )
    from students.models import StudentProfile

    section_id   = request.GET.get("section_id") or request.POST.get("section_id")
    term_id      = request.GET.get("term_id")    or request.POST.get("term_id")

    section   = None
    exam_term = None
    students  = []
    subjects  = []

    if section_id and term_id:
        section   = get_object_or_404(Section, pk=section_id)
        exam_term = get_object_or_404(ExamTerm, pk=term_id)
        students  = StudentProfile.objects.filter(
            section=section, status="active"
        ).order_by("roll_number")

        # First try: subjects matching the exam term's academic year
        subjects = ClassSubject.objects.filter(
            class_obj=section.class_obj,
            academic_year=exam_term.academic_year,
        ).select_related("subject")

        # Fallback: if no subjects found for that year, show ALL subjects
        # assigned to this class across any year (so teacher can still enter marks)
        if not subjects.exists():
            subjects = ClassSubject.objects.filter(
                class_obj=section.class_obj,
            ).select_related("subject", "academic_year")

    if request.method == "POST" and section and exam_term:
        saved = 0
        errors = []
        for student in students:
            for cs in subjects:
                theory_key    = f"theory_{student.id}_{cs.id}"
                practical_key = f"practical_{student.id}_{cs.id}"
                theory    = request.POST.get(theory_key, "0") or "0"
                practical = request.POST.get(practical_key, "0") or "0"
                try:
                    theory_val    = float(theory)
                    practical_val = float(practical)
                    total         = theory_val + practical_val
                    percentage    = (total / cs.full_marks * 100) if cs.full_marks else 0

                    # Grade
                    if percentage >= 90:   grade, gpa = "A+", 4.0
                    elif percentage >= 80: grade, gpa = "A",  3.6
                    elif percentage >= 70: grade, gpa = "B+", 3.2
                    elif percentage >= 60: grade, gpa = "B",  2.8
                    elif percentage >= 50: grade, gpa = "C",  2.4
                    elif percentage >= 40: grade, gpa = "D",  2.0
                    else:                  grade, gpa = "F",  0.0

                    StudentMark.objects.update_or_create(
                        student=student,
                        exam_term=exam_term,
                        class_subject=cs,
                        defaults={
                            "theory_marks":    theory_val,
                            "practical_marks": practical_val,
                            "total_marks":     total,
                            "percentage":      round(percentage, 2),
                            "grade":           grade,
                            "gpa":             gpa,
                        }
                    )
                    saved += 1
                except Exception as e:
                    errors.append(str(e))

        if errors:
            for err in errors[:3]:
                messages.error(request, err)
        messages.success(request, f"Marks saved for {saved} entries.")
        return redirect(
            f"{request.path}?section_id={section_id}&term_id={term_id}"
        )

    # Pre-load existing marks into a lookup dict
    existing = {}
    existing_json = {}
    if students and subjects:
        for mark in StudentMark.objects.filter(
            student__in=students,
            exam_term=exam_term,
            class_subject__in=subjects,
        ):
            existing[(mark.student_id, mark.class_subject_id)] = mark
            existing_json[f"theory_{mark.student_id}_{mark.class_subject_id}"]    = str(mark.theory_marks)
            existing_json[f"practical_{mark.student_id}_{mark.class_subject_id}"] = str(mark.practical_marks)

    import json
    return render(request, "academics/marks_entry.html", {
        "section":       section,
        "exam_term":     exam_term,
        "students":      students,
        "subjects":      subjects,
        "existing":      existing,
        "existing_json": json.dumps(existing_json),
        "section_id":    section_id,
        "term_id":       term_id,
        "no_subjects_for_year": section and exam_term and not ClassSubject.objects.filter(
            class_obj=section.class_obj,
            academic_year=exam_term.academic_year,
        ).exists(),
    })



# STUDENT MARKS VIEW (read-only for student)

@login_required
def student_marks_view(request):
    """
    Student views their own marks across all terms.
    """
    from .models import StudentMark, ExamTerm
    from students.models import StudentProfile

    try:
        student = StudentProfile.objects.get(user=request.user)
    except StudentProfile.DoesNotExist:
        messages.error(request, "No student profile linked to your account.")
        return redirect("accounts:student_dashboard")

    term_id = request.GET.get("term")
    terms   = ExamTerm.objects.all().order_by("-start_date")
    marks   = StudentMark.objects.filter(student=student).select_related(
        "exam_term", "class_subject__subject"
    ).order_by("exam_term__start_date", "class_subject__subject__name")

    if term_id:
        marks = marks.filter(exam_term_id=term_id)

    return render(request, "academics/student_marks.html", {
        "student": student,
        "marks":   marks,
        "terms":   terms,
        "selected_term": term_id,
    })


# CLASS MANAGEMENT — CREATE / RENAME / DELETE

@login_required
@require_write_role
def manage_classes(request):
    from .models import Class, Section
    classes = sorted_classes(Class.objects.prefetch_related("sections").all())
    if request.method == "POST":
        action = request.POST.get("action")
        try:
            with transaction.atomic():
                if action == "create":
                    name = request.POST.get("name", "").strip()
                    if not name:
                        raise ValidationError("Class name is required.")
                    if Class.objects.filter(name=name).exists():
                        raise ValidationError(f"Class '{name}' already exists.")
                    Class.objects.create(name=name)
                    messages.success(request, f"Class '{name}' created.")
                elif action == "rename":
                    pk   = request.POST.get("pk")
                    name = request.POST.get("name", "").strip()
                    obj  = get_object_or_404(Class, pk=pk)
                    obj.name = name
                    obj.save()
                    messages.success(request, f"Class renamed to '{name}'.")
                elif action == "delete":
                    pk  = request.POST.get("pk")
                    obj = get_object_or_404(Class, pk=pk)
                    obj.delete()
                    messages.success(request, "Class deleted.")
        except ValidationError as e:
            messages.error(request, str(e))
        except Exception as ex:
            messages.error(request, f"Error: {ex}")
        return redirect("academics:manage_classes")
    return render(request, "academics/manage_classes.html", {"classes": classes})



# SECTION MANAGEMENT — CREATE / RENAME / DELETE

@login_required
@require_write_role
def manage_sections(request):
    from .models import Class, Section
    sections = Section.objects.select_related("class_obj").all().order_by("class_obj__name", "name")
    classes  = sorted_classes()
    if request.method == "POST":
        action = request.POST.get("action")
        try:
            with transaction.atomic():
                if action == "create":
                    class_id = request.POST.get("class_obj")
                    name     = request.POST.get("name", "").strip().upper()
                    cls      = get_object_or_404(Class, pk=class_id)
                    if Section.objects.filter(class_obj=cls, name=name).exists():
                        raise ValidationError(f"Section '{name}' already exists in {cls.name}.")
                    Section.objects.create(class_obj=cls, name=name)
                    messages.success(request, f"Section '{name}' added to {cls.name}.")
                elif action == "rename":
                    pk   = request.POST.get("pk")
                    name = request.POST.get("name", "").strip().upper()
                    obj  = get_object_or_404(Section, pk=pk)
                    obj.name = name
                    obj.save()
                    messages.success(request, f"Section renamed to '{name}'.")
                elif action == "delete":
                    pk  = request.POST.get("pk")
                    obj = get_object_or_404(Section, pk=pk)
                    obj.delete()
                    messages.success(request, "Section deleted.")
        except ValidationError as e:
            messages.error(request, str(e))
        except Exception as ex:
            messages.error(request, f"Error: {ex}")
        return redirect("academics:manage_sections")
    return render(request, "academics/manage_sections.html", {"sections": sections, "classes": classes})



# SUBJECT MANAGEMENT — CREATE / RENAME / DELETE

@login_required
@require_write_role
def manage_subjects(request):
    from .models import Subject
    subjects = Subject.objects.all().order_by("name")
    if request.method == "POST":
        action = request.POST.get("action")
        try:
            with transaction.atomic():
                if action == "create":
                    code  = request.POST.get("code", "").strip()
                    name  = request.POST.get("name", "").strip()
                    credit = int(request.POST.get("credit_hours", 1) or 1)
                    desc  = request.POST.get("description", "")
                    if not code or not name:
                        raise ValidationError("Code and name are required.")
                    Subject.objects.create(code=code, name=name, credit_hours=credit, description=desc)
                    messages.success(request, f"Subject '{name}' created.")
                elif action == "rename":
                    pk   = request.POST.get("pk")
                    name = request.POST.get("name", "").strip()
                    code = request.POST.get("code", "").strip()
                    obj  = get_object_or_404(Subject, pk=pk)
                    obj.name = name
                    if code:
                        obj.code = code
                    obj.save()
                    messages.success(request, f"Subject updated to '{name}'.")
                elif action == "delete":
                    pk  = request.POST.get("pk")
                    obj = get_object_or_404(Subject, pk=pk)
                    obj.delete()
                    messages.success(request, "Subject deleted.")
        except ValidationError as e:
            messages.error(request, str(e))
        except Exception as ex:
            messages.error(request, f"Error: {ex}")
        return redirect("academics:manage_subjects")
    return render(request, "academics/manage_subjects.html", {"subjects": subjects})



# BULK UPLOAD — STUDENTS (CSV/Excell)

@login_required
@require_write_role
def bulk_upload_students(request):
    from .models import Section, AcademicYear, Class
    from students.models import StudentProfile
    import io

    classes        = sorted_classes()
    sections       = Section.objects.select_related("class_obj").all().order_by("class_obj__name", "name")
    academic_years = AcademicYear.objects.all().order_by("-start_date")

    # Filter sections by selected class
    selected_class_id = request.POST.get("class_id") or request.GET.get("class_id")
    if selected_class_id:
        sections = sections.filter(class_obj_id=selected_class_id)

    if request.method == "POST":
        excel_file = request.FILES.get("excel_file")
        section_id = request.POST.get("section_id")
        year_id    = request.POST.get("academic_year_id")

        if not excel_file or not section_id:
            messages.error(request, "Excel file and section are required.")
        else:
            section = get_object_or_404(Section, pk=section_id)
            year    = AcademicYear.objects.filter(pk=year_id).first() if year_id else None
            try:
                import openpyxl
                wb = openpyxl.load_workbook(io.BytesIO(excel_file.read()))
                ws = wb.active
                headers = [str(c.value).strip().lower() if c.value else "" for c in next(ws.iter_rows(min_row=1, max_row=1))]
                created = 0
                errors  = []
                for row in ws.iter_rows(min_row=2, values_only=True):
                    row_dict = dict(zip(headers, row))
                    try:
                        roll = str(row_dict.get("roll_number", "") or "").strip()
                        name = str(row_dict.get("name", "") or "").strip()
                        if not roll:
                            errors.append(f"Row missing roll_number: {row_dict}")
                            continue
                        if StudentProfile.objects.filter(section=section, roll_number=roll).exists():
                            errors.append(f"Roll {roll} already exists in {section}")
                            continue
                        StudentProfile.objects.create(
                            section=section,
                            roll_number=roll,
                            name=name or None,
                            gender=str(row_dict.get("gender", "male") or "male").strip().lower() or "male",
                            academic_year=year,
                            status="active",
                        )
                        created += 1
                    except Exception as e:
                        errors.append(f"Row {row_dict}: {e}")
                messages.success(request, f"Created {created} students.")
                for e in errors[:5]:
                    messages.warning(request, e)
            except Exception as e:
                messages.error(request, f"Failed to read Excel file: {e}")
        return redirect("academics:bulk_upload_students")

    return render(request, "academics/bulk_upload_students.html", {
        "classes":        classes,
        "sections":       sections,
        "academic_years": academic_years,
        "selected_class_id": selected_class_id or "",
        "sample_headers": "roll_number | name | gender",
    })



# BULK UPLOAD — MARKS (CSV/Excell)

@login_required
@require_write_role
def bulk_upload_marks(request):
    from .models import ExamTerm, Section, ClassSubject, StudentMark, Class
    from students.models import StudentProfile
    import io

    classes    = sorted_classes()
    sections   = Section.objects.select_related("class_obj").all().order_by("class_obj__name", "name")
    exam_terms = ExamTerm.objects.select_related("academic_year").order_by("-academic_year__start_date")

    selected_class_id = request.POST.get("class_id") or request.GET.get("class_id")
    if selected_class_id:
        sections = sections.filter(class_obj_id=selected_class_id)

    if request.method == "POST":
        excel_file = request.FILES.get("excel_file")
        section_id = request.POST.get("section_id")
        term_id    = request.POST.get("term_id")

        if not excel_file or not section_id or not term_id:
            messages.error(request, "Excel file, section, and exam term are required.")
        else:
            section   = get_object_or_404(Section, pk=section_id)
            exam_term = get_object_or_404(ExamTerm, pk=term_id)
            subjects  = ClassSubject.objects.filter(
                class_obj=section.class_obj,
                academic_year=exam_term.academic_year,
            ).select_related("subject")
            if not subjects.exists():
                subjects = ClassSubject.objects.filter(
                    class_obj=section.class_obj
                ).select_related("subject", "academic_year")

            subj_map = {cs.subject.name.lower(): cs for cs in subjects}

            try:
                import openpyxl
                wb = openpyxl.load_workbook(io.BytesIO(excel_file.read()))
                ws = wb.active
                headers = [str(c.value).strip().lower() if c.value else "" for c in next(ws.iter_rows(min_row=1, max_row=1))]
                saved  = 0
                errors = []
                for row in ws.iter_rows(min_row=2, values_only=True):
                    row_dict = dict(zip(headers, row))
                    try:
                        roll    = str(row_dict.get("roll_number", "") or "").strip()
                        subj_nm = str(row_dict.get("subject", "") or "").strip().lower()
                        theory  = float(row_dict.get("theory_marks", 0) or 0)
                        prac    = float(row_dict.get("practical_marks", 0) or 0)

                        student = StudentProfile.objects.filter(
                            section=section, roll_number=roll, status="active"
                        ).first()
                        if not student:
                            errors.append(f"Student roll {roll} not found in {section}")
                            continue
                        cs = subj_map.get(subj_nm)
                        if not cs:
                            errors.append(f"Subject '{subj_nm}' not found for {section.class_obj.name}")
                            continue

                        total      = theory + prac
                        percentage = (total / cs.full_marks * 100) if cs.full_marks else 0
                        if percentage >= 90:   grade, gpa = "A+", 4.0
                        elif percentage >= 80: grade, gpa = "A",  3.6
                        elif percentage >= 70: grade, gpa = "B+", 3.2
                        elif percentage >= 60: grade, gpa = "B",  2.8
                        elif percentage >= 50: grade, gpa = "C",  2.4
                        elif percentage >= 40: grade, gpa = "D",  2.0
                        else:                  grade, gpa = "F",  0.0

                        StudentMark.objects.update_or_create(
                            student=student, exam_term=exam_term, class_subject=cs,
                            defaults={
                                "theory_marks": theory, "practical_marks": prac,
                                "total_marks": total, "percentage": round(percentage, 2),
                                "grade": grade, "gpa": gpa,
                            }
                        )
                        saved += 1
                    except Exception as e:
                        errors.append(f"Row {row_dict}: {e}")
                messages.success(request, f"Saved {saved} mark entries.")
                for e in errors[:5]:
                    messages.warning(request, e)
            except Exception as e:
                messages.error(request, f"Failed to read Excel file: {e}")
        return redirect("academics:bulk_upload_marks")

    return render(request, "academics/bulk_upload_marks.html", {
        "classes":          classes,
        "sections":         sections,
        "exam_terms":       exam_terms,
        "selected_class_id": selected_class_id or "",
        "sample_headers":   "roll_number | subject | theory_marks | practical_marks",
    })



# BULK UPLOAD — STAFF / TEACHERS (CSV/Excell)

@login_required
@require_write_role
def bulk_upload_staff(request):
    from staff.models import StaffProfile, Department, Designation
    from accounts.models import User
    import csv, io, re

    departments = Department.objects.all().order_by("name")

    if request.method == "POST":
        csv_file = request.FILES.get("csv_file")
        if not csv_file:
            messages.error(request, "CSV file is required.")
        else:
            try:
                decoded = csv_file.read().decode("utf-8")
                reader  = csv.DictReader(io.StringIO(decoded))
                created = 0
                errors  = []
                for row in reader:
                    try:
                        username    = str(row.get("username", "")).strip()
                        email       = str(row.get("email", "")).strip()
                        designation = str(row.get("designation", "teacher")).strip().lower()
                        dept_name   = str(row.get("department", "")).strip()
                        password    = str(row.get("password", username)).strip() or username

                        if not username or not email:
                            errors.append(f"Row missing username/email: {row}")
                            continue
                        if User.objects.filter(username=username).exists():
                            errors.append(f"Username '{username}' already exists.")
                            continue

                        dept = None
                        if dept_name:
                            dept, _ = Department.objects.get_or_create(name=dept_name)

                        user = User.objects.create_user(
                            username=username, email=email,
                            password=password, role=User.Role.STAFF, is_active=True,
                        )
                        StaffProfile.objects.create(
                            user=user,
                            designation=designation if designation in dict(Designation.choices) else "teacher",
                            department=dept,
                        )
                        created += 1
                    except Exception as e:
                        errors.append(f"Row {row}: {e}")
                messages.success(request, f"Created {created} staff members.")
                if errors:
                    for e in errors[:5]:
                        messages.warning(request, e)
            except Exception as e:
                messages.error(request, f"Failed to parse CSV: {e}")
        return redirect("academics:bulk_upload_staff")

    return render(request, "academics/bulk_upload_staff.html", {
        "departments": departments,
        "sample_headers": "username,email,designation,department,password",
        "designations": [("teacher","Teacher"),("principal","Principal"),("vice_principal","Vice Principal"),
                         ("lab_assistant","Lab Assistant"),("admin_staff","Admin Staff")],
    })
