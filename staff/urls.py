from django.urls import path
from . import views

app_name = "staff"

urlpatterns = [
    
    
    
    path("", views.staff_list_view, name="staff_list"),
    path("create/", views.staff_create_view, name="staff_create"),
    path("<str:staff_id>/", views.staff_detail_view, name="staff_detail"),

    path("<str:staff_id>/update/", views.staff_update_view, name="staff_update"),

    path("<str:staff_id>/delete/", views.staff_delete_view, name="staff_delete"),
]