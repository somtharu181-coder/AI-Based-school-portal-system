from django.contrib import admin
from .models import ParentProfile, OnlineMeeting, SchoolLetter

@admin.register(ParentProfile)
class ParentProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "phone")
    filter_horizontal = ("children",)

@admin.register(OnlineMeeting)
class OnlineMeetingAdmin(admin.ModelAdmin):
    list_display = ("title", "host", "scheduled_at", "status", "target_class")
    list_filter  = ("status",)

@admin.register(SchoolLetter)
class SchoolLetterAdmin(admin.ModelAdmin):
    list_display = ("title", "issued_by", "is_published", "issued_at")
    list_filter  = ("is_published",)
