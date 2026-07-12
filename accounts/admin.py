"""
accounts/admin.py
Role-based access control for the Django admin site.

Rules enforced:
  - Only users with role="admin" (or is_superuser) can access /admin/
  - Admin users see everything.
  - Staff users are blocked at the admin gate entirely.
  - The custom AdminSite subclass enforces this at every request.
"""

from django.contrib import admin
from django.contrib.admin import AdminSite
from django.contrib.auth.admin import UserAdmin
from django.contrib import messages

from .models import User
from .forms import CustomUserCreationForm, CustomUserUpdateForm


# ── Role-gated Admin Site ─────────────────────────────────────────────────────

class ScholaroAdminSite(admin.AdminSite):
    """
    Custom admin site that restricts access to users with role='admin'
    or is_superuser=True. All other roles are rejected with a clear message.
    """
    site_header = "Scholaro ERP — Admin"
    site_title  = "Scholaro Admin"
    index_title = "Dashboard"

    def has_permission(self, request):
        """
        Grant admin access only to:
          - superusers  (Django built-in override)
          - users with role == 'admin' who are active and is_staff=True
        """
        if not request.user.is_active:
            return False
        if request.user.is_superuser:
            return True
        return (
            request.user.is_authenticated
            and request.user.is_staff
            and hasattr(request.user, "role")
            and request.user.role == "admin"
        )


# Replace the default admin site
scholaro_admin = ScholaroAdminSite(name="scholaro_admin")

# Also patch the default admin.site so all auto-registered models go through
# the same gate (Django's contrib apps register with admin.site).
admin.site.__class__ = ScholaroAdminSite
admin.site.site_header = "Scholaro ERP — Admin"
admin.site.site_title  = "Scholaro Admin"
admin.site.index_title = "Dashboard"


# ── Helper ────────────────────────────────────────────────────────────────────

def create_profile_for_user(user):
    from students.models import StudentProfile
    from staff.models import StaffProfile
    if user.role == "student":
        StudentProfile.objects.get_or_create(user=user)
    elif user.role == "staff":
        StaffProfile.objects.get_or_create(user=user)


# ── Admin action ──────────────────────────────────────────────────────────────

@admin.action(description="Create Profile for Selected Users")
def create_profile(modeladmin, request, queryset):
    for user in queryset:
        create_profile_for_user(user)
    messages.success(request, "Profiles created where missing.")


# ── User Admin ────────────────────────────────────────────────────────────────

class CustomUserAdmin(UserAdmin):
    add_form  = CustomUserCreationForm
    form      = CustomUserUpdateForm
    model     = User
    actions   = [create_profile]

    list_display  = ("username", "email", "role", "is_active", "is_staff", "date_joined")
    list_filter   = ("role", "is_active", "is_staff")
    search_fields = ("username", "email", "first_name", "last_name")
    ordering      = ("-date_joined",)

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal Info", {"fields": ("first_name", "last_name", "email", "phone")}),
        ("Role & Permissions", {
            "fields": (
                "role", "is_active", "is_staff", "is_superuser",
                "groups", "user_permissions",
            )
        }),
        ("Important Dates", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "email", "phone", "role", "password1", "password2"),
        }),
    )

    # ── Prevent non-superusers from promoting others to superuser ──
    def get_readonly_fields(self, request, obj=None):
        rf = list(super().get_readonly_fields(request, obj))
        if not request.user.is_superuser:
            rf += ["is_superuser", "user_permissions", "groups"]
        return rf

    # ── Prevent editing other admin accounts (only superuser can) ──
    def has_change_permission(self, request, obj=None):
        if obj and obj.role == "admin" and not request.user.is_superuser:
            if obj.pk != request.user.pk:
                return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and obj.role == "admin" and not request.user.is_superuser:
            return False
        return super().has_delete_permission(request, obj)

    # ── Role-based queryset: admins see all, staff see nothing here ──
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Admin role: exclude superusers from the list (can't accidentally edit them)
        return qs.filter(is_superuser=False)

    def save_model(self, request, obj, form, change):
        # Ensure is_staff=True for admin-role users so they can access /admin/
        if obj.role == "admin":
            obj.is_staff = True
        super().save_model(request, obj, form, change)


admin.site.register(User, CustomUserAdmin)
