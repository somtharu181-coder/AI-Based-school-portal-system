
# reporting_system/tests.py

import datetime
from django.test import TestCase, Client
from django.urls import reverse

from accounts.models import User
from academics.models import AcademicYear, Class, Section, Subject, ClassSubject, ExamTerm
from students.models import StudentProfile
from reporting_system.models import (
    StudentResult, SubjectResult, ResultCalculationLog,
    ClassResultSummary, StudentTranscript, ReportGenerationLog,
)


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def make_admin():
    return User.objects.create_user(
        username="repadmin", email="repadmin@test.com",
        role=User.Role.ADMIN, password="Pass@1234"
    )


def make_student_user():
    return User.objects.create_user(
        username="repstu", email="repstu@test.com",
        role=User.Role.STUDENT, password="Pass@1234"
    )


def make_academic_year():
    return AcademicYear.objects.create(
        name="2024-25",
        start_date=datetime.date(2024, 1, 1),
        end_date=datetime.date(2024, 12, 31),
        is_current=True,
    )


def make_class_section():
    cls = Class.objects.create(name="Class 10")
    sec = Section.objects.create(class_obj=cls, name="A")
    return cls, sec


def make_student_profile(section, academic_year, roll="001", user=None):
    return StudentProfile.objects.create(
        section=section, academic_year=academic_year,
        roll_number=roll, name="Rep Student", user=user,
        status=StudentProfile.Status.ACTIVE,
    )


def make_exam_term(academic_year):
    return ExamTerm.objects.create(
        academic_year=academic_year,
        name="First Term",
        term_type="first",
        start_date=datetime.date(2024, 3, 1),
        end_date=datetime.date(2024, 3, 31),
        is_published=True,
    )


def make_student_result(student, exam_term, percentage=75.0, gpa=3.2, is_pass=True):
    return StudentResult.objects.create(
        student=student,
        exam_term=exam_term,
        total_obtained_marks=375,
        total_full_marks=500,
        percentage=percentage,
        gpa=gpa,
        grade="B+",
        is_pass=is_pass,
    )


# ─────────────────────────────────────────────
# MODEL TESTS
# ─────────────────────────────────────────────
class StudentResultModelTest(TestCase):

    def setUp(self):
        self.ay = make_academic_year()
        self.cls, self.sec = make_class_section()
        self.sp = make_student_profile(self.sec, self.ay)
        self.term = make_exam_term(self.ay)

    def test_create_student_result(self):
        result = make_student_result(self.sp, self.term)
        self.assertEqual(result.grade, "B+")
        self.assertTrue(result.is_pass)

    def test_str_representation(self):
        result = make_student_result(self.sp, self.term)
        self.assertIn("First Term", str(result))

    def test_unique_per_student_per_term(self):
        make_student_result(self.sp, self.term)
        with self.assertRaises(Exception):
            StudentResult.objects.create(
                student=self.sp, exam_term=self.term,
                total_obtained_marks=300, total_full_marks=500,
                percentage=60.0, gpa=2.8, grade="B", is_pass=True,
            )

    def test_fail_result(self):
        result = make_student_result(self.sp, self.term, percentage=30.0, gpa=0.0, is_pass=False)
        self.assertFalse(result.is_pass)

    def test_percentage_stored_correctly(self):
        result = make_student_result(self.sp, self.term, percentage=88.5)
        self.assertEqual(float(result.percentage), 88.5)


class ResultCalculationLogModelTest(TestCase):

    def setUp(self):
        self.ay = make_academic_year()
        self.cls, self.sec = make_class_section()
        self.sp = make_student_profile(self.sec, self.ay)
        self.term = make_exam_term(self.ay)

    def test_create_log(self):
        log = ResultCalculationLog.objects.create(
            student=self.sp,
            exam_term=self.term,
            action="generated",
            total_marks=375,
            percentage=75.0,
            gpa=3.2,
        )
        self.assertEqual(log.action, "generated")

    def test_multiple_logs_allowed(self):
        ResultCalculationLog.objects.create(
            student=self.sp, exam_term=self.term,
            action="generated", total_marks=375, percentage=75.0, gpa=3.2,
        )
        ResultCalculationLog.objects.create(
            student=self.sp, exam_term=self.term,
            action="updated", total_marks=380, percentage=76.0, gpa=3.2,
        )
        self.assertEqual(ResultCalculationLog.objects.filter(student=self.sp).count(), 2)


class ClassResultSummaryModelTest(TestCase):

    def setUp(self):
        self.ay = make_academic_year()
        self.cls, self.sec = make_class_section()
        self.term = make_exam_term(self.ay)

    def test_create_summary(self):
        summary = ClassResultSummary.objects.create(
            academic_year=self.ay,
            class_obj=self.cls,
            exam_term=self.term,
            average_percentage=72.0,
            highest_percentage=95.0,
            lowest_percentage=40.0,
            total_students=30,
        )
        self.assertEqual(summary.total_students, 30)

    def test_unique_per_year_class_term(self):
        ClassResultSummary.objects.create(
            academic_year=self.ay, class_obj=self.cls, exam_term=self.term,
            average_percentage=72.0, highest_percentage=95.0,
            lowest_percentage=40.0, total_students=30,
        )
        with self.assertRaises(Exception):
            ClassResultSummary.objects.create(
                academic_year=self.ay, class_obj=self.cls, exam_term=self.term,
                average_percentage=70.0, highest_percentage=90.0,
                lowest_percentage=35.0, total_students=28,
            )


