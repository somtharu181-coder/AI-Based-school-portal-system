"""
Tests for the analytics app.
Covers: presentation_helpers (pure functions), analytics views,
prediction realism, recommendation content.
No existing logic is modified — tests only verify outputs.
"""
from django.test import TestCase, Client
from django.urls import reverse

from accounts.models import User
from analytics.presentation_helpers import (
    percentage_to_grade,
    percentage_to_gpa,
    risk_from_percentage,
    build_subject_prediction_table,
    build_term_forecast,
    build_subject_ranking,
    build_performance_insights,
    build_student_outlook,
    build_subject_timeline,
)



# GRADE / GPA / RISK HELPERS

class GradeHelperTest(TestCase):

    def test_grade_a_plus(self):
        self.assertEqual(percentage_to_grade(95), "A+")

    def test_grade_a(self):
        self.assertEqual(percentage_to_grade(85), "A")

    def test_grade_b_plus(self):
        self.assertEqual(percentage_to_grade(72), "B+")

    def test_grade_b(self):
        self.assertEqual(percentage_to_grade(62), "B")

    def test_grade_c_plus(self):
        self.assertEqual(percentage_to_grade(52), "C+")

    def test_grade_c(self):
        self.assertEqual(percentage_to_grade(47), "C")

    def test_grade_d(self):
        self.assertEqual(percentage_to_grade(42), "D")

    def test_grade_f(self):
        self.assertEqual(percentage_to_grade(30), "F")

    def test_grade_boundary_40(self):
        self.assertEqual(percentage_to_grade(40), "D")

    def test_grade_boundary_39(self):
        self.assertEqual(percentage_to_grade(39), "F")


class GpaHelperTest(TestCase):

    def test_gpa_range_valid(self):
        for p in [0, 10, 40, 50, 60, 70, 80, 90, 100]:
            gpa = percentage_to_gpa(p)
            self.assertGreaterEqual(gpa, 0.0)
            self.assertLessEqual(gpa, 4.0)

    def test_gpa_monotonic(self):
        self.assertGreaterEqual(percentage_to_gpa(80), percentage_to_gpa(70))
        self.assertGreaterEqual(percentage_to_gpa(70), percentage_to_gpa(60))
        self.assertGreaterEqual(percentage_to_gpa(60), percentage_to_gpa(50))

    def test_gpa_top(self):
        self.assertEqual(percentage_to_gpa(95), 4.0)

    def test_gpa_fail(self):
        self.assertEqual(percentage_to_gpa(30), 0.0)


class RiskHelperTest(TestCase):

    def test_high_risk_below_40(self):
        self.assertEqual(risk_from_percentage(35), "high")

    def test_medium_risk(self):
        self.assertEqual(risk_from_percentage(50), "medium")

    def test_low_risk(self):
        self.assertEqual(risk_from_percentage(75), "low")

    def test_high_risk_with_failures(self):
        self.assertEqual(risk_from_percentage(65, failed_count=2), "high")



# SUBJECT PREDICTION TABLE

SAMPLE_PREDS = [
    {"subject": "English",  "past_percentages": [76.0, 88.0], "predicted_percentage": 92.0, "trend": "improving"},
    {"subject": "Social",   "past_percentages": [65.0, 47.0], "predicted_percentage": 42.0, "trend": "declining"},
    {"subject": "Computer", "past_percentages": [46.0, 86.0], "predicted_percentage": 90.0, "trend": "improving"},
]

