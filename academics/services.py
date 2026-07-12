import logging
import re
from .models import Class, Section

from django.db import transaction
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from staff.models import StaffProfile
from .models import (
    AcademicYear,
    Class, Section,
    Subject,
    ClassSubject,
    TeacherSubjectAssignment,
    ClassRoutine,
)



# NATURAL SORT — shared utility

def _natural_key(text: str):
   
    import re
    nums = re.findall(r'\d+', text.strip())
    if not nums:
        return (0, 0, text.strip().lower())
    return (1, int(nums[0]), text.strip().lower())


def sorted_classes(queryset=None):
    """
    Return Class objects sorted by natural order of their name.
    Pass a queryset to filter first; defaults to Class.objects.all().
    """
    qs = queryset if queryset is not None else Class.objects.all()
    return sorted(qs, key=lambda c: _natural_key(c.name))

logger = logging.getLogger(__name__)



def service_log(level, message):

    if level == "info":
        logger.info(message)

    elif level == "warning":
        logger.warning(message)

    elif level == "error":
        logger.error(message)

    else:
        logger.debug(message)



# ACADEMIC YEAR SERVICES

class AcademicYearService:

    @staticmethod
    @transaction.atomic
    def create_academic_year(
        *,
        name,
        start_date,
        end_date,
        is_current=False
    ):
        """
        Enterprise academic year creation service.
        """

        if start_date >= end_date:
            raise ValidationError(
                "End date must be greater than start date."
            )

        academic_year = AcademicYear.objects.create(
            name=name,
            start_date=start_date,
            end_date=end_date,
            is_current=is_current,
        )

        service_log(
            "info",
            f"AcademicYear created: {academic_year.name}"
        )

        return academic_year

    @staticmethod
    @transaction.atomic
    def set_current_year(academic_year):

        AcademicYear.objects.filter(
            is_current=True
        ).update(is_current=False)

        academic_year.is_current = True
        academic_year.save()

        service_log(
            "info",
            f"AcademicYear set as current: "
            f"{academic_year.name}"
        )

        return academic_year



# SUBJECT SERVICES

class SubjectService:

    @staticmethod
    @transaction.atomic
    def create_subject(
        *,
        code,
        name,
        credit_hours=1,
        description=None
    ):

        subject = Subject.objects.create(
            code=code,
            name=name,
            credit_hours=credit_hours,
            description=description,
        )

        service_log(
            "info",
            f"Subject created: {subject.name}"
        )

        return subject



# CLASS SUBJECT SERVICES

class ClassSubjectService:

    @staticmethod
    @transaction.atomic
    def assign_subject_to_class(
        *,
        academic_year_id,
        class_obj_id,
        subject_id,
        full_marks=100,
        pass_marks=40,
        is_optional=False
    ):
        academic_year = get_object_or_404(AcademicYear, id=academic_year_id)
        class_obj = get_object_or_404(Class, id=class_obj_id)
        subject = get_object_or_404(Subject, id=subject_id)

        # Cast to int — POST data arrives as strings
        full_marks = int(full_marks)
        pass_marks = int(pass_marks)

        if pass_marks > full_marks:
            raise ValidationError("Pass marks cannot exceed full marks.")

        obj, created = ClassSubject.objects.get_or_create(
                academic_year=academic_year,
                class_obj=class_obj,
                subject=subject,
                defaults={
                    "full_marks": full_marks,
                    "pass_marks": pass_marks,
                    "is_optional": is_optional,
                })
        return obj,created




# TEACHER ASSIGNMENT SERVICES
class TeacherAssignmentService:

    @staticmethod
    @transaction.atomic
    def assign_teacher(
        *,
        teacher_id,
        class_subject_id,
        section_id,
        is_class_teacher=False,
        remarks=None
    ):
        teacher = get_object_or_404(StaffProfile, id=teacher_id)
        class_subject = get_object_or_404(ClassSubject, id=class_subject_id)
        section = get_object_or_404(Section, id=section_id)

        if teacher.designation not in ["teacher", "principal", "vice_principal"]:
            raise ValidationError("Only teaching staff allowed.")

        obj, created = TeacherSubjectAssignment.objects.get_or_create(
            teacher=teacher,
            class_subject=class_subject,
            section=section,
            defaults={
                "is_class_teacher": is_class_teacher,
                "remarks": remarks,
            })

        return obj,created




# ROUTINE SERVICES

class RoutineService:

    @staticmethod
    @transaction.atomic
    def create_routine(
        *,
        academic_year_id,
        class_subject_id,
        teacher_id,
        section_id,
        day,
        start_time,
        end_time,
        room=None
    ):
        academic_year = get_object_or_404(AcademicYear, id=academic_year_id)
        class_subject = get_object_or_404(ClassSubject, id=class_subject_id)
        teacher = get_object_or_404(StaffProfile, id=teacher_id)
        section = get_object_or_404(Section, id=section_id)

        if start_time >= end_time:
            raise ValidationError("Invalid time range")

        return ClassRoutine.objects.create(
            academic_year=academic_year,
            class_subject=class_subject,
            teacher=teacher,
            section=section,
            day=day,
            start_time=start_time,
            end_time=end_time,
            room=room,
        )



# ANALYTICS / SUMMARY SERVICES

class AcademicAnalyticsService:

    @staticmethod
    def get_total_subjects():

        return Subject.objects.filter(
            is_active=True
        ).count()

    @staticmethod
    def get_total_teacher_assignments():

        return TeacherSubjectAssignment.objects.filter(
            is_active=True
        ).count()

    @staticmethod
    def get_total_routines():

        return ClassRoutine.objects.filter(
            is_active=True
        ).count()

    @staticmethod
    def get_current_academic_year():

        return AcademicYear.objects.filter(
            is_current=True
        ).first()