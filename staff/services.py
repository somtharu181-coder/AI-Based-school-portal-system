import logging
from django.db import transaction
from django.core.exceptions import ValidationError

from .models import StaffProfile, Department, Designation
from accounts.models import User

logger = logging.getLogger(__name__)



# CREATE STAFF PROFILE SERVICE

@transaction.atomic
def create_staff_profile(
    user_id,
    designation,
    department_id=None,
    phone=None,
    address=None,
    salary=None
):

    try:

        # ---------------------------------------------
        # FETCH USER
        # ---------------------------------------------
        user = User.objects.get(id=user_id)

        # ---------------------------------------------
        # VALIDATION: prevent duplicate staff profile
        # ---------------------------------------------
        if StaffProfile.objects.filter(user=user).exists():
            raise ValidationError("Staff profile already exists for this user.")

        # ---------------------------------------------
        # VALIDATION: designation check
        # ---------------------------------------------
        valid_designations = [c[0] for c in Designation.choices]

        if designation not in valid_designations:
            raise ValidationError("Invalid designation.")

        # ---------------------------------------------
        # GET DEPARTMENT (optional)
        # ---------------------------------------------
        department = None
        if department_id:
            department = Department.objects.get(id=department_id)

        # ---------------------------------------------
        # CREATE STAFF PROFILE
        # ---------------------------------------------
        staff = StaffProfile.objects.create(
            user=user,
            designation=designation,
            department=department,
            phone=phone,
            address=address,
            salary=salary,
        )

        logger.info(
            f"[STAFF CREATED SERVICE] ID={staff.staff_id} USER={user.username}"
        )

        return staff

    except Exception as e:
        logger.error(f"[CREATE STAFF ERROR] {str(e)}")
        raise



# UPDATE STAFF PROFILE SERVICE

@transaction.atomic
def update_staff_profile(
    staff_id,
    **kwargs
):

    try:

        staff = StaffProfile.objects.get(staff_id=staff_id)

        # ---------------------------------------------
        # UPDATE FIELDS SAFELY
        # ---------------------------------------------
        for field, value in kwargs.items():

            if hasattr(staff, field):
                setattr(staff, field, value)

        staff.save()

        logger.info(
            f"[STAFF UPDATED SERVICE] ID={staff.staff_id}"
        )

        return staff

    except StaffProfile.DoesNotExist:
        raise ValidationError("Staff not found.")

    except Exception as e:
        logger.error(f"[UPDATE STAFF ERROR] {str(e)}")
        raise



# DELETE STAFF PROFILE SERVICE (SOFT SAFE LOGIC READY)

@transaction.atomic
def delete_staff_profile(staff_id):

    try:

        staff = StaffProfile.objects.get(staff_id=staff_id)

        staff.delete()

        logger.warning(
            f"[STAFF DELETED SERVICE] ID={staff_id}"
        )

        return True

    except StaffProfile.DoesNotExist:
        raise ValidationError("Staff not found.")

    except Exception as e:
        logger.error(f"[DELETE STAFF ERROR] {str(e)}")
        raise



# GET STAFF LIST (FOR API + TEMPLATE + REACT)

def get_staff_list():

    try:

        staff_qs = StaffProfile.objects.select_related(
            "user",
            "department"
        ).all()

        return staff_qs

    except Exception as e:
        logger.error(f"[GET STAFF LIST ERROR] {str(e)}")
        return StaffProfile.objects.none()



# GET SINGLE STAFF DETAIL

def get_staff_detail(staff_id):

    try:

        return StaffProfile.objects.select_related(
            "user",
            "department"
        ).get(staff_id=staff_id)

    except StaffProfile.DoesNotExist:
        raise ValidationError("Staff not found.")