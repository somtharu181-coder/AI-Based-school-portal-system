from django.urls import path
from . import views

app_name = "academics"

urlpatterns = [

    
    
    path(
        "dashboard/",
        views.academic_dashboard,
        name="academic_dashboard"
    ),

    
    path(
        "academic-year/create/",
        views.create_academic_year,
        name="create_academic_year"
    ),

    
    path(
        "subject/create/",
        views.create_subject,
        name="create_subject"
    ),

    
    path(
        "assign-subject/",
        views.assign_subject_to_class,
        name="assign_subject_to_class"
    ),

    
    path(
        "assign-teacher/",
        views.assign_teacher,
        name="assign_teacher"
    ),

    
    path(
        "routine/create/",
        views.create_routine,
        name="create_routine"
    ),
    
    path("exam-terms/",                        views.exam_term_list,          name="exam_term_list"),
    path("exam-terms/create/",                views.create_exam_term,        name="create_exam_term"),
    path("exam-terms/<int:pk>/toggle-status/", views.toggle_exam_term_status, name="toggle_exam_term_status"),

   
    path("marks/select/",  views.marks_entry_select, name="marks_entry_select"),
    path("marks/entry/",   views.marks_entry,         name="marks_entry"),
    path("marks/my/",      views.student_marks_view,  name="student_marks"),

    
    path("classes/manage/",  views.manage_classes,  name="manage_classes"),
    path("sections/manage/", views.manage_sections, name="manage_sections"),
    path("subjects/manage/", views.manage_subjects, name="manage_subjects"),


    path("bulk/students/", views.bulk_upload_students, name="bulk_upload_students"),
    path("bulk/marks/",    views.bulk_upload_marks,    name="bulk_upload_marks"),
    path("bulk/staff/",    views.bulk_upload_staff,    name="bulk_upload_staff"),
]