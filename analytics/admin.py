from django.contrib import admin

from .models import (
    StudentAnalyticsProfile,
    StudentFeature,
    AIRecommendation
)

 
# 1. STUDENT ANALYTICS PROFILE ADMIN

@admin.register(StudentAnalyticsProfile)
class StudentAnalyticsProfileAdmin(admin.ModelAdmin):

    list_display = (
        "student",
        "average_percentage",
        "gpa",
        "attendance_percentage",
        "performance_score",
        "risk_level",
        "updated_at",
    )

    list_filter = (
        "risk_level",
        "gpa",
    )

    search_fields = (
        "student__user__username",
        "student__user__first_name",
        "student__user__last_name",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )



# 2. STUDENT FEATURE (ML VECTOR DATA)

@admin.register(StudentFeature)
class StudentFeatureAdmin(admin.ModelAdmin):

    list_display = (
        "analytics_profile",
        "feature_name",
        "value",
    )

    list_filter = (
        "feature_name",
    )

    search_fields = (
        "analytics_profile__student__user__username",
        "feature_name",
    )



# 3. AI RECOMMENDATION ADMIN

@admin.register(AIRecommendation)
class AIRecommendationAdmin(admin.ModelAdmin):

    list_display = (
        "analytics_profile",
        "title",
        "confidence",
        "algorithm",
        "is_read",
        "created_at",
    )

    list_filter = (
        "algorithm",
        "is_read",
        "confidence",
    )

    search_fields = (
        "analytics_profile__student__user__username",
        "title",
    )

    list_editable = (
        "is_read",
    )

    readonly_fields = (
        "created_at",
    )