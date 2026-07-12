
# staff/tests.py

from django.test import TestCase, Client
from django.urls import reverse

from accounts.models import User
from staff.models import StaffProfile, Department, Designation



# HELPERS

def make_admin():
    return User.objects.create_user(
        username="staffadmin", email="staffadmin@test.com",
        role=User.Role.ADMIN, password="Pass@1234"
    )


def make_staff_user(username="staffuser", email="staffuser@test.com"):
    return User.objects.create_user(
        username=username, email=email,
        role=User.Role.STAFF, password="Pass@1234"
    )


def make_department(name="Science"):
    return Department.objects.create(name=name)


def make_staff_profile(user, designation=Designation.TEACHER, department=None):
    return StaffProfile.objects.create(
        user=user,
        designation=designation,
        department=department,
        phone="9800000001",
        salary=30000,
    )



# MODEL TESTS

class DepartmentModelTest(TestCase):

    def test_create_department(self):
        dept = make_department()
        self.assertEqual(str(dept), "Science")

    def test_department_unique_name(self):
        make_department()
        with self.assertRaises(Exception):
            Department.objects.create(name="Science")


class StaffProfileModelTest(TestCase):

    def test_create_staff_profile(self):
        user = make_staff_user()
        sp = make_staff_profile(user)
        self.assertEqual(sp.user, user)
        self.assertEqual(sp.designation, Designation.TEACHER)

    def test_staff_id_auto_generated(self):
        user = make_staff_user()
        sp = make_staff_profile(user)
        self.assertIsNotNone(sp.staff_id)
        self.assertTrue(sp.staff_id.startswith("STF-"))

    def test_staff_id_unique(self):
        user1 = make_staff_user("s1", "s1@test.com")
        user2 = make_staff_user("s2", "s2@test.com")
        sp1 = make_staff_profile(user1)
        sp2 = make_staff_profile(user2)
        self.assertNotEqual(sp1.staff_id, sp2.staff_id)

    def test_str_representation(self):
        user = make_staff_user()
        sp = make_staff_profile(user)
        self.assertIn("STF-", str(sp))
        self.assertIn("staffuser", str(sp))

    def test_one_user_one_staff_profile(self):
        user = make_staff_user()
        make_staff_profile(user)
        with self.assertRaises(Exception):
            StaffProfile.objects.create(
                user=user,
                designation=Designation.PRINCIPAL,
            )

    def test_is_active_default_true(self):
        user = make_staff_user()
        sp = make_staff_profile(user)
        self.assertTrue(sp.is_active)

    def test_department_optional(self):
        user = make_staff_user()
        sp = make_staff_profile(user, department=None)
        self.assertIsNone(sp.department)

    def test_designation_choices(self):
        choices = [c[0] for c in Designation.choices]
        self.assertIn("teacher", choices)
        self.assertIn("principal", choices)
        self.assertIn("accountant", choices)



# VIEW TESTS

class StaffListViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = make_admin()
        self.client.login(username="staffadmin", password="Pass@1234")

    def test_staff_list_returns_200(self):
        resp = self.client.get(reverse("staff:staff_list"))
        self.assertEqual(resp.status_code, 200)

    def test_staff_list_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse("staff:staff_list"))
        self.assertEqual(resp.status_code, 302)

    def test_staff_list_shows_staff(self):
        user = make_staff_user()
        sp = make_staff_profile(user)
        resp = self.client.get(reverse("staff:staff_list"))
        self.assertContains(resp, sp.staff_id)


class StaffDetailViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = make_admin()
        self.client.login(username="staffadmin", password="Pass@1234")
        user = make_staff_user()
        self.sp = make_staff_profile(user)

    def test_detail_returns_200(self):
        resp = self.client.get(reverse("staff:staff_detail", args=[self.sp.staff_id]))
        self.assertEqual(resp.status_code, 200)

    def test_detail_shows_staff_id(self):
        resp = self.client.get(reverse("staff:staff_detail", args=[self.sp.staff_id]))
        self.assertContains(resp, self.sp.staff_id)


class StaffCreateViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = make_admin()
        self.client.login(username="staffadmin", password="Pass@1234")
        self.url = reverse("staff:staff_create")

    def test_get_returns_200(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_post_creates_staff(self):
        user = make_staff_user()
        self.client.post(self.url, {
            "user": user.pk,
            "designation": "teacher",
        })
        self.assertTrue(StaffProfile.objects.filter(user=user).exists())


class StaffUpdateViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = make_admin()
        self.client.login(username="staffadmin", password="Pass@1234")
        user = make_staff_user()
        self.sp = make_staff_profile(user)

    def test_get_returns_200(self):
        resp = self.client.get(reverse("staff:staff_update", args=[self.sp.staff_id]))
        self.assertEqual(resp.status_code, 200)

    def test_post_updates_phone(self):
        self.client.post(
            reverse("staff:staff_update", args=[self.sp.staff_id]),
            {
                "designation": "teacher",
                "phone": "9811111111",
                "salary": "35000",
                "address": "Kathmandu",
            }
        )
        self.sp.refresh_from_db()
        self.assertEqual(self.sp.phone, "9811111111")


class StaffDeleteViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = make_admin()
        self.client.login(username="staffadmin", password="Pass@1234")
        user = make_staff_user()
        self.sp = make_staff_profile(user)

    def test_post_deletes_staff(self):
        staff_id = self.sp.staff_id
        self.client.post(reverse("staff:staff_delete", args=[staff_id]))
        self.assertFalse(StaffProfile.objects.filter(staff_id=staff_id).exists())
