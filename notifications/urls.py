from django.urls import path
from . import views

app_name = "notifications"

urlpatterns = [
    path("",              views.inbox,     name="inbox"),
    path("send/",         views.send,      name="send"),
    path("read/",         views.mark_read, name="mark_all_read"),
    path("read/<int:pk>/",views.mark_read, name="mark_read"),
]
