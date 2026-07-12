from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = "attendance"


router = DefaultRouter()
router.register(r"api", views.AttendanceViewSet, basename="attendance-api")

urlpatterns = [
    
    path("mark/",        views.mark_student_attendance_view, name="mark_student_attendance"),
    path("records/",     views.student_attendance_list,      name="student_attendance_list"),
    path("my/",          views.my_attendance_view,           name="my_attendance"),
    path("sections/",    views.get_sections_by_class,        name="get_sections"),

   
    path("", include(router.urls)),
]
