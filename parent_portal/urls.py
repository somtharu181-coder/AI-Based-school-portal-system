from django.urls import path
from . import views

app_name = "parent_portal"

urlpatterns = [
    path("",                    views.dashboard,            name="dashboard"),
    path("meetings/",           views.meetings_view,        name="meetings"),
    path("meetings/create/",    views.create_meeting_view,  name="create_meeting"),
    path("letters/",            views.letters_view,         name="letters"),
    path("letters/publish/",    views.publish_letter_view,  name="publish_letter"),
    path("ajax/sections/",      views.ajax_sections,        name="ajax_sections"),
]
