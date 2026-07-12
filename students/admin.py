from django.contrib import admin, messages
from .models import StudentProfile


# ── Bulk actions ──────────────────────────────────────────────────────────────

@admin.action(description="Mark selected students as ACTIVE")
def mark_active(modeladmin, request, queryset):
    queryset.update(status="active")

@admin.action(description="Mark selected students as INACTIVE")
def mark_inactive(modeladmin, request, queryset):
    queryset.update(status="inactive")

@admin.action(description="Mark selected students as GRADUATED")
def mark_graduated(modeladmin, request, queryset):
    queryset.update(status="graduated")


# ── StudentProfile admin ──────────────────────────────────────────────────────

@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):

    list_select_related = ("user", "section", "section__class_obj")

    list_display = (
        "student_id", "name", "user",
        "get_class", "section", "roll_number",
        "status", "admission_date",
    )
    list_filter  = ("status", "section", "section__class_obj")
    search_fields = (
        "student_id", "name",
        "user__username", "user__email",
        "guardian_name", "guardian_phone",
    )
    ordering = ("section", "roll_number")
    actions  = [mark_active, mark_inactive, mark_graduated]

    fieldsets = (
        ("Basic Information", {
            "fields": ("user", "student_id", "roll_number", "section", "academic_year", "status")
        }),
        ("Personal Information", {
            "fields": ("name", "gender", "date_of_birth", "email",
                       "temporary_address", "permanent_address",
                       "father_name", "mother_name", "telephone_number")
        }),
        ("Guardian Information", {
            "fields": ("guardian_name", "guardian_phone")
        }),
        ("System Information", {
            "fields": ("admission_date", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )
    readonly_fields   = ("student_id", "admission_date", "created_at", "updated_at")
    autocomplete_fields = ("user", "section")

    def get_class(self, obj):
        return obj.section.class_obj
    get_class.short_description = "Class"

    def save_model(self, request, obj, form, change):
        if obj.user and obj.user.role != "student":
            messages.error(request, "Only users with 'student' role can be linked.")
            return
        super().save_model(request, obj, form, change)

    # ── Role-based queryset: staff can only see students in their sections ──
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser or request.user.role == "admin":
            return qs
        # Staff: scope to sections they teach
        try:
            from staff.models import StaffProfile
            from academics.models import TeacherSubjectAssignment
            sp = StaffProfile.objects.get(user=request.user)
            section_ids = TeacherSubjectAssignment.objects.filter(
                teacher=sp
            ).values_list("section_id", flat=True).distinct()
            return qs.filter(section_id__in=section_ids)
        except Exception:
            return qs.none()

    # ── Role-based field visibility ──
    def get_readonly_fields(self, request, obj=None):
        rf = list(self.readonly_fields)
        if not request.user.is_superuser and request.user.role != "admin":
            # Staff can see but not edit sensitive fields
            rf += ["user", "section", "academic_year", "email",
                   "father_name", "mother_name", "telephone_number",
                   "temporary_address", "permanent_address",
                   "guardian_name", "guardian_phone"]
        return rf
