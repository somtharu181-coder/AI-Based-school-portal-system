from django.utils import timezone
from django.db import transaction
from .models import Assignment, Submission


def create_assignment(teacher_user, class_subject, section, title, description, due_date, max_marks=10):
    return Assignment.objects.create(
        teacher=teacher_user, class_subject=class_subject,
        section=section, title=title, description=description,
        due_date=due_date, max_marks=max_marks, status=Assignment.Status.PUBLISHED,
    )


def get_assignments_for_teacher(teacher_user):
    return Assignment.objects.filter(teacher=teacher_user).select_related(
        "class_subject__subject", "class_subject__class_obj", "section"
    )


def get_assignments_for_student(student_profile):
    return Assignment.objects.filter(
        section=student_profile.section,
        status=Assignment.Status.PUBLISHED,
    ).select_related("class_subject__subject", "teacher")


def submit_assignment(assignment, student, answer):
    sub, _ = Submission.objects.update_or_create(
        assignment=assignment, student=student,
        defaults={"answer": answer},
    )
    return sub


@transaction.atomic
def check_submission(submission_pk, teacher_user, marks, grade, feedback):
    sub = Submission.objects.select_for_update().get(pk=submission_pk)
    sub.marks      = marks
    sub.grade      = grade
    sub.feedback   = feedback
    sub.checked_at = timezone.now()
    sub.checked_by = teacher_user
    sub.save()
    return sub


def get_submissions_for_assignment(assignment_pk):
    return Submission.objects.filter(assignment_id=assignment_pk).select_related("student__user")
