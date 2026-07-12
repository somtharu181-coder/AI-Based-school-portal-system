from django.db import models
from django.utils.crypto import get_random_string
from accounts.models import User



# DEPARTMENT MODEL

class Department(models.Model):
    """
    School departments (Science, Math, Administration, etc.)
    """
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Departments"



# DESIGNATION (ROLE INSIDE SCHOOL - NOT LOGIN ROLE)

class Designation(models.TextChoices):
    TEACHER = "teacher", "Teacher"
    VICE_PRINCIPAL= "vice_principal","Vice Principal"
    PRINCIPAL = "principal", "Principal"
    ACCOUNTANT = "accountant", "Accountant"
    LAB_ASSISTANT = "lab_assistant", "Lab Assistant"
    ADMIN_STAFF = "admin_staff", "Admin Staff"



# STAFF PROFILE (CORE ERP ENTITY)

class StaffProfile(models.Model):

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="staff_profile"
    )

    staff_id = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        editable=False
    )

    designation = models.CharField(
        max_length=30,
        choices=Designation.choices
    )

    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_members"
    )

    phone = models.CharField(max_length=15, null=True, blank=True)
    address = models.TextField(null=True, blank=True)

    joining_date = models.DateField(auto_now_add=True)

    is_active = models.BooleanField(default=True)

    salary = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # =================================================
    # AUTO STAFF ID GENERATION (PRODUCTION SAFE)
    # =================================================
    def save(self, *args, **kwargs):
        if not self.staff_id:
            self.staff_id = f"STF-{get_random_string(8).upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.staff_id} | {self.user.username} | {self.designation}"

    class Meta:
        ordering = ["designation", "staff_id"]

        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                name="unique_staff_user"
            )
        ]