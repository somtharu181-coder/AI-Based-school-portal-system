from django.contrib import admin
from django.contrib import messages
from django.db.models import Q

from .models import (
    Department,
    StaffProfile,
    Designation,
)


# =====================================================
# DEPARTMENT ADMIN
# =====================================================
@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "name",
    )

    search_fields = (
        "name",
    )

    ordering = (
        "name",
    )


# =====================================================
# BULK ACTIONS
# =====================================================
@admin.action(description="Mark selected staff as ACTIVE")
def mark_active(modeladmin, request, queryset):

    updated = queryset.update(is_active=True)

    messages.success(
        request,
        f"{updated} staff members marked as active."
    )


@admin.action(description="Mark selected staff as INACTIVE")
def mark_inactive(modeladmin, request, queryset):

    updated = queryset.update(is_active=False)

    messages.warning(
        request,
        f"{updated} staff members marked as inactive."
    )


# =====================================================
# STAFF PROFILE ADMIN
# =====================================================
@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):

    # -------------------------------------------------
    # PERFORMANCE OPTIMIZATION
    # -------------------------------------------------
    list_select_related = (
        "user",
        "department",
    )

    autocomplete_fields = (
        "user",
        "department",
    )

    list_per_page = 25

    # -------------------------------------------------
    # TABLE DISPLAY
    # -------------------------------------------------
    list_display = (
        "staff_id",
        "get_full_name",
        "designation",
        "department",
        "phone",
        "joining_date",
        "is_active",
    )

    # -------------------------------------------------
    # FILTERS
    # -------------------------------------------------
    list_filter = (
        "designation",
        "department",
        "is_active",
        "joining_date",
    )

    # -------------------------------------------------
    # SEARCH
    # -------------------------------------------------
    search_fields = (
        "staff_id",
        "user__username",
        "user__first_name",
        "user__last_name",
        "user__email",
        "phone",
    )

    # -------------------------------------------------
    # DEFAULT ORDERING
    # -------------------------------------------------
    ordering = (
        "designation",
        "staff_id",
    )

    # -------------------------------------------------
    # READONLY FIELDS
    # -------------------------------------------------
    readonly_fields = (
        "staff_id",
        "created_at",
        "updated_at",
    )

    # -------------------------------------------------
    # BULK ACTIONS
    # -------------------------------------------------
    actions = (
        mark_active,
        mark_inactive,
    )

    # -------------------------------------------------
    # FORM ORGANIZATION
    # -------------------------------------------------
    fieldsets = (

        ("User Information", {
            "fields": (
                "user",
                "staff_id",
            )
        }),

        ("Professional Information", {
            "fields": (
                "designation",
                "department",
                "salary",
                "joining_date",
                "is_active",
            )
        }),

        ("Contact Information", {
            "fields": (
                "phone",
                "address",
            )
        }),

        ("System Information", {
            "fields": (
                "created_at",
                "updated_at",
            )
        }),
    )

    # -------------------------------------------------
    # SAFE SAVE HANDLER
    # -------------------------------------------------
    def save_model(self, request, obj, form, change):

        try:

            if not obj.user:

                messages.error(
                    request,
                    "User is required."
                )
                return

            # -----------------------------------------
            # Prevent duplicate profile
            # -----------------------------------------
            existing_profile = StaffProfile.objects.filter(
                user=obj.user
            ).exclude(
                pk=obj.pk
            ).exists()

            if existing_profile:

                messages.error(
                    request,
                    "This user already has a staff profile."
                )
                return

            # -----------------------------------------
            # Validate designation dynamically
            # -----------------------------------------
            valid_designations = [
                choice[0]
                for choice in Designation.choices
            ]

            if obj.designation not in valid_designations:

                messages.error(
                    request,
                    "Invalid designation selected."
                )
                return

            # -----------------------------------------
            # Salary validation
            # -----------------------------------------
            if obj.salary is not None and obj.salary < 0:

                messages.error(
                    request,
                    "Salary cannot be negative."
                )
                return

            super().save_model(
                request,
                obj,
                form,
                change
            )

            messages.success(
                request,
                "Staff profile saved successfully."
            )

        except Exception as e:

            messages.error(
                request,
                f"Unexpected error: {str(e)}"
            )

    # -------------------------------------------------
    # CUSTOM FULL NAME
    # -------------------------------------------------
    @admin.display(description="Full Name")
    def get_full_name(self, obj):

        full_name = (
            f"{obj.user.first_name} "
            f"{obj.user.last_name}"
        ).strip()

        if full_name:
            return full_name

        return obj.user.username

    # -------------------------------------------------
    # QUERYSET OPTIMIZATION
    # -------------------------------------------------
    def get_queryset(self, request):

        queryset = super().get_queryset(request)

        return queryset.select_related(
            "user",
            "department",
        )

    # -------------------------------------------------
    # DYNAMIC SEARCH IMPROVEMENT
    # -------------------------------------------------
    def get_search_results(
        self,
        request,
        queryset,
        search_term
    ):

        queryset, use_distinct = super().get_search_results(
            request,
            queryset,
            search_term
        )

        queryset |= self.model.objects.filter(
            Q(user__email__icontains=search_term)
        )

        return queryset, use_distinct