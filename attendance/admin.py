from django.contrib import admin
from django.utils import timezone
from django.contrib import messages

from .models import StudentAttendance, StaffAttendance, AttendanceStatus



# FILTERS (REUSABLE)

class DateRangeFilter(admin.SimpleListFilter):
    title = "Date Filter"
    parameter_name = "date_filter"

    def lookups(self, request, model_admin):
        return (
            ("today", "Today"),
            ("this_week", "This Week"),
            ("this_month", "This Month"),
        )

    def queryset(self, request, queryset):

        if self.value() == "today":
            return queryset.filter(date=timezone.now().date())

        if self.value() == "this_week":
            start = timezone.now().date() - timezone.timedelta(days=7)
            return queryset.filter(date__gte=start)

        if self.value() == "this_month":
            start = timezone.now().date().replace(day=1)
            return queryset.filter(date__gte=start)


# STUDENT ATTENDANCE ADMIN
@admin.register(StudentAttendance)
class StudentAttendanceAdmin(admin.ModelAdmin):

    
    list_select_related = ("student", "marked_by")

    
    list_display = (
        "student",
        "date",
        "status",
        "marked_by",
        "created_at",
    )

    
    list_filter = (
        "status",
        DateRangeFilter,
        "date",
    )

   
    search_fields = (
        "student__student_id",
        "student__user__username",
    )

   
    ordering = ("-date",)

    
    fieldsets = (
        ("Attendance Info", {
            "fields": ("student", "date", "status")
        }),
        ("Meta Info", {
            "fields": ("marked_by", "remarks")
        }),
    )

    readonly_fields = ("created_at", "updated_at")

    
    def save_model(self, request, obj, form, change):

        if not obj.marked_by:
            obj.marked_by = request.user

        super().save_model(request, obj, form, change)



@admin.register(StaffAttendance)
class StaffAttendanceAdmin(admin.ModelAdmin):

    list_select_related = ("staff", "marked_by")

    list_display = (
        "staff",
        "date",
        "status",
        "marked_by",
        "created_at",
    )

    list_filter = (
        "status",
        DateRangeFilter,
        "date",
    )

    search_fields = (
        "staff__staff_id",
        "staff__user__username",
    )

    ordering = ("-date",)

    fieldsets = (
        ("Attendance Info", {
            "fields": ("staff", "date", "status")
        }),
        ("Meta Info", {
            "fields": ("marked_by", "remarks")
        }),
    )

    readonly_fields = ("created_at", "updated_at")

    def save_model(self, request, obj, form, change):

        if not obj.marked_by:
            obj.marked_by = request.user

        super().save_model(request, obj, form, change)