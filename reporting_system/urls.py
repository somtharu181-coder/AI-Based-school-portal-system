from django.urls import path
from . import views

app_name = "reporting_system"

urlpatterns = [
    
    # DASHBOARD
    
    path(
        "dashboard/",
        views.reporting_dashboard,
        name="reporting_dashboard"
    ),

    
    # STUDENT RESULTS
    
    path(
        "results/",
        views.student_results,
        name="student_results"
    ),

    path(
        "results/<int:pk>/",
        views.student_result_detail,
        name="student_result_detail"
    ),

    
    # ACADEMIC SUMMARY
    
    path(
        "summary/",
        views.academic_summary_list,
        name="academic_summary_list"
    ),

    
    # AUDIT LOGS
    
    path(
        "audit-logs/",
        views.audit_logs,
        name="audit_logs"
    ),

    
    # ADMIN ACTION
    # (Rebuild all results manually)
    
    path(
        "rebuild-results/",
        views.rebuild_results,
        name="rebuild_results"
    ),

    # Student's own results (filtered to logged-in student)
    path("my-results/", views.my_results, name="my_results"),

    # Download PDF report for a specific result
    path("results/<int:result_pk>/download-pdf/", views.download_result_pdf, name="download_result_pdf"),
]