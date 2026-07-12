import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scholaro.settings')
import django
django.setup()

from django.urls import reverse

urls_to_check = [
    # accounts
    ("accounts:login", []),
    ("accounts:dashboard", []),
    ("accounts:staff_dashboard", []),
    ("accounts:student_dashboard", []),
    ("accounts:accountant_dashboard", []),
    ("accounts:user_list", []),
    ("accounts:create_user", []),
    ("accounts:create_student_accounts", []),
    # students
    ("students:student_list", []),
    ("students:create_student", []),
    ("students:my_profile", []),
    ("students:student_detail", [1]),
    # academics
    ("academics:academic_dashboard", []),
    ("academics:create_academic_year", []),
    ("academics:create_subject", []),
    ("academics:assign_subject_to_class", []),
    ("academics:assign_teacher", []),
    ("academics:create_routine", []),
    ("academics:marks_entry_select", []),
    ("academics:marks_entry", []),
    ("academics:student_marks", []),
    # attendance
    ("attendance:mark_student_attendance", []),
    ("attendance:student_attendance_list", []),
    ("attendance:my_attendance", []),
    # analytics
    ("analytics:analytics_dashboard", []),
    ("analytics:student_detail", [1]),
    # reporting
    ("reporting_system:reporting_dashboard", []),
    ("reporting_system:student_results", []),
    ("reporting_system:audit_logs", []),
    # staff
    ("staff:staff_list", []),
    ("staff:staff_create", []),
]

errors = []
for name, args in urls_to_check:
    try:
        url = reverse(name, args=args) if args else reverse(name)
        print(f"  OK  {name:50s} -> {url}")
    except Exception as e:
        errors.append((name, str(e)))
        print(f"  ERR {name:50s} -> {e}")

print()
if errors:
    print(f"=== {len(errors)} URL(s) FAILED ===")
    for n, e in errors:
        print(f"  {n}: {e}")
else:
    print("=== ALL URLs RESOLVED — PROJECT READY ===")
