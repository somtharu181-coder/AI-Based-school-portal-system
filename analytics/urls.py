from django.urls import path
from . import views

app_name = "analytics"

urlpatterns = [
    path("dashboard/",          views.analytics_dashboard,      name="analytics_dashboard"),
    path("student/<int:student_id>/", views.student_analytics_detail, name="student_detail"),
    path("my-report/",          views.my_ai_report,             name="my_ai_report"),

    path("teacher/",            views.teacher_analytics_view,   name="teacher_analytics"),
    path("principal/",          views.principal_analytics_view, name="principal_analytics"),
]