# ─────────────────────────────────────────────
# VIEW TESTS
# ─────────────────────────────────────────────
class ReportingDashboardViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = make_admin()
        self.client.login(username="repadmin", password="Pass@1234")

    def test_dashboard_returns_200(self):
        resp = self.client.get(reverse("reporting_system:reporting_dashboard"))
        self.assertEqual(resp.status_code, 200)

    def test_dashboard_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse("reporting_system:reporting_dashboard"))
        self.assertEqual(resp.status_code, 302)


class StudentResultsViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = make_admin()
        self.client.login(username="repadmin", password="Pass@1234")
        self.ay = make_academic_year()
        self.cls, self.sec = make_class_section()
        self.sp = make_student_profile(self.sec, self.ay)
        self.term = make_exam_term(self.ay)

    def test_results_list_returns_200(self):
        resp = self.client.get(reverse("reporting_system:student_results"))
        self.assertEqual(resp.status_code, 200)

    def test_results_list_shows_results(self):
        make_student_result(self.sp, self.term)
        resp = self.client.get(reverse("reporting_system:student_results"))
        self.assertContains(resp, "B+")


class StudentResultDetailViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = make_admin()
        self.client.login(username="repadmin", password="Pass@1234")
        self.ay = make_academic_year()
        self.cls, self.sec = make_class_section()
        self.sp = make_student_profile(self.sec, self.ay)
        self.term = make_exam_term(self.ay)
        self.result = make_student_result(self.sp, self.term)

    def test_detail_returns_200(self):
        resp = self.client.get(
            reverse("reporting_system:student_result_detail", args=[self.result.pk])
        )
        self.assertEqual(resp.status_code, 200)

    def test_detail_shows_grade(self):
        resp = self.client.get(
            reverse("reporting_system:student_result_detail", args=[self.result.pk])
        )
        self.assertContains(resp, "B+")


class MyResultsViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.ay = make_academic_year()
        self.cls, self.sec = make_class_section()
        self.student_user = make_student_user()
        self.sp = make_student_profile(self.sec, self.ay, user=self.student_user)
        self.term = make_exam_term(self.ay)
        self.client.login(username="repstu", password="Pass@1234")

    def test_my_results_returns_200(self):
        resp = self.client.get(reverse("reporting_system:my_results"))
        self.assertEqual(resp.status_code, 200)

    def test_my_results_shows_own_results(self):
        make_student_result(self.sp, self.term)
        resp = self.client.get(reverse("reporting_system:my_results"))
        self.assertContains(resp, "B+")

    def test_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse("reporting_system:my_results"))
        self.assertEqual(resp.status_code, 302)


class AcademicSummaryListViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = make_admin()
        self.client.login(username="repadmin", password="Pass@1234")

    def test_summary_list_returns_200(self):
        resp = self.client.get(reverse("reporting_system:academic_summary_list"))
        self.assertEqual(resp.status_code, 200)


class AuditLogsViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = make_admin()
        self.client.login(username="repadmin", password="Pass@1234")

    def test_audit_logs_returns_200(self):
        resp = self.client.get(reverse("reporting_system:audit_logs"))
        self.assertEqual(resp.status_code, 200)

    def test_filter_by_action(self):
        resp = self.client.get(
            reverse("reporting_system:audit_logs"),
            {"model": "generated"}
        )
        self.assertEqual(resp.status_code, 200)


class DownloadResultPDFViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.ay = make_academic_year()
        self.cls, self.sec = make_class_section()
        self.student_user = make_student_user()
        self.sp = make_student_profile(self.sec, self.ay, user=self.student_user)
        self.term = make_exam_term(self.ay)
        self.result = make_student_result(self.sp, self.term)
        self.client.login(username="repstu", password="Pass@1234")

    def test_pdf_download_returns_pdf(self):
        resp = self.client.get(
            reverse("reporting_system:download_result_pdf", args=[self.result.pk])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")

    def test_pdf_filename_contains_student_id(self):
        resp = self.client.get(
            reverse("reporting_system:download_result_pdf", args=[self.result.pk])
        )
        self.assertIn(self.sp.student_id, resp["Content-Disposition"])

    def test_other_student_cannot_download(self):
        other_user = User.objects.create_user(
            username="other", email="other@test.com",
            role=User.Role.STUDENT, password="Pass@1234"
        )
        self.client.login(username="other", password="Pass@1234")
        resp = self.client.get(
            reverse("reporting_system:download_result_pdf", args=[self.result.pk])
        )
        self.assertEqual(resp.status_code, 404)

    def test_admin_can_download_any_result(self):
        admin = make_admin()
        self.client.login(username="repadmin", password="Pass@1234")
        resp = self.client.get(
            reverse("reporting_system:download_result_pdf", args=[self.result.pk])
        )
        self.assertEqual(resp.status_code, 200)
