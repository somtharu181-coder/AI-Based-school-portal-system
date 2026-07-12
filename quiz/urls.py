from django.urls import path
from . import views
app_name = "quiz"
urlpatterns = [
    path("",                     views.home,    name="home"),
    path("start/",               views.start,   name="start"),
    path("attempt/<int:pk>/",    views.attempt, name="attempt"),
    path("answer/<int:question_pk>/", views.answer, name="answer"),
    path("finish/<int:pk>/",     views.finish,  name="finish"),
    path("result/<int:pk>/",     views.result,  name="result"),
]
