
import datetime
from django.test import TestCase, Client
from django.urls import reverse

from accounts.models import User
from academics.models import AcademicYear, Class, Section
from students.models import StudentProfile



# HELPERS

def make_admin():
    return User.objects.create_user(
        username="stuadmin", email="stuadmin@test.com",
        role=User.Role.ADMIN, password="Pass@1234"
    )


def make_student_user(username="stuuser", email="stuuser@test.com"):
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
        section=section,
        academic_year=academic_year,
        roll_number=roll,
        name="Test Student",
        user=user,
        status=StudentProfile.Status.ACTIVE,
    )



# MODEL TESTS

class StudentProfileModelTest(TestCase):

    def setUp(self):
        self.ay = make_academic_year()
        self.cls, self.sec = make_class_and_section()

    def test_create_student_profile(self):
        sp = make_student_profile(self.sec, self.ay)
        self.assertEqual(sp.name, "Test Student")
        self.assertEqual(sp.status, StudentProfile.Status.ACTIVE)

    def test_student_id_auto_generated(self):
        sp = make_student_profile(self.sec, self.ay)
        self.assertIsNotNone(sp.student_id)
        self.assertTrue(len(sp.student_id) > 0)

    def test_student_id_contains_org_id(self):
        sp = make_student_profile(self.sec, self.ay)
        self.assertIn("42019", sp.student_id)

    def test_str_representation(self):
        sp = make_student_profile(self.sec, self.ay)
        self.assertIn("NoUser", str(sp))

    def test_str_with_user(self):
        user = make_student_user()
        sp = make_student_profile(self.sec, self.ay, user=user)
        self.assertIn("stuuser", str(sp))

    def test_unique_roll_per_section_per_year(self):
        make_student_profile(self.sec, self.ay, roll="001")
        with self.assertRaises(Exception):
            make_student_profile(self.sec, self.ay, roll="001")

    def test_default_status_is_active(self):
        sp = make_student_profile(self.sec, self.ay, roll="002")
        self.assertEqual(sp.status, "active")

    def test_default_gender_is_male(self):
        sp = make_student_profile(self.sec, self.ay, roll="003")
        self.assertEqual(sp.gender, "male")

    def test_status_choices(self):
        choices = [c[0] for c in StudentProfile.Status.choices]
        self.assertIn("active", choices)
        self.assertIn("inactive", choices)
        self.assertIn("graduated", choices)
        self.assertIn("dropped", choices)

    def test_user_link_optional(self):
        sp = make_student_profile(self.sec, self.ay, roll="004")
        self.assertIsNone(sp.user)

    def test_email_unique(self):
        StudentProfile.objects.create(
            section=self.sec, academic_year=self.ay,
            roll_number="005", email="unique@test.com"
        )
        with self.assertRaises(Exception):
            StudentProfile.objects.create(
                section=self.sec, academic_year=self.ay,
                roll_number="006", email="unique@test.com"
            )



# VIEW TESTS

class StudentListViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = make_admin()
        self.client.login(username="stuadmin", password="Pass@1234")
        self.ay = make_academic_year()
        self.cls, self.sec = make_class_and_section()

    def test_student_list_returns_200(self):
        resp = self.client.get(reverse("students:student_list"))
        self.assertEqual(resp.status_code, 200)

    def test_student_list_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse("students:student_list"))
        self.assertEqual(resp.status_code, 302)

    def test_student_list_shows_students(self):
        make_student_profile(self.sec, self.ay)
        resp = self.client.get(reverse("students:student_list"))
        self.assertContains(resp, "Test Student")


class StudentDetailViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = make_admin()
        self.client.login(username="stuadmin", password="Pass@1234")
        self.ay = make_academic_year()
        self.cls, self.sec = make_class_and_section()
        self.sp = make_student_profile(self.sec, self.ay)

    def test_detail_returns_200(self):
        resp = self.client.get(reverse("students:student_detail", args=[self.sp.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_detail_shows_student_name(self):
        resp = self.client.get(reverse("students:student_detail", args=[self.sp.pk]))
        self.assertContains(resp, "Test Student")


class CreateStudentViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = make_admin()
        self.client.login(username="stuadmin", password="Pass@1234")
        self.ay = make_academic_year()
        self.cls, self.sec = make_class_and_section()
        self.url = reverse("students:create_student")

    def test_get_returns_200(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_post_creates_student(self):
        self.client.post(self.url, {
            "section": self.sec.pk,
            "academic_year": self.ay.pk,
            "roll_number": "007",
            "name": "New Student",
            "gender": "male",
            "religion_type": "non_religious",
            "status": "active",
        })
        self.assertTrue(StudentProfile.objects.filter(roll_number="007").exists())


class UpdateStudentViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = make_admin()
        self.client.login(username="stuadmin", password="Pass@1234")
        self.ay = make_academic_year()
        self.cls, self.sec = make_class_and_section()
        self.sp = make_student_profile(self.sec, self.ay)

    def test_get_returns_200(self):
        resp = self.client.get(reverse("students:update_student", args=[self.sp.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_post_updates_student(self):
        self.client.post(reverse("students:update_student", args=[self.sp.pk]), {
            "section": self.sec.pk,
            "academic_year": self.ay.pk,
            "roll_number": "001",
            "name": "Updated Name",
            "gender": "female",
            "religion_type": "non_religious",
            "status": "active",
        })
        self.sp.refresh_from_db()
        self.assertEqual(self.sp.name, "Updated Name")


class DeleteStudentViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = make_admin()
        self.client.login(username="stuadmin", password="Pass@1234")
        self.ay = make_academic_year()
        self.cls, self.sec = make_class_and_section()
        self.sp = make_student_profile(self.sec, self.ay)

    def test_get_shows_confirm(self):
        resp = self.client.get(reverse("students:delete_student", args=[self.sp.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_post_deletes_student(self):
        self.client.post(reverse("students:delete_student", args=[self.sp.pk]))
        self.assertFalse(StudentProfile.objects.filter(pk=self.sp.pk).exists())


class UpdateStudentStatusViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = make_admin()
        self.client.login(username="stuadmin", password="Pass@1234")
        self.ay = make_academic_year()
        self.cls, self.sec = make_class_and_section()
        self.sp = make_student_profile(self.sec, self.ay)

    def test_get_returns_200(self):
        resp = self.client.get(reverse("students:update_student_status", args=[self.sp.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_post_updates_status(self):
        self.client.post(
            reverse("students:update_student_status", args=[self.sp.pk]),
            {"status": "graduated"}
        )
        self.sp.refresh_from_db()
        self.assertEqual(self.sp.status, "graduated")


class GetSectionsViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = make_admin()
        self.client.login(username="stuadmin", password="Pass@1234")
        self.cls, self.sec = make_class_and_section()

    def test_returns_json(self):
        resp = self.client.get(
            reverse("students:get_sections"),
            {"class_id": self.cls.pk}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("sections", data)

    def test_returns_correct_sections(self):
        resp = self.client.get(
            reverse("students:get_sections"),
            {"class_id": self.cls.pk}
        )
        data = resp.json()
        names = [s["name"] for s in data["sections"]]
        self.assertIn("A", names)
