import random
import string
import hashlib
import io

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache
from django.http import HttpResponse

from accounts.models import User
from students.models import StudentProfile
from staff.models import StaffProfile
from attendance.models import StudentAttendance, AttendanceStatus
from django.utils import timezone

from .forms import (
    LoginForm,
    CustomUserCreationForm,
    CustomUserUpdateForm,
    ChangeCredentialsForm,
)


# ── CAPTCHA image endpoint ────────────────────────────────────────────────────

@never_cache
def captcha_image(request):
    """Generate a fresh CAPTCHA PNG and store the answer hash in session."""
    text = _generate_captcha_text(5)
    request.session['captcha_hash'] = _hash_captcha(text)
    png = _render_captcha_image(text)
    response = HttpResponse(png, content_type="image/png")
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response["Pragma"]        = "no-cache"
    response["Expires"]       = "0"
    return response


# ── CAPTCHA helpers ────────────────────────────────────────────────────────────

_CAPTCHA_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I ambiguity

def _generate_captcha_text(length=5):
    return "".join(random.choices(_CAPTCHA_CHARS, k=length))


def _hash_captcha(text):
    return hashlib.sha256(text.upper().encode()).hexdigest()


def _render_captcha_image(text):
    """
    Professional, human-readable CAPTCHA.
    - Large bold characters, clearly readable by a human
    - Each char has a unique dark colour (high contrast on light background)
    - Slight per-character rotation ±10° — enough to beat OCR
    - Clean gradient background rendered efficiently via numpy-free method
    - 3 thin crossing lines + 20 noise dots (bot deterrent only)
    - Rendered at 2× resolution, downsampled with LANCZOS → crisp edges
    - NO wave distortion, NO gaussian blur, NO grid overlay
    """
    from PIL import Image, ImageDraw, ImageFont

    SCALE = 2
    W, H  = 200, 62          # final output size (px)
    WS    = W * SCALE        # working canvas size
    HS    = H * SCALE

    # ── Background: horizontal gradient via paste strips ───────────────────
    BG_L = (248, 250, 255)
    BG_R = (232, 238, 252)
    img  = Image.new("RGB", (WS, HS), BG_L)
    # Draw one-pixel-wide vertical strips — fast, no per-pixel loop
    for x in range(WS):
        t   = x / max(WS - 1, 1)
        col = tuple(int(BG_L[c] + (BG_R[c] - BG_L[c]) * t) for c in range(3))
        strip = Image.new("RGB", (1, HS), col)
        img.paste(strip, (x, 0))

    draw = ImageDraw.Draw(img)

    # ── 3 thin crossing lines (very light — not obstructive) ───────────────
    LINE_COL = (185, 198, 222)
    for _ in range(3):
        x1 = random.randint(0, WS // 3)
        y1 = random.randint(0, HS)
        x2 = random.randint(WS * 2 // 3, WS)
        y2 = random.randint(0, HS)
        draw.line([(x1, y1), (x2, y2)], fill=LINE_COL, width=SCALE)

    # ── 20 noise dots ──────────────────────────────────────────────────────
    for _ in range(20):
        x = random.randint(0, WS - 1)
        y = random.randint(0, HS - 1)
        c = random.randint(175, 215)
        draw.point((x, y), fill=(c, c, c + 6))

    # ── Font discovery ─────────────────────────────────────────────────────
    FONT_SIZE    = 40 * SCALE
    FONT_PATHS   = [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/verdanab.ttf",
        "C:/Windows/Fonts/calibrib.ttf",
        "C:/Windows/Fonts/trebucbd.ttf",
        "C:/Windows/Fonts/impact.ttf",
        "C:/Windows/Fonts/georgiab.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]
    working_path = None
    base_font    = None
    for fp in FONT_PATHS:
        try:
            base_font    = ImageFont.truetype(fp, size=FONT_SIZE)
            working_path = fp
            break
        except Exception:
            continue
    if base_font is None:
        base_font = ImageFont.load_default()

    # ── Colour palette: dark, distinct, high contrast ──────────────────────
    PALETTE = [
        (20,  45,  175),   # deep blue
        (165, 18,  18),    # deep red
        (18,  115, 42),    # deep green
        (115, 25,  145),   # deep purple
        (175, 85,   8),    # deep amber
        (8,   125, 150),   # deep teal
    ]

    # ── Draw characters ─────────────────────────────────────────────────────
    n      = len(text)
    cell_w = WS // n

    for i, ch in enumerate(text):
        colour = PALETTE[i % len(PALETTE)]

        # Size variation ±3px (at scale)
        size_var = random.randint(-3, 3) * SCALE
        try:
            ch_font = (
                ImageFont.truetype(working_path, size=FONT_SIZE + size_var)
                if working_path else base_font
            )
        except Exception:
            ch_font = base_font

        # Measure on a scratch draw to get precise bbox
        tmp_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        try:
            bb = tmp_draw.textbbox((0, 0), ch, font=ch_font)
            tw = bb[2] - bb[0]
            th = bb[3] - bb[1]
        except Exception:
            tw = th = FONT_SIZE

        # Render char onto transparent cell for clean rotation
        cell_img  = Image.new("RGBA", (cell_w, HS), (0, 0, 0, 0))
        cell_draw = ImageDraw.Draw(cell_img)

        cx = max(0, (cell_w - tw) // 2)
        cy = max(0, (HS - th) // 2) + random.randint(-3, 3) * SCALE

        # Shadow (depth)
        shadow = tuple(max(0, c - 55) for c in colour) + (100,)
        cell_draw.text((cx + SCALE, cy + SCALE), ch, fill=shadow,           font=ch_font)
        cell_draw.text((cx,         cy),          ch, fill=colour + (255,),  font=ch_font)

        # Rotate ±10° — readable for humans, confusing for OCR
        angle    = random.uniform(-10, 10)
        cell_img = cell_img.rotate(angle, resample=Image.BICUBIC, expand=False)

        img.paste(cell_img, (i * cell_w, 0), cell_img)

    # ── Downsample 2× → final size (LANCZOS = sharpest) ────────────────────
    out = img.resize((W, H), resample=Image.LANCZOS)

    # ── Thin border ─────────────────────────────────────────────────────────
    border = ImageDraw.Draw(out)
    border.rectangle([(0, 0), (W - 1, H - 1)], outline=(195, 205, 225), width=1)

    buf = io.BytesIO()
    out.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.read()





# ROLE CHECKERS

def is_admin(user):
    return (
        user.is_authenticated
        and user.role.lower() == "admin"
    )


def is_staff_user(user):
    return (
        user.is_authenticated
        and user.role.lower() == "staff"
    )


def is_student(user):
    return (
        user.is_authenticated
        and user.role.lower() == "student"
    )


def is_accountant(user):
    return (
        user.is_authenticated
        and user.role.lower() == "accountant"
    )


def is_principal(user):
    """
    Principal = a staff user whose StaffProfile.designation == 'principal'.
    They log in with role='staff' but are routed to the principal dashboard.
    """
    if not user.is_authenticated or user.role.lower() != "staff":
        return False
    try:
        from staff.models import StaffProfile, Designation
        return StaffProfile.objects.filter(
            user=user, designation=Designation.PRINCIPAL
        ).exists()
    except Exception:
        return False


def _is_staff_not_principal(user):
    """True for staff who are NOT the principal — used to guard staff_dashboard."""
    if not user.is_authenticated or user.role.lower() != "staff":
        return False
    return not is_principal(user)



# ROLE-BASED REDIRECT ENGINE

def redirect_user_by_role(user):
    """
    Enterprise role-based routing system.
    """

    role = user.role.lower()


    if role == "admin":
        return redirect("accounts:dashboard")

    
    elif role == "staff":
        # Principal is a staff user with designation=principal → own dashboard
        if is_principal(user):
            return redirect("accounts:principal_dashboard")
        return redirect("accounts:staff_dashboard")

    
    elif role == "student":
        return redirect("accounts:student_dashboard")

    elif role == "parent":
        return redirect("parent_portal:dashboard")

    
    elif role == "accountant":
        return redirect("accounts:accountant_dashboard")

    
    return redirect("accounts:login")



# LOGIN VIEW

@never_cache
@require_http_methods(["GET", "POST"])
def login_view(request):
    """
    Login with canvas CAPTCHA verification.
    CAPTCHA image served from /accounts/captcha-image/
    Answer compared against SHA-256 hash stored in session.
    """
    if request.user.is_authenticated:
        return redirect_user_by_role(request.user)

    form = LoginForm(request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            username      = form.cleaned_data.get("username")
            password      = form.cleaned_data.get("password")
            captcha_input = request.POST.get("captcha", "").strip().upper()

            # ── CAPTCHA verification ────────────────────────────────────────
            stored_hash = request.session.get("captcha_hash", "")
            if not stored_hash or _hash_captcha(captcha_input) != stored_hash:
                # Invalidate used/wrong captcha immediately
                request.session.pop("captcha_hash", None)
                messages.error(request, "Incorrect CAPTCHA. Please type the characters shown in the image.")
                return render(request, "accounts/login.html", {"form": form})

            # Invalidate used captcha — single-use
            request.session.pop("captcha_hash", None)

            # ── Rate limit: 5 failed attempts per IP / 60 s ────────────────
            from django.core.cache import cache
            ip        = request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", ""))
            ip        = ip.split(",")[0].strip()
            cache_key = f"login_attempts_{ip}"
            attempts  = cache.get(cache_key, 0)

            if attempts >= 5:
                messages.error(request, "Too many failed attempts. Please wait 60 seconds and try again.")
                return render(request, "accounts/login.html", {"form": form})

            # ── Authenticate ────────────────────────────────────────────────
            user = authenticate(request, username=username, password=password)

            if user is not None:
                cache.delete(cache_key)
                if not user.is_active:
                    messages.error(request, "This account has been deactivated. Contact your administrator.")
                    return render(request, "accounts/login.html", {"form": form})
                login(request, user)
                messages.success(request, f"Welcome back, {user.get_full_name() or user.username}.")
                return redirect_user_by_role(user)

            cache.set(cache_key, attempts + 1, timeout=60)
            remaining = 5 - (attempts + 1)
            if remaining > 0:
                messages.error(request, f"Invalid username or password. {remaining} attempt(s) remaining before lockout.")
            else:
                messages.error(request, "Account temporarily locked due to too many failed attempts. Try again in 60 seconds.")

    return render(request, "accounts/login.html", {"form": form})



# LOGOUT VIEW

@login_required
@require_http_methods(["POST"])
def logout_view(request):

    logout(request)

    messages.success(
        request,
        "Logged out successfully."
    )

    return redirect("accounts:login")



# ADMIN DASHBOARD

@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    from academics.models import AcademicYear, Class, Section
    from academics.services import sorted_classes as _ac_sorted_classes
    from students.models import StudentProfile


    total_users      = User.objects.count()
    total_students   = StudentProfile.objects.filter(status="active").count()
    total_staff      = User.objects.filter(role=User.Role.STAFF).count()
    attendance_today = StudentAttendance.objects.filter(
        date=timezone.now().date(),
        status=AttendanceStatus.PRESENT
    ).count()

   
    academic_years = AcademicYear.objects.all().order_by("-start_date")
    classes        = _ac_sorted_classes(Class.objects.prefetch_related("sections").all())
    sections       = Section.objects.select_related("class_obj").all().order_by("class_obj__name", "name")

   
    class_list = []
    for cls in classes:
        count = StudentProfile.objects.filter(
            section__class_obj=cls, status="active"
        ).count()
        class_list.append({
            "id":       cls.id,
            "name":     cls.name,
            "sections": list(cls.sections.all()),
            "student_count": count,
        })

    
    section_list = []
    for sec in sections:
        count = StudentProfile.objects.filter(
            section=sec, status="active"
        ).count()
        section_list.append({
            "id":         sec.id,
            "name":       sec.name,
            "class_name": sec.class_obj.name,
            "student_count": count,
        })

    context = {
        "total_users":      total_users,
        "total_students":   total_students,
        "total_staff":      total_staff,
        "attendance_today": attendance_today,
        # overview popup data
        "academic_years":          academic_years,
        "classes":                 classes,
        "sections":                sections,
        "class_list":              class_list,
        "section_list":            section_list,
        "total_classes":           len(class_list),
        "total_sections":          sections.count(),
        "total_academic_years":    academic_years.count(),
        "current_academic_year":   academic_years.filter(is_current=True).first(),
        # users for reset password popup (non-admin users only)
        "users_for_reset": User.objects.exclude(role="admin").order_by("role", "username")[:30],
    }

    # ── Notification stats for dashboard widget ────────────────────────────
    try:
        from notifications.models import Notification
        from django.utils import timezone as tz
        from datetime import timedelta
        from notifications.services import unread_count
        last_7 = tz.now() - timedelta(days=7)
        context["notif_total_sent"]  = Notification.objects.count()
        context["notif_sent_week"]   = Notification.objects.filter(created_at__gte=last_7).count()
        context["notif_recent"]      = Notification.objects.select_related("sender").order_by("-created_at")[:5]
        context["admin_unread"]      = unread_count(request.user)
        context["events_info"]       = [
            ("Result Published",  "Auto-notifies students & parents when ExamTerm.is_published flips True"),
            ("Meeting Scheduled", "Notifies selected audience when a meeting is created with notify toggle on"),
            ("Letter Published",  "Notifies selected audience when a school letter is published"),
            ("Student Enrolled",  "Notifies admins when a new student profile is created"),
        ]
    except Exception:
        pass

    return render(request, "accounts/admins.html", context)




@login_required
@user_passes_test(is_staff_user)
def staff_dashboard(request):
    # Principals have their own dashboard — redirect them away
    if is_principal(request.user):
        return redirect("accounts:principal_dashboard")
    from staff.models import StaffProfile
    from academics.models import TeacherSubjectAssignment, ClassRoutine, ExamTerm, AcademicYear
    from attendance.models import StaffAttendance, AttendanceStatus, StudentAttendance
    from students.models import StudentProfile
    from assignments.models import Assignment, Submission
    from notifications.models import NotificationRecipient
    from django.utils import timezone

    today = timezone.now().date()
    current_year = AcademicYear.objects.filter(is_current=True).first()

    # Get staff profile
    staff_profile = None
    try:
        staff_profile = StaffProfile.objects.select_related(
            "department", "user"
        ).get(user=request.user)
    except StaffProfile.DoesNotExist:
        pass

    context = {"staff_profile": staff_profile}

    if staff_profile:
        # Subjects this teacher is assigned to
        assignments_qs = TeacherSubjectAssignment.objects.filter(
            teacher=staff_profile
        ).select_related("class_subject__subject", "class_subject__class_obj", "section")

        assigned_subjects = list(assignments_qs)

        # Today's class routine
        weekday_map = {0: "monday", 1: "tuesday", 2: "wednesday",
                       3: "thursday", 4: "friday", 5: "saturday", 6: "sunday"}
        today_weekday = weekday_map.get(today.weekday(), "monday")
        todays_classes = ClassRoutine.objects.filter(
            teacher=staff_profile,
            day=today_weekday,
        ).select_related(
            "class_subject__subject", "section"
        ).order_by("start_time") if current_year else []

        # Own attendance today
        own_attendance_today = StaffAttendance.objects.filter(
            staff=staff_profile, date=today
        ).first()

        # Students in classes this teacher teaches
        section_ids = assignments_qs.values_list("section_id", flat=True).distinct()
        total_students_taught = StudentProfile.objects.filter(
            section_id__in=section_ids, status="active"
        ).count()

        # Attendance marked today for teacher's sections
        attendance_today_count = StudentAttendance.objects.filter(
            student__section_id__in=section_ids, date=today
        ).count()

        # Pending assignments (created by this user, awaiting submissions)
        my_assignments = Assignment.objects.filter(
            teacher=request.user, status="published"
        ).order_by("-due_date")[:5]

        pending_checks = Submission.objects.filter(
            assignment__teacher=request.user, checked_at__isnull=True
        ).count()

        # Unread notifications
        unread_notifications = NotificationRecipient.objects.filter(
            user=request.user, is_read=False
        ).count()

        # Active exam terms
        active_terms = ExamTerm.objects.filter(
            is_published=False,
            academic_year=current_year
        ).order_by("start_date")[:3] if current_year else []

        # ── Teacher own recommendations (personalised, plain language) ──
        teacher_own_recs = []
        try:
            from analytics.services import run_analytics_for_all_students
            from analytics.presentation_helpers import build_teacher_own_recommendations
            all_data = run_analytics_for_all_students().get("data", [])
            teacher_own_recs = build_teacher_own_recommendations(staff_profile, all_data)
        except Exception:
            teacher_own_recs = []

        context.update({
            "assigned_subjects":       assigned_subjects,
            "todays_classes":          todays_classes,
            "own_attendance_today":    own_attendance_today,
            "total_students_taught":   total_students_taught,
            "attendance_today_count":  attendance_today_count,
            "my_assignments":          my_assignments,
            "pending_checks":          pending_checks,
            "unread_notifications":    unread_notifications,
            "active_terms":            active_terms,
            "current_year":            current_year,
            "today":                   today,
            "today_weekday":           today_weekday.capitalize(),
            "teacher_own_recs":        teacher_own_recs,
        })

    return render(request, "accounts/staff_dashboard.html", context)



@login_required
@user_passes_test(is_accountant)
def accountant_dashboard(request):
    from staff.models import StaffProfile
    from students.models import StudentProfile
    from django.db.models import Sum, Count

    # Real staff count and salary totals
    total_staff = StaffProfile.objects.filter(is_active=True).count()
    total_salary = StaffProfile.objects.filter(
        is_active=True, salary__isnull=False
    ).aggregate(total=Sum("salary"))["total"] or 0

    total_students = StudentProfile.objects.filter(status="active").count()

    return render(
        request,
        "accounts/accountant_dashboard.html",
        {
            "total_salary":    total_salary,
            "total_staff":     total_staff,
            "total_students":  total_students,
        }
    )



@login_required
@user_passes_test(is_student)
def student_dashboard(request):
    """
    Student dashboard — passes student profile + live stats to template.
    """
    from students.models import StudentProfile
    from academics.models import StudentMark, ExamTerm
    from attendance.models import StudentAttendance, AttendanceStatus
    from reporting_system.models import StudentResult
    from notifications.models import NotificationRecipient
    from assignments.models import Assignment, Submission

    student_profile = None
    context = {}

    try:
        student_profile = StudentProfile.objects.select_related(
            "section", "section__class_obj", "academic_year"
        ).get(user=request.user)
    except StudentProfile.DoesNotExist:
        pass

    if student_profile:
        # Marks count
        total_marks = StudentMark.objects.filter(student=student_profile).count()

        # Attendance percentage
        total_att = StudentAttendance.objects.filter(student=student_profile).count()
        present_att = StudentAttendance.objects.filter(
            student=student_profile,
            status__in=[AttendanceStatus.PRESENT, AttendanceStatus.LATE]
        ).count()
        att_pct = round((present_att / total_att * 100), 1) if total_att > 0 else 0.0

        # Latest published result
        latest_result = StudentResult.objects.filter(
            student=student_profile,
            exam_term__is_published=True
        ).select_related("exam_term").order_by("-exam_term__start_date").first()

        # Unread notifications
        unread_notif = NotificationRecipient.objects.filter(
            user=request.user, is_read=False
        ).count()

        # Pending assignments (published, not yet submitted)
        pending_assignments_count = max(0,
            Assignment.objects.filter(
                class_subject__class_obj=student_profile.section.class_obj,
                section=student_profile.section,
                status="published",
            ).exclude(
                submissions__student=student_profile
            ).count()
        )

        context.update({
            "total_marks":        total_marks,
            "attendance_pct":     att_pct,
            "total_attendance":   total_att,
            "latest_result":      latest_result,
            "unread_notif":       unread_notif,
            "pending_assignments": pending_assignments_count,
        })

    context["student_profile"] = student_profile

    return render(request, "accounts/student_dashboard.html", context)



@login_required
@user_passes_test(is_admin)
def user_list(request):

    users = User.objects.all().order_by(
        "-created_at"
    )

    return render(
        request,
        "accounts/user_list.html",
        {"users": users}
    )



@login_required
@user_passes_test(is_admin)
@require_http_methods(["GET", "POST"])
def create_user(request):

    form = CustomUserCreationForm(
        request.POST or None
    )

    if request.method == "POST":

        if form.is_valid():

            created_user = form.save()

            messages.success(
                request,
                f"User '{created_user.username}' created successfully."
            )

            return redirect("accounts:user_list")

    return render(
        request,
        "accounts/create_user.html",
        {"form": form}
    )



@login_required
@user_passes_test(is_admin)
@require_http_methods(["GET", "POST"])
def update_user(request, pk):

    user_obj = get_object_or_404(
        User,
        pk=pk
    )

    form = CustomUserUpdateForm(
        request.POST or None,
        instance=user_obj
    )

    if request.method == "POST":

        if form.is_valid():

            form.save()

            messages.success(
                request,
                "User updated successfully."
            )

            return redirect("accounts:user_list")

    return render(
        request,
        "accounts/update_user.html",
        {
            "form": form,
            "user_obj": user_obj
        }
    )



@login_required
@user_passes_test(is_admin)
@require_http_methods(["GET", "POST"])
def delete_user(request, pk):

    user_obj = get_object_or_404(
        User,
        pk=pk
    )

    if request.method == "POST":

        username = user_obj.username

        user_obj.delete()

        messages.success(
            request,
            f"User '{username}' deleted successfully."
        )

        return redirect("accounts:user_list")

    return render(
        request,
        "accounts/confirm_delete.html",
        {"user": user_obj}
    )



@login_required
@user_passes_test(is_admin)
def create_student_accounts(request):
    """
    Lists all StudentProfile records that have no linked User account.
    Admin can create login credentials for them in bulk or one by one.
    """
    from students.models import StudentProfile

    students_without_accounts = StudentProfile.objects.filter(
        user__isnull=True
    ).select_related("section", "section__class_obj")

    if request.method == "POST":
        action_type = request.POST.get("action")

        if action_type == "create_one":
            student_id = request.POST.get("student_id")
            student = get_object_or_404(StudentProfile, pk=student_id)
            _create_account_for_student(request, student)

        elif action_type == "create_all":
            count = 0
            for student in students_without_accounts:
                if _create_account_for_student(request, student, silent=True):
                    count += 1
            messages.success(request, f"Created accounts for {count} students.")

        return redirect("accounts:create_student_accounts")

    return render(request, "accounts/create_student_accounts.html", {
        "students": students_without_accounts,
        "total":    students_without_accounts.count(),
    })


def _create_account_for_student(request, student, silent=False):
    """
    Helper: creates a User for a StudentProfile and links them.
    Username = student_id, password = student_id (student must change it).
    """
    import re
    try:
        # Build a safe username from student_id
        base_username = re.sub(r"[^a-zA-Z0-9_]", "", student.student_id or "")
        if not base_username:
            base_username = f"stu{student.pk}"

        # Ensure uniqueness
        username = base_username
        counter  = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

        email = student.email or f"{username}@scholaro.edu"
        # Ensure email uniqueness
        if User.objects.filter(email=email).exists():
            email = f"{username}_{student.pk}@scholaro.edu"

        user = User.objects.create_user(
            username=username,
            email=email,
            password=student.student_id,   # default password = student_id
            role=User.Role.STUDENT,
            is_active=True,
        )
        student.user = user
        student.save(update_fields=["user"])

        if not silent:
            messages.success(
                request,
                f"Account created for {student.name or student.student_id} "
                f"— username: {username}, password: {student.student_id}"
            )
        return True
    except Exception as e:
        if not silent:
            messages.error(request, f"Failed for {student}: {e}")
        return False



@login_required
@require_http_methods(["GET", "POST"])
def change_credentials(request):
    """
    Any logged-in user can change their own username and/or password.
    After a password change the session is refreshed so the user stays logged in.
    """
    from django.contrib.auth import update_session_auth_hash

    form = ChangeCredentialsForm(request.user, request.POST or None)

    if request.method == "POST" and form.is_valid():
        form.save()
        # Keep the session alive after password change
        update_session_auth_hash(request, request.user)
        messages.success(request, "Your credentials have been updated successfully.")
        return redirect_user_by_role(request.user)

    return render(request, "accounts/change_credentials.html", {"form": form})



@login_required
@user_passes_test(is_admin)
@require_http_methods(["GET", "POST"])
def reset_user_password(request, pk):
    """
    Admin resets password for any non-admin user.
    Admin cannot reset another admin's password.
    """
    target_user = get_object_or_404(User, pk=pk)

    
    if target_user.role.lower() == "admin" and target_user != request.user:
        messages.error(request, "You cannot reset another admin's password.")
        return redirect("accounts:user_list")

    if request.method == "POST":
        new_password = request.POST.get("new_password", "").strip()
        confirm_password = request.POST.get("confirm_password", "").strip()

        if not new_password:
            messages.error(request, "Password cannot be empty.")
        elif len(new_password) < 8:
            messages.error(request, "Password must be at least 8 characters.")
        elif new_password != confirm_password:
            messages.error(request, "Passwords do not match.")
        else:
            target_user.set_password(new_password)
            target_user.save()
            # Audit: password reset by admin
            try:
                from audit_log.services import log_password_change
                log_password_change(request, target_user, reset_by=request.user)
            except Exception:
                pass
            messages.success(
                request,
                f"Password for '{target_user.username}' has been reset successfully."
            )
            return redirect("accounts:user_list")

    return render(request, "accounts/reset_password.html", {
        "target_user": target_user,
    })


# =========================================================
# CREATE PARENT ACCOUNT — link to one or more students
# =========================================================
@login_required
@user_passes_test(is_admin)
def create_parent_account(request):
    """
    Admin creates a parent User account and links it to one or more StudentProfiles.
    If a student already has a parent, the new parent is added alongside (supports
    multiple children per parent account).
    """
    from students.models import StudentProfile
    from parent_portal.models import ParentProfile
    from academics.services import sorted_classes

    classes  = sorted_classes()
    students = StudentProfile.objects.select_related(
        "user", "section__class_obj"
    ).filter(status="active").order_by("section__class_obj__name", "roll_number")

    if request.method == "POST":
        # ── Collect form data ──────────────────────────────────────
        username     = request.POST.get("username", "").strip()
        email        = request.POST.get("email", "").strip()
        phone        = request.POST.get("phone", "").strip()
        password     = request.POST.get("password", "").strip() or username
        student_ids  = request.POST.getlist("student_ids")  # multiple children

        # ── Validation ────────────────────────────────────────────
        if not username or not email:
            messages.error(request, "Username and email are required.")
        elif User.objects.filter(username=username).exists():
            messages.error(request, f"Username '{username}' already exists.")
        elif User.objects.filter(email=email).exists():
            messages.error(request, f"Email '{email}' already exists.")
        elif not student_ids:
            messages.error(request, "Please select at least one student (child).")
        else:
            try:
                # Create the User
                parent_user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    role=User.Role.PARENT,
                    is_active=True,
                )
                if phone:
                    parent_user.phone = phone
                    parent_user.save(update_fields=["phone"])

                # Create or get ParentProfile and link children
                profile, _ = ParentProfile.objects.get_or_create(
                    user=parent_user,
                    defaults={"phone": phone},
                )
                selected_students = StudentProfile.objects.filter(pk__in=student_ids)
                for stu in selected_students:
                    profile.children.add(stu)

                messages.success(
                    request,
                    f"Parent account created for '{username}' "
                    f"linked to {selected_students.count()} student(s). "
                    f"Default password: {password}"
                )
                return redirect("accounts:create_parent_account")
            except Exception as e:
                messages.error(request, f"Failed: {e}")

    # List existing parent accounts
    existing_parents = ParentProfile.objects.select_related("user").prefetch_related(
        "children__section__class_obj"
    ).all().order_by("-id")

    return render(request, "accounts/create_parent_account.html", {
        "classes":          classes,
        "students":         students,
        "existing_parents": existing_parents,
    })


# =========================================================
# MANAGE PARENT — add/remove children from existing parent
# =========================================================
@login_required
@user_passes_test(is_admin)
def manage_parent_children(request, pk):
    """Add or remove children from an existing parent account."""
    from students.models import StudentProfile
    from parent_portal.models import ParentProfile

    profile  = get_object_or_404(ParentProfile, pk=pk)
    students = StudentProfile.objects.select_related(
        "section__class_obj"
    ).filter(status="active")

    if request.method == "POST":
        student_ids = request.POST.getlist("student_ids")
        profile.children.set(StudentProfile.objects.filter(pk__in=student_ids))
        messages.success(request, f"Children updated for {profile.user.username}.")
        return redirect("accounts:create_parent_account")

    return render(request, "accounts/manage_parent_children.html", {
        "profile":  profile,
        "students": students,
        "current":  profile.children.values_list("pk", flat=True),
    })


# =========================================================
# PRINCIPAL DASHBOARD
# =========================================================

@login_required
@user_passes_test(is_principal)
def principal_dashboard(request):
    """
    Dashboard for Principal role.
    Principal = staff user with StaffProfile.designation == 'principal'.

    Permissions:
    - READ: students, staff, attendance, results, analytics
    - MANAGE: exam terms (publish/unpublish), notifications, meetings, letters
    - NO ACCESS: user CRUD, marks entry, bulk uploads, salary data
    """
    from staff.models import StaffProfile, Designation
    from students.models import StudentProfile
    from academics.models import AcademicYear, Class, Section, ExamTerm
    from attendance.models import StudentAttendance, AttendanceStatus, StaffAttendance
    from notifications.services import unread_count
    from django.utils import timezone as tz
    from datetime import timedelta

    today        = tz.now().date()
    current_year = AcademicYear.objects.filter(is_current=True).first()

    # ── Own profile ──────────────────────────────────────────────────────
    try:
        staff_profile = StaffProfile.objects.select_related(
            "department", "user"
        ).get(user=request.user)
    except StaffProfile.DoesNotExist:
        staff_profile = None

    # ── School-wide stats ─────────────────────────────────────────────────
    total_students   = StudentProfile.objects.filter(status="active").count()
    total_staff      = StaffProfile.objects.filter(is_active=True).count()
    total_classes    = Class.objects.count()
    total_sections   = Section.objects.count()

    # Attendance today (students)
    students_present_today = StudentAttendance.objects.filter(
        date=today,
        status__in=[AttendanceStatus.PRESENT, AttendanceStatus.LATE],
    ).count()
    students_absent_today = StudentAttendance.objects.filter(
        date=today,
        status=AttendanceStatus.ABSENT,
    ).count()
    students_total_today = StudentAttendance.objects.filter(date=today).count()
    attendance_pct_today = (
        round(students_present_today / students_total_today * 100, 1)
        if students_total_today else 0
    )

    # Staff attendance today
    staff_present_today = StaffAttendance.objects.filter(
        date=today,
        status__in=[AttendanceStatus.PRESENT, AttendanceStatus.LATE],
    ).count()

    # ── Exam terms ────────────────────────────────────────────────────────
    exam_terms = ExamTerm.objects.select_related("academic_year").order_by(
        "-academic_year__start_date", "start_date"
    )[:10]

    unpublished_terms = ExamTerm.objects.filter(is_published=False).count()
    published_terms   = ExamTerm.objects.filter(is_published=True).count()

    # ── Recent academic years ─────────────────────────────────────────────
    academic_years = AcademicYear.objects.order_by("-start_date")[:5]

    # ── Notifications ─────────────────────────────────────────────────────
    unread = unread_count(request.user)

    # ── Class-wise student breakdown ──────────────────────────────────────
    from academics.services import sorted_classes
    classes = sorted_classes(
        Class.objects.prefetch_related("sections").all()
    )
    class_stats = []
    for cls in classes:
        count = StudentProfile.objects.filter(
            section__class_obj=cls, status="active"
        ).count()
        class_stats.append({
            "name":    cls.name,
            "count":   count,
            "id":      cls.id,
        })

    # ── Staff by designation ──────────────────────────────────────────────
    staff_by_desig = {}
    for sp in StaffProfile.objects.filter(is_active=True).values("designation"):
        desig = sp["designation"]
        staff_by_desig[desig] = staff_by_desig.get(desig, 0) + 1

    # ── Recent notifications sent (visibility for principal) ──────────────
    recent_notifs = []
    try:
        from notifications.models import Notification
        recent_notifs = Notification.objects.select_related("sender").order_by(
            "-created_at"
        )[:5]
    except Exception:
        pass

    # ── AI analytics summary ──────────────────────────────────────────────
    principal_analytics = None
    try:
        from analytics.services import run_analytics_for_all_students
        result = run_analytics_for_all_students()
        principal_analytics = result.get("summary", None)
    except Exception:
        pass

    context = {
        # Profile
        "staff_profile":          staff_profile,
        "today":                  today,
        # Stats
        "total_students":         total_students,
        "total_staff":            total_staff,
        "total_classes":          total_classes,
        "total_sections":         total_sections,
        # Attendance
        "students_present_today": students_present_today,
        "students_absent_today":  students_absent_today,
        "students_total_today":   students_total_today,
        "attendance_pct_today":   attendance_pct_today,
        "staff_present_today":    staff_present_today,
        # Academic
        "current_year":           current_year,
        "academic_years":         academic_years,
        "exam_terms":             exam_terms,
        "unpublished_terms":      unpublished_terms,
        "published_terms":        published_terms,
        "class_stats":            class_stats,
        "staff_by_desig":         staff_by_desig,
        # Comms
        "unread":                 unread,
        "recent_notifs":          recent_notifs,
        # Analytics
        "principal_analytics":    principal_analytics,
    }

    return render(request, "accounts/principal_dashboard.html", context)
