"""
Tests for the academics app.
Covers: AcademicYear, Subject, Class, Section, ClassSubject,
ExamTerm, StudentMark, marks entry, bulk upload views.
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.core.exceptions import ValidationError

from accounts.models import User
from academics.models import (
    AcademicYear, Subject, Class, Section,
    ClassSubject, ExamTerm, StudentMark,
)
from students.models import StudentProfile




def make_admin():
    return User.objects.create_user(
        username="acadmin", email="acadmin@t.com",
        password="pass1234", role=User.Role.ADMIN,
    )

def make_academic_year(name="2024-25", is_current=True):
    from datetime import date
    return AcademicYear.objects.create(
        name=name,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        is_current=is_current,
    )

def make_class(name="Class 5"):
    return Class.objects.create(name=name)

def make_section(cls, name="A"):
    return Section.objects.create(class_obj=cls, name=name)

def make_subject(code="ENG", name="English"):
    return Subject.objects.create(code=code, name=name, credit_hours=1)

def make_class_subject(year, cls, subject):
    return ClassSubject.objects.create(
        academic_year=year, class_obj=cls, subject=subject,
        full_marks=100, pass_marks=40,
    )

def make_exam_term(year, name="First Term"):
    from datetime import date
    return ExamTerm.objects.create(
        academic_year=year, name=name,
        term_type=ExamTerm.TermType.FIRST,
        start_date=date(2024, 3, 1),
        end_date=date(2024, 3, 31),
    )

def make_student(section, roll="001"):
    u = User.objects.create_user(
        username=f"stu_{roll}", email=f"stu_{roll}@t.com",
        password="pass1234", role=User.Role.STUDENT,
    )
    return StudentProfile.objects.create(
        user=u, section=section, roll_number=roll, status="active",
    )



# ACADEMIC YEAR MODEL TESTS

class AcademicYearModelTest(TestCase):

    def test_create_academic_year(self):
        yr = make_academic_year()
        self.assertEqual(str(yr), "2024-25")

    def test_only_one_current_year(self):
        yr1 = make_academic_year(name="2023-24", is_current=True)
        yr2 = make_academic_year(name="2024-25", is_current=True)
        yr1.refresh_from_db()
        self.assertFalse(yr1.is_current)
        self.assertTrue(yr2.is_current)

    def test_invalid_dates_raise_error(self):
        from datetime import date
        yr = AcademicYear(
            name="bad", start_date=date(2024, 12, 31),
            end_date=date(2024, 1, 1),
        )
        with self.assertRaises(ValidationError):
            yr.clean()



# SUBJECT MODEL TESTS

class SubjectModelTest(TestCase):

    def test_create_subject(self):
        s = make_subject()
        self.assertEqual(s.name, "English")
        self.assertEqual(s.code, "ENG")

    def test_subject_str(self):
        s = make_subject()
        self.assertIn("ENG", str(s))

    def test_unique_code(self):
        make_subject(code="MATH", name="Mathematics")
        with self.assertRaises(Exception):
            make_subject(code="MATH", name="Math2")



# CLASS & SECTION MODEL TESTS

class ClassSectionModelTest(TestCase):

    def test_create_class(self):
        cls = make_class()
        self.assertEqual(cls.name, "Class 5")

    def test_create_section(self):
        cls = make_class()
        sec = make_section(cls)
        self.assertEqual(sec.name, "A")
        self.assertEqual(sec.class_obj, cls)

    def test_section_str(self):
        cls = make_class()
        sec = make_section(cls)
        self.assertIn("Class 5", str(sec))
        self.assertIn("A", str(sec))

    def test_unique_section_per_class(self):
        cls = make_class()
        make_section(cls, "A")
        with self.assertRaises(Exception):
            make_section(cls, "A")



# EXAM TERM MODEL TESTS

class ExamTermModelTest(TestCase):

    def test_create_exam_term(self):
        yr = make_academic_year()
        term = make_exam_term(yr)
        self.assertEqual(term.name, "First Term")

    def test_exam_term_str(self):
        yr = make_academic_year()
        term = make_exam_term(yr)
        self.assertIn("First Term", str(term))

    def test_invalid_dates(self):
        from datetime import date
        yr = make_academic_year()
        term = ExamTerm(
            academic_year=yr, name="Bad",
            term_type=ExamTerm.TermType.FIRST,
            start_date=date(2024, 5, 1),
            end_date=date(2024, 3, 1),
        )
        with self.assertRaises(ValidationError):
            term.clean()



# STUDENT MARK MODEL TESTS

class StudentMarkModelTest(TestCase):

    def setUp(self):
        self.yr  = make_academic_year()
        self.cls = make_class()
        self.sec = make_section(self.cls)
        self.sub = make_subject()
        self.cs  = make_class_subject(self.yr, self.cls, self.sub)
        self.term = make_exam_term(self.yr)
        self.student = make_student(self.sec)

    def test_create_mark(self):
        mark = StudentMark.objects.create(
            student=self.student, exam_term=self.term,
            class_subject=self.cs,
            theory_marks=70, practical_marks=10,
            total_marks=80, percentage=80.0,
            grade="A", gpa=3.6,
        )
        self.assertEqual(mark.percentage, 80.0)

    def test_unique_mark_per_student_subject_term(self):
        StudentMark.objects.create(
            student=self.student, exam_term=self.term,
            class_subject=self.cs, total_marks=80, percentage=80.0,
        )
        with self.assertRaises(Exception):
            StudentMark.objects.create(
                student=self.student, exam_term=self.term,
                class_subject=self.cs, total_marks=70, percentage=70.0,
            )



# MANAGE CLASS / SECTION / SUBJECT VIEW TESTS

class ManageClassViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = make_admin()
        self.client.login(username="acadmin", password="pass1234")

    def test_manage_classes_get(self):
        r = self.client.get(reverse("academics:manage_classes"))
        self.assertEqual(r.status_code, 200)

    def test_create_class(self):
        self.client.post(reverse("academics:manage_classes"), {
            "action": "create", "name": "Class 10"
        })
        self.assertTrue(Class.objects.filter(name="Class 10").exists())

    def test_rename_class(self):
        cls = make_class(name="Old Name")
        self.client.post(reverse("academics:manage_classes"), {
            "action": "rename", "pk": cls.pk, "name": "New Name"
        })
        cls.refresh_from_db()
        self.assertEqual(cls.name, "New Name")

    def test_delete_class(self):
        cls = make_class(name="ToDelete")
        self.client.post(reverse("academics:manage_classes"), {
            "action": "delete", "pk": cls.pk
        })
        self.assertFalse(Class.objects.filter(name="ToDelete").exists())


class ManageSectionViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = make_admin()
        self.cls = make_class()
        self.client.login(username="acadmin", password="pass1234")

    def test_manage_sections_get(self):
        r = self.client.get(reverse("academics:manage_sections"))
        self.assertEqual(r.status_code, 200)

    def test_create_section(self):
        self.client.post(reverse("academics:manage_sections"), {
            "action": "create", "class_obj": self.cls.pk, "name": "B"
        })
        self.assertTrue(Section.objects.filter(class_obj=self.cls, name="B").exists())

    def test_delete_section(self):
        sec = make_section(self.cls, "Z")
        self.client.post(reverse("academics:manage_sections"), {
            "action": "delete", "pk": sec.pk
        })
        self.assertFalse(Section.objects.filter(pk=sec.pk).exists())


class ManageSubjectViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = make_admin()
        self.client.login(username="acadmin", password="pass1234")

    def test_manage_subjects_get(self):
        r = self.client.get(reverse("academics:manage_subjects"))
        self.assertEqual(r.status_code, 200)

    def test_create_subject(self):
        self.client.post(reverse("academics:manage_subjects"), {
            "action": "create", "code": "SCI", "name": "Science", "credit_hours": 2
        })
        self.assertTrue(Subject.objects.filter(code="SCI").exists())

    def test_delete_subject(self):
        sub = make_subject(code="DEL", name="ToDelete")
        self.client.post(reverse("academics:manage_subjects"), {
            "action": "delete", "pk": sub.pk
        })
        self.assertFalse(Subject.objects.filter(code="DEL").exists())



# BULK UPLOAD VIEW TESTS

class BulkUploadViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = make_admin()
        self.client.login(username="acadmin", password="pass1234")

    def test_bulk_upload_students_get(self):
        r = self.client.get(reverse("academics:bulk_upload_students"))
        self.assertEqual(r.status_code, 200)

    def test_bulk_upload_marks_get(self):
        r = self.client.get(reverse("academics:bulk_upload_marks"))
        self.assertEqual(r.status_code, 200)

    def test_bulk_upload_staff_get(self):
        r = self.client.get(reverse("academics:bulk_upload_staff"))
        self.assertEqual(r.status_code, 200)

    def test_bulk_upload_students_csv(self):
        import io, openpyxl
        cls = make_class()
        sec = make_section(cls)
        # Create Excel file instead of CSV (view now expects .xlsx)
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["roll_number", "name", "gender"])
        ws.append(["101", "Test Student", "male"])
        ws.append(["102", "Test Two", "female"])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        buf.name = "students.xlsx"
        r = self.client.post(reverse("academics:bulk_upload_students"), {
            "section_id": sec.pk,
            "excel_file": buf,
        })
        self.assertEqual(StudentProfile.objects.filter(section=sec).count(), 2)

    def test_bulk_upload_marks_csv(self):
        import io, openpyxl
        yr   = make_academic_year()
        cls  = make_class(name="Class 6")
        sec  = make_section(cls, "A")
        sub  = make_subject(code="MAT", name="Math")
        cs   = make_class_subject(yr, cls, sub)
        term = make_exam_term(yr, "Second Term")
        stu  = make_student(sec, roll="201")
        # Create Excel file instead of CSV
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["roll_number", "subject", "theory_marks", "practical_marks"])
        ws.append(["201", "Math", 60, 10])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        buf.name = "marks.xlsx"
        self.client.post(reverse("academics:bulk_upload_marks"), {
            "section_id": sec.pk,
            "term_id": term.pk,
            "excel_file": buf,
        })
        self.assertTrue(StudentMark.objects.filter(student=stu, exam_term=term).exists())
