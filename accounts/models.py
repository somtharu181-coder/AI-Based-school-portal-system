from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):

    class Role(models.TextChoices):
        ADMIN       = "admin",       "Admin"
        STAFF       = "staff",       "Staff"
        ACCOUNTANT  = "accountant",  "Accountant"
        STUDENT     = "student",     "Student"
        PARENT      = "parent",      "Parent"

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.STUDENT,
        db_index=True
    )

    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15, unique=True, null=True, blank=True)

    is_verified = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email"]

    def __str__(self):
        return f"{self.username} - {self.role}"

    class Meta:
        ordering = ["-created_at"]
        