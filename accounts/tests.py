"""
Tests for the accounts app.
Covers: User model, login/logout, role-based redirects,
admin dashboard, user CRUD, reset password, change credentials.
"""
from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User



# HELPERS

def make_admin(**kw):
    return User.objects.create_user(
        username=kw.get("username", "admin1"),
        email=kw.get("email", "admin1@test.com"),
        password=kw.get("password", "pass1234"),
        role=User.Role.ADMIN,
    )

def make_student_user(**kw):
    return User.objects.create_user(
        username=kw.get("username", "stu1"),
        email=kw.get("email", "stu1@test.com"),
        password=kw.get("password", "pass1234"),
        role=User.Role.STUDENT,
    )

def make_staff_user(**kw):
    return User.objects.create_user(
        username=kw.get("username", "staff1"),
        email=kw.get("email", "staff1@test.com"),
        password=kw.get("password", "pass1234"),
        role=User.Role.STAFF,
    )



# USER MODEL TESTS

class UserModelTest(TestCase):

    def test_create_user_default_role(self):
        u = User.objects.create_user(username="u1", email="u1@t.com", password="x")
        self.assertEqual(u.role, User.Role.STUDENT)

    def test_admin_role(self):
        u = make_admin()
        self.assertEqual(u.role, User.Role.ADMIN)

    def test_str_representation(self):
        u = make_admin()
        self.assertIn("admin1", str(u))

    def test_email_unique(self):
        make_admin(username="a1", email="same@t.com")
        with self.assertRaises(Exception):
            make_admin(username="a2", email="same@t.com")

    def test_username_unique(self):
        make_admin(username="same", email="e1@t.com")
        with self.assertRaises(Exception):
            make_admin(username="same", email="e2@t.com")



# LOGIN / LOGOUT TESTS

class LoginLogoutTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = make_admin()
        self.student = make_student_user()

    def test_login_page_get(self):
        r = self.client.get(reverse("accounts:login"))
        self.assertEqual(r.status_code, 200)

    def test_login_valid_admin(self):
        r = self.client.post(reverse("accounts:login"), {
            "username": "admin1", "password": "pass1234"
        })
        self.assertRedirects(r, reverse("accounts:dashboard"))

    def test_login_valid_student(self):
        r = self.client.post(reverse("accounts:login"), {
            "username": "stu1", "password": "pass1234"
        })
        self.assertRedirects(r, reverse("accounts:student_dashboard"))

    def test_login_invalid_credentials(self):
        r = self.client.post(reverse("accounts:login"), {
            "username": "admin1", "password": "wrong"
        })
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Invalid")

    def test_logout_redirects_to_login(self):
        self.client.login(username="admin1", password="pass1234")
        r = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(r, reverse("accounts:login"))

    def test_logged_in_user_redirected_from_login(self):
        self.client.login(username="admin1", password="pass1234")
        r = self.client.get(reverse("accounts:login"))
        self.assertEqual(r.status_code, 302)



# ADMIN DASHBOARD TESTS

class AdminDashboardTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = make_admin()
        self.student = make_student_user()

    def test_admin_can_access_dashboard(self):
        self.client.login(username="admin1", password="pass1234")
        r = self.client.get(reverse("accounts:dashboard"))
        self.assertEqual(r.status_code, 200)

    def test_student_cannot_access_admin_dashboard(self):
        self.client.login(username="stu1", password="pass1234")
        r = self.client.get(reverse("accounts:dashboard"))
        self.assertNotEqual(r.status_code, 200)

    def test_unauthenticated_redirected(self):
        r = self.client.get(reverse("accounts:dashboard"))
        self.assertEqual(r.status_code, 302)

    def test_dashboard_context_has_total_users(self):
        self.client.login(username="admin1", password="pass1234")
        r = self.client.get(reverse("accounts:dashboard"))
        self.assertIn("total_users", r.context)

    def test_dashboard_context_has_class_list(self):
        self.client.login(username="admin1", password="pass1234")
        r = self.client.get(reverse("accounts:dashboard"))
        self.assertIn("class_list", r.context)

    def test_dashboard_context_has_section_list(self):
        self.client.login(username="admin1", password="pass1234")
        r = self.client.get(reverse("accounts:dashboard"))
        self.assertIn("section_list", r.context)

    def test_dashboard_context_has_users_for_reset(self):
        self.client.login(username="admin1", password="pass1234")
        r = self.client.get(reverse("accounts:dashboard"))
        self.assertIn("users_for_reset", r.context)



# USER CRUD TESTS

class UserCRUDTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = make_admin()
        self.client.login(username="admin1", password="pass1234")

    def test_user_list_accessible(self):
        r = self.client.get(reverse("accounts:user_list"))
        self.assertEqual(r.status_code, 200)

    def test_create_user_get(self):
        r = self.client.get(reverse("accounts:create_user"))
        self.assertEqual(r.status_code, 200)

    def test_create_user_post(self):
        r = self.client.post(reverse("accounts:create_user"), {
            "username": "newuser",
            "email": "newuser@t.com",
            "phone": "9800000099",
            "password1": "testpass123!",
            "password2": "testpass123!",
            "role": "student",
        })
        self.assertTrue(User.objects.filter(username="newuser").exists())

    def test_update_user_get(self):
        u = make_student_user(username="upd1", email="upd1@t.com")
        r = self.client.get(reverse("accounts:update_user", args=[u.pk]))
        self.assertEqual(r.status_code, 200)

    def test_delete_user_post(self):
        u = make_student_user(username="del1", email="del1@t.com")
        self.client.post(reverse("accounts:delete_user", args=[u.pk]))
        self.assertFalse(User.objects.filter(username="del1").exists())


# RESET PASSWORD TESTS

class ResetPasswordTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = make_admin()
        self.target = make_student_user(username="target1", email="target1@t.com")
        self.client.login(username="admin1", password="pass1234")

    def test_reset_page_get(self):
        r = self.client.get(reverse("accounts:reset_user_password", args=[self.target.pk]))
        self.assertEqual(r.status_code, 200)

    def test_reset_password_success(self):
        r = self.client.post(reverse("accounts:reset_user_password", args=[self.target.pk]), {
            "new_password": "newpass123",
            "confirm_password": "newpass123",
        })
        self.assertRedirects(r, reverse("accounts:user_list"))
        self.target.refresh_from_db()
        self.assertTrue(self.target.check_password("newpass123"))

    def test_reset_password_mismatch(self):
        r = self.client.post(reverse("accounts:reset_user_password", args=[self.target.pk]), {
            "new_password": "newpass123",
            "confirm_password": "different",
        })
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "do not match")

    def test_reset_password_too_short(self):
        r = self.client.post(reverse("accounts:reset_user_password", args=[self.target.pk]), {
            "new_password": "abc",
            "confirm_password": "abc",
        })
        self.assertEqual(r.status_code, 200)

    def test_student_cannot_reset_password(self):
        self.client.logout()
        self.client.login(username="target1", password="pass1234")
        r = self.client.get(reverse("accounts:reset_user_password", args=[self.target.pk]))
        self.assertNotEqual(r.status_code, 200)
