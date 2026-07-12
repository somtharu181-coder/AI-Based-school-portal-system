import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scholaro.settings')
import django
django.setup()

import inspect
from students import views as sv
from academics import views as av
from attendance import views as attv
from analytics import views as anv
from reporting_system import views as rv

checks = [
    ("students.my_profile",          sv.my_profile),
    ("academics.student_marks_view", av.student_marks_view),
    ("attendance.my_attendance_view",attv.my_attendance_view),
    ("analytics.my_ai_report",       anv.my_ai_report),
    ("reporting_system.my_results",  rv.my_results),
]

for name, fn in checks:
    # unwrap decorators to see the real function
    src = inspect.getsource(fn)
    has_login_required   = "@login_required" in src or "login_required" in src
    has_user_passes_test = "user_passes_test" in src
    has_is_admin         = "is_admin" in src
    has_is_student       = "is_student" in src
    print(f"\n--- {name} ---")
    print(f"  login_required   : {has_login_required}")
    print(f"  user_passes_test : {has_user_passes_test}")
    print(f"  is_admin check   : {has_is_admin}")
    print(f"  is_student check : {has_is_student}")
    # show first 8 lines
    lines = src.split('\n')[:8]
    for l in lines:
        print(f"  {l}")