class SubjectPredictionTableTest(TestCase):

    def test_empty_input(self):
        self.assertEqual(build_subject_prediction_table([]), [])

    def test_length_preserved(self):
        result = build_subject_prediction_table(SAMPLE_PREDS)
        self.assertEqual(len(result), 3)

    def test_sorted_descending(self):
        result = build_subject_prediction_table(SAMPLE_PREDS)
        pcts = [r["predicted_pct"] for r in result]
        self.assertEqual(pcts, sorted(pcts, reverse=True))

    def test_confidence_clamped(self):
        result = build_subject_prediction_table(SAMPLE_PREDS)
        for r in result:
            self.assertGreaterEqual(r["confidence_pct"], 0)
            self.assertLessEqual(r["confidence_pct"], 100)

    def test_previous_term_none_when_single_data(self):
        preds = [{"subject": "X", "past_percentages": [70.0], "predicted_percentage": 72.0, "trend": "stable"}]
        result = build_subject_prediction_table(preds)
        self.assertIsNone(result[0]["previous_term_pct"])

    def test_has_grade_field(self):
        result = build_subject_prediction_table(SAMPLE_PREDS)
        for r in result:
            self.assertIn(r["predicted_grade"], ["A+","A","B+","B","C+","C","D","F"])



# TERM FORECAST

class TermForecastTest(TestCase):

    def test_empty_input(self):
        self.assertEqual(build_term_forecast([], {}), [])

    def test_last_row_is_predicted(self):
        result = build_term_forecast(SAMPLE_PREDS, {"failed_count": 0})
        self.assertTrue(result[-1]["is_predicted"])

    def test_past_rows_not_predicted(self):
        result = build_term_forecast(SAMPLE_PREDS, {"failed_count": 0})
        for row in result[:-1]:
            self.assertFalse(row["is_predicted"])

    def test_numeric_fields_rounded(self):
        result = build_term_forecast(SAMPLE_PREDS, {"failed_count": 0})
        for row in result:
            self.assertIsInstance(row["avg_percentage"], float)



# SUBJECT RANKING

class SubjectRankingTest(TestCase):

    def test_empty_input(self):
        result = build_subject_ranking([])
        self.assertEqual(result["strongest"], [])
        self.assertEqual(result["needs_attention"], [])

    def test_strongest_max_3(self):
        result = build_subject_ranking(SAMPLE_PREDS)
        self.assertLessEqual(len(result["strongest"]), 3)

    def test_needs_attention_max_3(self):
        result = build_subject_ranking(SAMPLE_PREDS)
        self.assertLessEqual(len(result["needs_attention"]), 3)

    def test_total_subjects_count(self):
        result = build_subject_ranking(SAMPLE_PREDS)
        self.assertEqual(result["total_subjects"], 3)

    def test_pass_fail_sum(self):
        result = build_subject_ranking(SAMPLE_PREDS)
        self.assertEqual(result["pass_count"] + result["fail_count"], 3)

    def test_declining_subject_in_needs_attention(self):
        result = build_subject_ranking(SAMPLE_PREDS)
        subjects = [s["subject"] for s in result["needs_attention"]]
        # Social is declining — should appear in needs_attention
        self.assertIn("Social", subjects)



# PERFORMANCE INSIGHTS

class PerformanceInsightsTest(TestCase):

    def test_empty_input(self):
        self.assertEqual(build_performance_insights([], []), [])

    def test_max_8_insights(self):
        result = build_performance_insights(SAMPLE_PREDS, [])
        self.assertLessEqual(len(result), 8)

    def test_all_strings(self):
        result = build_performance_insights(SAMPLE_PREDS, [])
        for ins in result:
            self.assertIsInstance(ins, str)

    def test_no_algorithm_names(self):
        result = build_performance_insights(SAMPLE_PREDS, [])
        forbidden = ["LinearRegression", "Scikit", "cosine", "XGBoost", "Content-Based"]
        for ins in result:
            for word in forbidden:
                self.assertNotIn(word, ins)

    def test_improving_subject_mentioned(self):
        result = build_performance_insights(SAMPLE_PREDS, [])
        text = " ".join(result)
        self.assertIn("English", text)

    def test_declining_subject_mentioned(self):
        result = build_performance_insights(SAMPLE_PREDS, [])
        text = " ".join(result)
        self.assertIn("Social", text)



