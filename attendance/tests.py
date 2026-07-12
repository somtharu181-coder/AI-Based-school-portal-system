
# attendance/tests.py

import datetime
from django.test import TestCase, Client
from django.urls import reverse

from accounts.models import User
from academics.models import AcademicYear, Class, Section
from students.models import StudentProfile
from staff.models import StaffProfile, Designation
from attendance.models import StudentAttendance, StaffAttendance, AttendanceStatus


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def make_admin():
    return User.objects.create_user(
        username="attadmin", email="attadmin@test.com",
        role=User.Role.ADMIN, password="Pass@1234"
    )


def make_staff_user(username="attstaff", email="attstaff@test.com"):
    return User.objects.create_user(
        username=username, email=email,
        role=User.Role.STAFF, password="Pass@1234"
    )


def make_student_user(username="attstu", email="attstu@test.com"):
    return User.objects.create_user(
        username=username, email=email,
        role=User.Role.STUDENT, password="Pass@1234"
    )


def make_academic_year():
    return AcademicYear.objects.create(
        name="2024-25",
        start_date=datetime.date(2024, 1, 1),
        end_date=datetime.date(2024, 12, 31),
        is_current=True,
    )


def make_class_and_section():
    cls = Class.objects.create(name="Class 10")
    sec = Section.objects.create(class_obj=cls, name="A")
    return cls, sec


def make_student_profile(section, academic_year, roll="001", user=None):
    return StudentProfile.objects.create(
        section=section, academic_year=academic_year,
        roll_number=roll, name="Att Student", user=user,
        status=StudentProfile.Status.ACTIVE,
    )


def make_staff_profile(user):
    return StaffProfile.objects.create(user=user, designation=Designation.TEACHER)


# ─────────────────────────────────────────────
# MODEL TESTS
# ─────────────────────────────────────────────
class StudentAttendanceModelTest(TestCase):

    def setUp(self):
        self.ay = make_academic_year()
        self.cls, self.sec = make_class_and_section()
        self.sp = make_student_profile(self.sec, self.ay)
        self.marker = make_admin()

    def test_create_attendance(self):
        att = StudentAttendance.objects.create(
            student=self.sp,
            date=datetime.date(2024, 3, 1),
            status=AttendanceStatus.PRESENT,
            marked_by=self.marker,
        )
        self.assertEqual(att.status, AttendanceStatus.PRESENT)

    def test_str_representation(self):
        att = StudentAttendance.objects.create(
            student=self.sp,
            date=datetime.date(2024, 3, 1),
            status=AttendanceStatus.ABSENT,
            marked_by=self.marker,
        )
        self.assertIn("absent", str(att))

    def test_unique_per_student_per_date(self):
        StudentAttendance.objects.create(
            student=self.sp,
            date=datetime.date(2024, 3, 1),
            status=AttendanceStatus.PRESENT,
            marked_by=self.marker,
        )
        with self.assertRaises(Exception):
            StudentAttendance.objects.create(
                student=self.sp,
                date=datetime.date(2024, 3, 1),
                status=AttendanceStatus.ABSENT,
                marked_by=self.marker,
            )

    def test_attendance_status_choices(self):
        choices = [c[0] for c in AttendanceStatus.choices]
        self.assertIn("present", choices)
        self.assertIn("absent", choices)
        self.assertIn("late", choices)
        self.assertIn("half_day", choices)
        self.assertIn("holiday", choices)

    def test_different_dates_allowed(self):
        StudentAttendance.objects.create(
            student=self.sp, date=datetime.date(2024, 3, 1),
            status=AttendanceStatus.PRESENT, marked_by=self.marker,
        )
        att2 = StudentAttendance.objects.create(
            student=self.sp, date=datetime.date(2024, 3, 2),
            status=AttendanceStatus.ABSENT, marked_by=self.marker,
        )
        self.assertIsNotNone(att2.pk)

    def test_remarks_optional(self):
        att = StudentAttendance.objects.create(
            student=self.sp, date=datetime.date(2024, 3, 3),
            status=AttendanceStatus.LATE, marked_by=self.marker,
        )
        self.assertIsNone(att.remarks)


class StaffAttendanceModelTest(TestCase):

    def setUp(self):
        self.staff_user = make_staff_user()
        self.sp = make_staff_profile(self.staff_user)
        self.marker = make_admin()

    def test_create_staff_attendance(self):
        att = StaffAttendance.objects.create(
            staff=self.sp,
            date=datetime.date(2024, 3, 1),
            status=AttendanceStatus.PRESENT,
            marked_by=self.marker,
        )
        self.assertEqual(att.status, "present")

    def test_unique_per_staff_per_date(self):
        StaffAttendance.objects.create(
            staff=self.sp, date=datetime.date(2024, 3, 1),
            status=AttendanceStatus.PRESENT, marked_by=self.marker,
        )
        with self.assertRaises(Exception):
            StaffAttendance.objects.create(
                staff=self.sp, date=datetime.date(2024, 3, 1),
                status=AttendanceStatus.ABSENT, marked_by=self.marker,
            )


# ─────────────────────────────────────────────
# VIEW TESTS
# ─────────────────────────────────────────────
class MarkAttendanceViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.staff_user = make_staff_user()
        self.client.login(username="attstaff", password="Pass@1234")
        self.ay = make_academic_year()
        self.cls, self.sec = make_class_and_section()

    def test_get_returns_200(self):
        resp = self.client.get(reverse("attendance:mark_student_attendance"))
        self.assertEqual(resp.status_code, 200)

    def test_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse("attendance:mark_student_attendance"))
        self.assertEqual(resp.status_code, 302)


class StudentAttendanceListViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.staff_user = make_staff_user()
        self.client.login(username="attstaff", password="Pass@1234")

    def test_list_returns_200(self):
        resp = self.client.get(reverse("attendance:student_attendance_list"))
        self.assertEqual(resp.status_code, 200)

    def test_filter_by_status(self):
        resp = self.client.get(
            reverse("attendance:student_attendance_list"),
            {"status": "present"}
        )
        self.assertEqual(resp.status_code, 200)


class MyAttendanceViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.ay = make_academic_year()
        self.cls, self.sec = make_class_and_section()
        self.student_user = make_student_user()
        self.sp = make_student_profile(self.sec, self.ay, user=self.student_user)
        self.client.login(username="attstu", password="Pass@1234")

    def test_my_attendance_returns_200(self):
        resp = self.client.get(reverse("attendance:my_attendance"))
        self.assertEqual(resp.status_code, 200)

    def test_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse("attendance:my_attendance"))
        self.assertEqual(resp.status_code, 302)


class GetSectionsByClassViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.staff_user = make_staff_user()
        self.client.login(username="attstaff", password="Pass@1234")
        self.cls, self.sec = make_class_and_section()

    def test_returns_json(self):
        resp = self.client.get(
            reverse("attendance:get_sections"),
            {"class_id": self.cls.pk}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("sections", data)
