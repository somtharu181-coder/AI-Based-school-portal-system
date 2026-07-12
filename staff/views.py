from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_http_methods
from django.core.exceptions import ValidationError

from .forms import StaffCreateForm, StaffUpdateForm
from .models import StaffProfile, Department, Designation
from accounts.models import User
from .services import (
    create_staff_profile,
    update_staff_profile,
    delete_staff_profile,
    get_staff_list,
    get_staff_detail,
)


def is_admin(user):
    return user.is_authenticated and user.role.lower() == "admin"

def is_admin_or_staff_user(user):
    return user.is_authenticated and user.role.lower() in ("admin", "staff")


# STAFF CREATE VIEW

@login_required
@user_passes_test(is_admin)
@require_http_methods(["GET", "POST"])
def staff_create_view(request):

    form = StaffCreateForm(request.POST or None)

    
    # ONLY USERS WITHOUT STAFF PROFILE (FOR DROPDOWN)
    
    available_users = User.objects.filter(role__in=[User.Role.STAFF])

    if request.method == "POST":

        try:
            if form.is_valid():

                data = form.cleaned_data
                user = data.get("user")

                
                # Set role to STAFF but do NOT grant Django admin access
                user.role = User.Role.STAFF
                user.is_staff = False   # Security fix: never grant Django admin via this form
                user.save()

                
                # CREATE STAFF PROFILE (SERVICE LAYER)
                
                staff = create_staff_profile(
                    user_id=user.id,
                    designation=data.get("designation"),
                    department_id=data.get("department").id if data.get("department") else None,
                    phone=data.get("phone"),
                    address=data.get("address"),
                    salary=data.get("salary"),
                )

                messages.success(
                    request,
                    f"Staff created successfully. ID: {staff.staff_id}"
                )

                return redirect("staff:staff_list")

            else:
                messages.error(request, "Invalid form data")

        except ValidationError as e:
            messages.error(request, str(e))

        except Exception as e:
            messages.error(request, f"Error: {str(e)}")

    return render(
        request,
        "staffs/staff_create.html",
        {
            "form": form,
            "available_users": available_users
        }
    )

@login_required
@user_passes_test(is_admin_or_staff_user)
@require_http_methods(["GET"])
def staff_list_view(request):

    staffs = get_staff_list()
    return render(request, "staffs/staff_list.html", {"staffs": staffs})


@login_required
@user_passes_test(is_admin_or_staff_user)
@require_http_methods(["GET"])
def staff_detail_view(request, staff_id):

    staff = get_staff_detail(staff_id)
    return render(request, "staffs/staff_detail.html", {"staff": staff})


@login_required
@user_passes_test(is_admin)
@require_http_methods(["GET", "POST"])
def staff_update_view(request, staff_id):

    # ==========================================
    # GET STAFF OBJECT
    # ==========================================
    staff = get_object_or_404(
        StaffProfile,
        staff_id=staff_id
    )

    # ==========================================
    # USE UPDATE FORM (IMPORTANT CHANGE)
    # ==========================================
    form = StaffUpdateForm(
        request.POST or None,
        instance=staff
    )

    # ==========================================
    # UPDATE PROCESS
    # ==========================================
    if request.method == "POST":

        try:

            if form.is_valid():

                form.save()

                messages.success(
                    request,
                    "Staff updated successfully."
                )

                return redirect("staff:staff_list")

            else:
                messages.error(request, form.errors)

        except Exception as e:
            messages.error(request, str(e))

    # ==========================================
    # RENDER CONTEXT
    # ==========================================
    return render(
        request,
        "staffs/staff_update.html",
        {
            "form": form,
            "staff": staff
        }
    )



# STAFF DELETE VIEW

@login_required
@user_passes_test(is_admin)
@require_http_methods(["POST"])
def staff_delete_view(request, staff_id):

    try:
        delete_staff_profile(staff_id)

        messages.success(
            request,
            "Staff deleted successfully."
        )

    except Exception as e:
        messages.error(request, str(e))

    return redirect("staff:staff_list")