# STUDENT OUTLOOK

class StudentOutlookTest(TestCase):

    def test_empty_predictions(self):
        result = build_student_outlook([], {"attendance_percentage": 80})
        self.assertIn("predicted_avg_pct", result)
        self.assertIn("chart_data", result)

    def test_all_keys_present(self):
        result = build_student_outlook(SAMPLE_PREDS, {"attendance_percentage": 80})
        required = [
            "predicted_avg_pct", "predicted_gpa", "predicted_grade",
            "predicted_risk_level", "predicted_pass_count",
            "predicted_fail_count", "attendance_impact", "chart_data",
        ]
        for key in required:
            self.assertIn(key, result)

    def test_pass_plus_fail_equals_total(self):
        result = build_student_outlook(SAMPLE_PREDS, {"attendance_percentage": 80})
        self.assertEqual(
            result["predicted_pass_count"] + result["predicted_fail_count"],
            len(SAMPLE_PREDS)
        )

    def test_attendance_impact_positive(self):
        result = build_student_outlook(SAMPLE_PREDS, {"attendance_percentage": 80})
        self.assertEqual(result["attendance_impact"], "Positive")

    def test_attendance_impact_at_risk(self):
        result = build_student_outlook(SAMPLE_PREDS, {"attendance_percentage": 50})
        self.assertEqual(result["attendance_impact"], "At Risk")

    def test_attendance_impact_neutral(self):
        result = build_student_outlook(SAMPLE_PREDS, {"attendance_percentage": 65})
        self.assertEqual(result["attendance_impact"], "Neutral")



# SUBJECT TIMELINE

class SubjectTimelineTest(TestCase):

    def test_empty_input(self):
        self.assertEqual(build_subject_timeline([]), [])

    def test_length_preserved(self):
        result = build_subject_timeline(SAMPLE_PREDS)
        self.assertEqual(len(result), 3)

    def test_last_point_is_predicted(self):
        result = build_subject_timeline(SAMPLE_PREDS)
        for item in result:
            self.assertTrue(item["timeline"][-1]["is_predicted"])

    def test_timeline_length(self):
        result = build_subject_timeline(SAMPLE_PREDS)
        for i, item in enumerate(result):
            past_len = len(SAMPLE_PREDS[i]["past_percentages"])
            self.assertEqual(len(item["timeline"]), past_len + 1)



# ANALYTICS VIEWS

class AnalyticsViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username="anadmin", email="anadmin@t.com",
            password="pass1234", role=User.Role.ADMIN,
        )
        self.staff = User.objects.create_user(
            username="anastaff", email="anastaff@t.com",
            password="pass1234", role=User.Role.STAFF,
        )
        self.student = User.objects.create_user(
            username="anastudent", email="anastudent@t.com",
            password="pass1234", role=User.Role.STUDENT,
        )

    def test_analytics_dashboard_admin(self):
        self.client.login(username="anadmin", password="pass1234")
        r = self.client.get(reverse("analytics:analytics_dashboard"))
        self.assertEqual(r.status_code, 200)

    def test_analytics_dashboard_unauthenticated(self):
        r = self.client.get(reverse("analytics:analytics_dashboard"))
        self.assertEqual(r.status_code, 302)

    def test_teacher_view_admin(self):
        self.client.login(username="anadmin", password="pass1234")
        r = self.client.get(reverse("analytics:teacher_analytics"))
        self.assertEqual(r.status_code, 200)

    def test_teacher_view_staff(self):
        self.client.login(username="anastaff", password="pass1234")
        r = self.client.get(reverse("analytics:teacher_analytics"))
        self.assertEqual(r.status_code, 200)

    def test_teacher_view_student_blocked(self):
        self.client.login(username="anastudent", password="pass1234")
        r = self.client.get(reverse("analytics:teacher_analytics"))
        self.assertNotEqual(r.status_code, 200)

    def test_principal_view_admin(self):
        self.client.login(username="anadmin", password="pass1234")
        r = self.client.get(reverse("analytics:principal_analytics"))
        self.assertEqual(r.status_code, 200)

    def test_principal_view_staff_blocked(self):
        self.client.login(username="anastaff", password="pass1234")
        r = self.client.get(reverse("analytics:principal_analytics"))
        self.assertNotEqual(r.status_code, 200)

    def test_my_ai_report_redirects_without_profile(self):
        self.client.login(username="anastudent", password="pass1234")
        r = self.client.get(reverse("analytics:my_ai_report"))
        self.assertEqual(r.status_code, 302)



