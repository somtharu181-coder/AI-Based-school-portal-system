from django.urls import path
from . import views

app_name = "students"

urlpatterns = [
    path("",                              views.student_list,           name="student_list"),
    path("create/",                       views.create_student,         name="create_student"),
    path("update/<int:pk>/",              views.update_student,         name="update_student"),
    path("delete/<int:pk>/",              views.delete_student,         name="delete_student"),
    path("status/<int:pk>/",              views.update_student_status,  name="update_student_status"),
    path("get-sections/",                 views.get_sections,           name="get_sections"),
    path("student/<int:pk>/",             views.student_detail,         name="student_detail"),
    path("my-profile/",                   views.my_profile,             name="my_profile"),
    path("promote/<int:pk>/",             views.promote_student,        name="promote_student"),
    path("double-promote/<int:pk>/",      views.double_promote_student, name="double_promote_student"),
    path("fail/<int:pk>/",                views.fail_student,           name="fail_student"),
]