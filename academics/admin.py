from django.contrib import admin
from django.contrib.admin import ModelAdmin
from django.core.exceptions import ValidationError
from django.contrib import messages
from staff .models import StaffProfile
from .models import StudentMark, ExamTerm

from .models import (
    AcademicYear,
    Subject,
    ClassSubject,
    TeacherSubjectAssignment,
    ClassRoutine,
    Class,
    Section,
)




# GLOBAL BASE ADMIN

class BaseAdmin(admin.ModelAdmin):
    readonly_fields = (
        "uuid",
        "created_at",
        "updated_at",
    )

    save_on_top = True

    list_per_page = 50

    actions_on_top = True
    actions_on_bottom = True

# Class ADMIN


@admin.register(Class)
class ClassAdmin(admin.ModelAdmin):
    search_fields = ["name"]

    list_display = ("name", "is_active", "created_at")
    list_filter = ("is_active",)
    ordering = ("name",)


# Section ADMIN


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    search_fields = ["name", "class_obj__name"]

    list_display = ("class_obj", "name", "created_at")
    list_filter = ("class_obj",)
    ordering = ("class_obj", "name")

# ACADEMIC YEAR ADMIN


@admin.register(AcademicYear)
class AcademicYearAdmin(BaseAdmin):

    search_fields = [
        "name",
    ]

    list_display = (
        "name",
        "start_date",
        "end_date",
        "is_current",
        "is_active",
    )

    list_filter = (
        "is_current",
        "is_active",
    )

    

    ordering = (
        "-start_date",
    )

    fieldsets = (

        ("Academic Year Information", {
            "fields": (
                "name",
                "start_date",
                "end_date",
            )
        }),

        ("System Configuration", {
            "fields": (
                "is_current",
                "is_active",
            )
        }),

        ("Audit Information", {
            "fields": (
                "uuid",
                "created_at",
                "updated_at",
            )
        }),
    )



# SUBJECT ADMIN

@admin.register(Subject)
class SubjectAdmin(BaseAdmin):

    search_fields = [
        "code",
        "name",
    ]
    
    list_display = (
        "code",
        "name",
        "credit_hours",
        "is_active",
    )

    list_filter = (
        "is_active",
    )


    ordering = (
        "name",
    )

    fieldsets = (

        ("Subject Information", {
            "fields": (
                "code",
                "name",
                "credit_hours",
                "description",
            )
        }),

        ("Status", {
            "fields": (
                "is_active",
            )
        }),

        ("Audit Information", {
            "fields": (
                "uuid",
                "created_at",
                "updated_at",
            )
        }),
    )



# CLASS SUBJECT ADMIN

@admin.register(ClassSubject)
class ClassSubjectAdmin(BaseAdmin):

    search_fields = [
        "subject__name",
        "class_obj__name",
        
    ]


    list_select_related = (
        "academic_year",
        "class_obj",
        "subject",
    )

    autocomplete_fields = (
        "academic_year",
        "class_obj",
        "subject",
    )

    list_display = (
        "class_obj",
        "subject",
        "academic_year",
        "full_marks",
        "pass_marks",
        "is_optional",
        "is_active",
    )

    list_filter = (
        "academic_year",
        "is_optional",
        "is_active",
    )

    
    ordering = (
        "class_obj",
        "subject",
    )

    fieldsets = (

        ("Assignment Information", {
            "fields": (
                "academic_year",
                "class_obj",
                "subject",
            )
        }),

        ("Marks Configuration", {
            "fields": (
                "full_marks",
                "pass_marks",
            )
        }),

        ("Options", {
            "fields": (
                "is_optional",
                "is_active",
            )
        }),

        ("Audit Information", {
            "fields": (
                "uuid",
                "created_at",
                "updated_at",
            )
        }),
    )

# TEACHER SUBJECT ASSIGNMENT ADMIN

@admin.register(TeacherSubjectAssignment)
class TeacherSubjectAssignmentAdmin(BaseAdmin):

    search_fields = [
        "teacher__user__username",
        "class_subject__subject__name",
    ]

    list_select_related = (
        "teacher",
        "class_subject",
        "section",
    )

    autocomplete_fields = (
        "teacher",
        "class_subject",
        "section",
    )

    list_display = (
        "teacher",
        "class_subject",
        "section",
        "is_class_teacher",
        "is_active",
    )

    list_filter = (
        "is_class_teacher",
        "is_active",
    )

    

    ordering = (
        "teacher",
    )

    fieldsets = (

        ("Teacher Assignment", {
            "fields": (
                "teacher",
                "class_subject",
                "section",
            )
        }),

        ("Assignment Options", {
            "fields": (
                "is_class_teacher",
                "remarks",
                "is_active",
            )
        }),

        ("Audit Information", {
            "fields": (
                "uuid",
                "created_at",
                "updated_at",
            )
        }),
    )



# CLASS ROUTINE ADMIN

@admin.register(ClassRoutine)
class ClassRoutineAdmin(BaseAdmin):

    search_fields = [
        "section__name",
        "teacher__user__username",
        "class_subject__subject__name",
    ]

    list_select_related = (
        "academic_year",
        "teacher",
        "section",
        "class_subject",
    )

    autocomplete_fields = (
        "academic_year",
        "teacher",
        "section",
        "class_subject",
    )

    list_display = (
        "room",
        "academic_year",
        "section",
        "class_subject",
        "teacher",
        "day",
        "start_time",
        "end_time",
        "is_active",
    )

    list_filter = (
        "academic_year",
        "day",
        "is_active",
    )

    

    ordering = (
        "day",
        "start_time",
    )

    fieldsets = (

        ("Routine Information", {
            "fields": (
                "academic_year",
                "class_subject",
                "teacher",
                "section",
            )
        }),

        ("Schedule", {
            "fields": (
                "day",
                "start_time",
                "end_time",
                "room",
            )
        }),

        ("Status", {
            "fields": (
                "is_active",
            )
        }),

        ("Audit Information", {
            "fields": (
                "uuid",
                "created_at",
                "updated_at",
            )
        }),
    )

@admin.register(ExamTerm)
class ExamTermAdmin(BaseAdmin):

    list_display = (
        "name",
        "academic_year",
        "term_type",
        "is_published",
        "is_active",
    )

    list_filter = (
        "academic_year",
        "term_type",
        "is_published",
    )


@admin.register(StudentMark)
class StudentMarkAdmin(BaseAdmin):

    list_display = (
        "student",
        "exam_term",
        "class_subject",
        "theory_marks",
        "practical_marks",
        "total_marks",
        "percentage",
        "grade",
        "gpa",
    )

    list_filter = (
        "exam_term",
        "class_subject",
    )

    search_fields = (
        "student__id",
    )