# PREDICTION REALISM TESTS

class PredictionRealismTest(TestCase):
    """
    Verify the dampened prediction logic in services.py
    without touching the existing algorithm — only testing outputs.
    """

    def _make_student_with_marks(self, scores_per_subject):
        """Helper: create a student with marks and return the StudentProfile."""
        from datetime import date
        from academics.models import (
            AcademicYear, Class, Section, Subject,
            ClassSubject, ExamTerm, StudentMark,
        )
        from students.models import StudentProfile

        yr  = AcademicYear.objects.create(name="T2024", start_date=date(2024,1,1), end_date=date(2024,12,31))
        cls = Class.objects.create(name="TestClass")
        sec = Section.objects.create(class_obj=cls, name="A")
        u   = User.objects.create_user(username="predstu", email="predstu@t.com", password="x", role=User.Role.STUDENT)
        stu = StudentProfile.objects.create(user=u, section=sec, roll_number="001", status="active")

        for subj_name, scores in scores_per_subject.items():
            sub = Subject.objects.create(code=subj_name[:3].upper(), name=subj_name)
            cs  = ClassSubject.objects.create(academic_year=yr, class_obj=cls, subject=sub, full_marks=100, pass_marks=40)
            for i, score in enumerate(scores):
                term = ExamTerm.objects.create(
                    academic_year=yr, name=f"Term{i+1}_{subj_name}",
                    term_type=ExamTerm.TermType.FIRST,
                    start_date=date(2024, i+1, 1),
                    end_date=date(2024, i+1, 28),
                )
                StudentMark.objects.create(
                    student=stu, exam_term=term, class_subject=cs,
                    total_marks=score, percentage=score, grade="A", gpa=3.0,
                )
        return stu

    def test_prediction_never_exceeds_95_for_normal_student(self):
        from analytics.services import predict_future_marks
        stu = self._make_student_with_marks({"English": [60.0, 75.0]})
        preds = predict_future_marks(stu)
        for p in preds:
            self.assertLessEqual(p["predicted_percentage"], 95.0,
                msg=f"Prediction {p['predicted_percentage']} exceeds 95% ceiling")

    def test_prediction_never_negative(self):
        from analytics.services import predict_future_marks
        stu = self._make_student_with_marks({"Social": [80.0, 30.0]})
        preds = predict_future_marks(stu)
        for p in preds:
            self.assertGreaterEqual(p["predicted_percentage"], 0.0)

    def test_single_term_prediction_equals_last_score(self):
        from analytics.services import predict_future_marks
        stu = self._make_student_with_marks({"Math": [72.0]})
        preds = predict_future_marks(stu)
        self.assertEqual(preds[0]["predicted_percentage"], 72.0)
        self.assertEqual(preds[0]["trend"], "stable")

    def test_improving_trend_detected(self):
        from analytics.services import predict_future_marks
        stu = self._make_student_with_marks({"Science": [50.0, 65.0]})
        preds = predict_future_marks(stu)
        self.assertEqual(preds[0]["trend"], "improving")

    def test_declining_trend_detected(self):
        from analytics.services import predict_future_marks
        stu = self._make_student_with_marks({"History": [80.0, 55.0]})
        preds = predict_future_marks(stu)
        self.assertEqual(preds[0]["trend"], "declining")
