from django.db import transaction
from django.core.exceptions import ValidationError

from accounts.models import User
from .models import StudentProfile



# 1. VALIDATION LAYER (SAFE REUSABLE CHECKS)

def is_student_user(user: User) -> bool:
    """
    Reusable validation for entire system.
    Used by admin, API, signals.
    """
    return user.role == "student"


def validate_student_user(user: User):
    """
    Strict validation (used when failure must block action).
    """
    if not is_student_user(user):
        raise ValidationError("Only users with role 'student' are allowed.")



# 2. CREATE SINGLE STUDENT PROFILE

@transaction.atomic
def create_student_profile(user: User):
    """
    Core service for creating student profile.

    Used by:
    - Django Admin
    - API (React frontend)
    - EMIS integration (future)
    """

    validate_student_user(user)

    profile, created = StudentProfile.objects.get_or_create(
        user=user,
        defaults={
            "student_id": f"STU-{user.id}",
            "roll_number": "",
            "class_name": None,
            "section": None,
        }
    )

    return profile, created



# 3. BULK STUDENT PROFILE CREATION

@transaction.atomic
def bulk_create_student_profiles(users_queryset):
    """
    Bulk creation optimized for admin actions or EMIS sync.
    """

    created_profiles = []

    for user in users_queryset:
        if is_student_user(user):
            profile, created = StudentProfile.objects.get_or_create(user=user)
            if created:
                created_profiles.append(profile)

    return created_profiles



# 4. UPDATE STUDENT STATUS (BULK SAFE)

@transaction.atomic
def update_student_status(student_ids, status: str):
    """
    Bulk update for:
    - admin panel
    - API
    - reporting system
    """

    return StudentProfile.objects.filter(
        student_id__in=student_ids
    ).update(status=status)



# 5. GET STUDENT PROFILE (SAFE FETCH)

def get_student_profile(user: User):
    """
    Safe reusable fetch function.
    Used in API and admin.
    """
    try:
        return StudentProfile.objects.get(user=user)
    except StudentProfile.DoesNotExist:
        return None



# 6. STUDENT SUMMARY (FOR API / DASHBOARD)

def get_student_summary(student_id: str):
    """
    Lightweight data output for React frontend / dashboards.
    """

    try:
        student = StudentProfile.objects.select_related(
            "user", "class_name", "section"
        ).get(student_id=student_id)

        return {
            "student_id": student.student_id,
            "name": student.user.username,
            "class": str(student.class_name),
            "section": str(student.section),
            "status": student.status,
        }

    except StudentProfile.DoesNotExist:
        return None