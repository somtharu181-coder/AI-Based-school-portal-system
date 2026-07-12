import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import transaction

from academics.models import StudentMark
from students.models import StudentProfile

from .models import (
    StudentResult,
    ClassResultSummary,
    ReportGenerationLog,
)

logger = logging.getLogger(__name__)



# SAFE LOG HELPER

def log_event(level, message):
    if level == "info":
        logger.info(message)
    elif level == "warning":
        logger.warning(message)
    elif level == "error":
        logger.error(message)
    else:
        logger.debug(message)



# STUDENT RESULT AUTO GENERATION

@receiver(post_save, sender=StudentMark)
def generate_student_result(sender, instance, created, **kwargs):

    def _process():
        student = instance.student
        exam_term = instance.exam_term

        marks = StudentMark.objects.filter(
            student=student,
            exam_term=exam_term
        )

        total = 0
        max_total = 0

        for m in marks:
            total += float(m.total_marks or 0)
            max_total += float(m.class_subject.full_marks or 100)

        percentage = (total / max_total) * 100 if max_total > 0 else 0

        grade = "F"
        gpa = 0.0
        is_pass = percentage >= 40

        if percentage >= 90:
            grade, gpa = "A+", 4.0
        elif percentage >= 80:
            grade, gpa = "A", 3.6
        elif percentage >= 70:
            grade, gpa = "B+", 3.2
        elif percentage >= 60:
            grade, gpa = "B", 2.8
        elif percentage >= 50:
            grade, gpa = "C", 2.4
        elif percentage >= 40:
            grade, gpa = "D", 2.0

        StudentResult.objects.update_or_create(
            student=student,
            exam_term=exam_term,
            defaults={
                "total_obtained_marks": total,
                "total_full_marks": max_total,
                "percentage": percentage,
                "grade": grade,
                "gpa": gpa,
                "is_pass": is_pass,
            }
        )

        log_event("info", f"Result updated: {student} | {exam_term}")

    transaction.on_commit(_process)



# CLASS RESULT SUMMARY UPDATE

@receiver(post_save, sender=StudentResult)
@receiver(post_delete, sender=StudentResult)
def update_class_summary(sender, instance, **kwargs):

    def _process():
        exam_term = instance.exam_term

        all_results = StudentResult.objects.filter(
            exam_term=exam_term
        )

        total_students = all_results.values("student").distinct().count()
        total_pass = all_results.filter(is_pass=True).count()
        total_fail = all_results.filter(is_pass=False).count()

        percentages = list(all_results.values_list("percentage", flat=True))

        avg = sum(percentages) / len(percentages) if percentages else 0
        highest = max(percentages) if percentages else 0
        lowest = min(percentages) if percentages else 0

        ClassResultSummary.objects.update_or_create(
            academic_year=exam_term.academic_year,
            class_obj=instance.student.section.class_obj if hasattr(instance.student, "section") and instance.student.section else None,
            exam_term=exam_term,
            defaults={
                "average_percentage": avg,
                "highest_percentage": highest,
                "lowest_percentage": lowest,
                "total_students": total_students,
            }
        )

        log_event("info", f"Class summary updated: {exam_term}")

    transaction.on_commit(_process)



# BASIC AUDIT LOGGER

@receiver(post_save, sender=StudentResult)
def audit_student_result(sender, instance, created, **kwargs):

    def _process():
        ReportGenerationLog.objects.create(
            student=instance.student,
            generated_by=None,
            report_type="result",
            status="generated" if created else "updated",
        )

        log_event("info", f"Audit logged: StudentResult {instance}")

    transaction.on_commit(_process)