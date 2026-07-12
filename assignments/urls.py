from django.urls import path
from . import views
app_name = "assignments"
urlpatterns = [
    path("teacher/",            views.teacher_dashboard, name="teacher_dashboard"),
    path("create/",             views.create,            name="create"),
    path("check/<int:pk>/",     views.check,             name="check"),
    path("student/",            views.student_list,      name="student_list"),
    path("submit/<int:pk>/",    views.submit,            name="submit"),
]
