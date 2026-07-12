from django.contrib import admin
from .models import (
    StudentResult,
    SubjectResult,
    ResultCalculationLog,
    ClassResultSummary,
    StudentTranscript,
    ReportGenerationLog
)


# STUDENT RESULT ADMIN

@admin.register(StudentResult)
class StudentResultAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "exam_term",
        "total_obtained_marks",
        "total_full_marks",
        "percentage",
        "gpa",
        "grade",
        "rank",
        "is_pass",
    )
    list_filter = ("exam_term", "is_pass")
    search_fields = ("student__id", "student__user__username")
    ordering = ("-percentage",)



# SUBJECT RESULT ADMIN

@admin.register(SubjectResult)
class SubjectResultAdmin(admin.ModelAdmin):
    list_display = (
        "student_result",
        "class_subject",
        "theory_marks",
        "practical_marks",
        "total_marks",
        "percentage",
        "grade",
        "is_pass",
    )
    list_filter = ("class_subject", "is_pass")
    search_fields = ("student_result__student__id",)



# RESULT CALCULATION LOG ADMIN

@admin.register(ResultCalculationLog)
class ResultCalculationLogAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "exam_term",
        "action",
        "total_marks",
        "percentage",
        "gpa",
        "created_at",
    )
    list_filter = ("action", "exam_term")
    search_fields = ("student__id",)



# CLASS RESULT SUMMARY ADMIN

@admin.register(ClassResultSummary)
class ClassResultSummaryAdmin(admin.ModelAdmin):
    list_display = (
        "academic_year",
        "class_obj",
        "exam_term",
        "average_percentage",
        "highest_percentage",
        "lowest_percentage",
        "total_students",
    )
    list_filter = ("academic_year", "exam_term")



# STUDENT TRANSCRIPT ADMIN

@admin.register(StudentTranscript)
class StudentTranscriptAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "academic_year",
        "total_gpa",
        "final_grade",
        "is_promoted",
    )
    list_filter = ("academic_year", "is_promoted")
    search_fields = ("student__id",)



# REPORT GENERATION LOG ADMIN

@admin.register(ReportGenerationLog)
class ReportGenerationLogAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "generated_by",
        "report_type",
        "status",
        "created_at",
    )
    list_filter = ("report_type", "status")
    search_fields = ("student__id", "generated_by__username")