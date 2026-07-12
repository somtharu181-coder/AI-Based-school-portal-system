from django.contrib import admin
from .models import Assignment, Submission

class SubmissionInline(admin.TabularInline):
    model = Submission
    extra = 0
    readonly_fields = ("student","submitted_at","checked_at")

@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ("title","class_subject","section","teacher","due_date","status")
    list_filter  = ("status",)
    inlines      = [SubmissionInline]

@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ("student","assignment","marks","grade","submitted_at")
    list_filter  = ("grade",)
