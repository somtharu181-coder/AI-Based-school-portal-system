from django.urls import path
from . import views

# App namespace (important for production projects)
app_name = "accounts"

urlpatterns = [
    
    path("login/", views.login_view, name="login"),
    path("captcha/", views.captcha_image, name="captcha_image"),

    path("logout/", views.logout_view, name="logout"),

    path("dashboard/", views.admin_dashboard, name="dashboard"),
    path("student_dashboard/", views.student_dashboard, name="student_dashboard"),
    path("staff_dashboard/", views.staff_dashboard, name="staff_dashboard"),
    path("principal_dashboard/", views.principal_dashboard, name="principal_dashboard"),
    path("accountant_dashboard/", views.accountant_dashboard, name="accountant_dashboard"),

    path("users/", views.user_list, name="user_list"),


    path("users/create/", views.create_user, name="create_user"),

    path("users/<int:pk>/update/", views.update_user, name="update_user"),

    path("users/<int:pk>/delete/", views.delete_user, name="delete_user"),

    # Student account creation from existing profiles
    path("students/create-accounts/", views.create_student_accounts, name="create_student_accounts"),

    # Self-service credentials change (all roles)
    path("change-credentials/", views.change_credentials, name="change_credentials"),

    # Admin resets password for any user
    path("users/<int:pk>/reset-password/", views.reset_user_password, name="reset_user_password"),

    # Parent account management
    path("parents/create/",              views.create_parent_account,   name="create_parent_account"),
    path("parents/<int:pk>/children/",   views.manage_parent_children,  name="manage_parent_children"),
]