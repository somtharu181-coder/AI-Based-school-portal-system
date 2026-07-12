from django.db import transaction
from django.db.models import Sum, Avg

from academics.models import ClassSubject, ExamTerm
from students.models import StudentProfile

from .models import (
    StudentResult,
    SubjectResult,
    ResultCalculationLog,
    StudentTranscript,
    ClassResultSummary,
)



# GRADE ENGINE (CORE LOGIC)

class GradeEngine:

    @staticmethod
    def get_grade(percentage):
        if percentage >= 90:
            return "A+"
        elif percentage >= 80:
            return "A"
        elif percentage >= 70:
            return "B+"
        elif percentage >= 60:
            return "B"
        elif percentage >= 50:
            return "C"
        elif percentage >= 40:
            return "D"
        return "F"

    @staticmethod
    def get_gpa(percentage):
        if percentage >= 90:
            return 4.0
        elif percentage >= 80:
            return 3.6
        elif percentage >= 70:
            return 3.2
        elif percentage >= 60:
            return 2.8
        elif percentage >= 50:
            return 2.4
        elif percentage >= 40:
            return 2.0
        return 0.0



# RESULT ENGINE (MAIN SERVICE)

class ResultService:

    @staticmethod
    @transaction.atomic
    def generate_student_result(student, exam_term):
        """
        Main function: generates full result of a student
        """

        class_subjects = ClassSubject.objects.filter(
            class_obj=student.section.class_obj
        )

        total_obtained = 0
        total_full = 0

        student_result, _ = StudentResult.objects.update_or_create(
            student=student,
            exam_term=exam_term,
            defaults={
                "total_obtained_marks": 0,
                "total_full_marks": 0,
                "percentage": 0,
                "gpa": 0,
                "grade": "",
                "is_pass": False,
            }
        )

        for cs in class_subjects:

            # Example: fetch marks from academics.StudentMark
            mark_obj = cs.student_marks.filter(
                student=student,
                exam_term=exam_term
            ).first()

            theory = mark_obj.theory_marks if mark_obj else 0
            practical = mark_obj.practical_marks if mark_obj else 0

            total = theory + practical

            percentage = (total / cs.full_marks) * 100 if cs.full_marks else 0

            grade = GradeEngine.get_grade(percentage)
            is_pass = percentage >= cs.pass_marks

            SubjectResult.objects.update_or_create(
                student_result=student_result,
                class_subject=cs,
                defaults={
                    "theory_marks":   theory,
                    "practical_marks": practical,
                    "total_marks":    total,
                    "percentage":     percentage,
                    "grade":          grade,
                    "is_pass":        is_pass,
                }
            )

            total_obtained += total
            total_full += cs.full_marks

        # FINAL CALCULATION
        percentage = (total_obtained / total_full) * 100 if total_full else 0
        gpa = GradeEngine.get_gpa(percentage)
        grade = GradeEngine.get_grade(percentage)

        student_result.total_obtained_marks = total_obtained
        student_result.total_full_marks = total_full
        student_result.percentage = percentage
        student_result.gpa = gpa
        student_result.grade = grade
        student_result.is_pass = percentage >= 40
        student_result.save()

        # LOGGING
        ResultCalculationLog.objects.create(
            student=student,
            exam_term=exam_term,
            action="generated",
            total_marks=total_obtained,
            percentage=percentage,
            gpa=gpa
        )

        return student_result



# RANKING ENGINE

class RankingService:

    @staticmethod
    def assign_ranks(exam_term, class_obj):
        """
        Assign ranks for a class in an exam
        """

        results = StudentResult.objects.filter(
            exam_term=exam_term,
            student__section__class_obj=class_obj
        ).order_by("-percentage")

        rank = 1

        for r in results:
            r.rank = rank
            r.save(update_fields=["rank"])
            rank += 1



# CLASS REPORT ENGINE

class ClassReportService:

    @staticmethod
    @transaction.atomic
    def generate_class_summary(exam_term, class_obj, academic_year):
        """
        Generates class-level analytics
        """

        results = StudentResult.objects.filter(
            exam_term=exam_term,
            student__section__class_obj=class_obj
        )

        avg = results.aggregate(avg=Avg("percentage"))["avg"] or 0
        high = results.order_by("-percentage").first()
        low = results.order_by("percentage").first()

        summary, created = ClassResultSummary.objects.get_or_create(
            exam_term=exam_term,
            class_obj=class_obj,
            academic_year=academic_year,
            defaults={
                "average_percentage": avg,
                "highest_percentage": high.percentage if high else 0,
                "lowest_percentage": low.percentage if low else 0,
                "total_students": results.count()
            }
        )

        return summary



# TRANSCRIPT ENGINE

class TranscriptService:

    @staticmethod
    @transaction.atomic
    def generate_transcript(student, academic_year):
        """
        Final year transcript generator
        """

        results = StudentResult.objects.filter(
            student=student,
            exam_term__academic_year=academic_year
        )

        avg_gpa = results.aggregate(avg=Avg("gpa"))["avg"] or 0

        if avg_gpa >= 3.6:
            final_grade = "A"
        elif avg_gpa >= 3.0:
            final_grade = "B"
        elif avg_gpa >= 2.0:
            final_grade = "C"
        else:
            final_grade = "F"

        transcript, created = StudentTranscript.objects.get_or_create(
            student=student,
            academic_year=academic_year,
            defaults={
                "total_gpa": avg_gpa,
                "final_grade": final_grade,
                "is_promoted": avg_gpa >= 2.0,
                "remarks": "Generated automatically by system"
            }
        )

        return transcript