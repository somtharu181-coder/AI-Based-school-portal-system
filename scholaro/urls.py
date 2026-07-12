"""
URL configuration for scholaro project.
"""
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)


def home(request):
    return redirect("accounts:login")


urlpatterns = [
    path("", home),
    path("admin/", admin.site.urls),

    # ── Authentication (JWT API tokens) ─────────────────────────────
    path("api/token/",         TokenObtainPairView.as_view(),  name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(),     name="token_refresh"),
    path("api/token/verify/",  TokenVerifyView.as_view(),      name="token_verify"),

    # ── App routes ───────────────────────────────────────────────────
    path("accounts/",          include("accounts.urls")),
    path("students/",          include("students.urls")),
    path("staff/",             include("staff.urls")),
    path("academics/",         include("academics.urls")),
    path("attendance/",        include("attendance.urls")),
    path("reporting_system/",  include("reporting_system.urls")),
    path("analytics/",         include("analytics.urls", namespace="analytics")),
    path("notifications/",     include("notifications.urls")),
    path("assignments/",       include("assignments.urls")),
    path("quiz/",              include("quiz.urls")),
    path("parent/",            include("parent_portal.urls")),
    path("audit/",             include("audit_log.urls", namespace="audit_log")),
]
