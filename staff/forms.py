from django import forms
from .models import StaffProfile, Designation, Department
from accounts.models import User



# STAFF CREATE FORM (PROFESSIONAL)

class StaffCreateForm(forms.ModelForm):

    class Meta:
        model = StaffProfile
        fields = [
            "user",
            "designation",
            "department",
            "phone",
            "address",
            "salary",
        ]

        widgets = {
            "user": forms.Select(attrs={"class": "form-select"}),

            "designation": forms.Select(attrs={"class": "form-select"}),

            "department": forms.Select(attrs={"class": "form-select"}),

            "phone": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Enter phone number"
            }),

            "address": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 2,
                "placeholder": "Enter address"
            }),

            "salary": forms.NumberInput(attrs={
                "class": "form-control",
                "placeholder": "Enter salary"
            }),
        }

    # =================================================
    # PHONE VALIDATION
    # =================================================
    def clean_phone(self):
        phone = self.cleaned_data.get("phone")

        if phone and not phone.isdigit():
            raise forms.ValidationError(
                "Phone number must contain digits only."
            )

        return phone

    # =================================================
    # FILTER USERS BY ROLE (FIXED + SAFE)
    # =================================================
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["user"].queryset = User.objects.filter(
            role__in=[User.Role.STAFF],
            staff_profile__isnull=True
        )


# STAFF UPDATE FORM (PROFESSIONAL)

class StaffUpdateForm(forms.ModelForm):

    class Meta:
        model = StaffProfile

        fields = [
            "designation",
            "department",
            "phone",
            "address",
            "salary"
        ]

        widgets = {
            "designation": forms.Select(attrs={
                "class": "form-select"
            }),

            "department": forms.Select(attrs={
                "class": "form-select"
            }),

            "phone": forms.TextInput(attrs={
                "class": "form-control"
            }),

            "address": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3
            }),

            "salary": forms.NumberInput(attrs={
                "class": "form-control"
            }),
        }

    def clean_phone(self):
        phone = self.cleaned_data.get("phone")

        if phone and not phone.isdigit():
            raise forms.ValidationError(
                "Phone number must contain digits only."
            )

        return phone