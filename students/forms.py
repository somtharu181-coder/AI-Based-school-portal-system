from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from .models import StudentProfile,Section

User = get_user_model()



# STUDENT CREATE FORM (PRODUCTION READY)

class StudentProfileForm(forms.ModelForm):

    class Meta:
        model = StudentProfile

        fields = [
            "section",
            "academic_year",
            "name",
            "gender",
            "date_of_birth",
            "religion_type",
            "roll_number",
            "status",
            "temporary_address",   # fixed: was temprory_adress
            "email",
            "guardian_name",
            "guardian_phone",
            "permanent_address",   # fixed: was permanent_adress
            "father_name",
            "mother_name",
            "telephone_number",
        ]
        widgets = {
            "section": forms.Select(attrs={"class": "form-select"}),
            "academic_year": forms.Select(attrs={"class": "form-select"}),

            "name": forms.TextInput(attrs={"class": "form-control"}),

            "gender": forms.Select(attrs={"class": "form-select"}),

            "date_of_birth": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date"
                }
            ),

            "religion_type": forms.Select(attrs={"class": "form-select"}),

            "roll_number": forms.TextInput(
                attrs={"class": "form-control"}
            ),

            "status": forms.Select(attrs={"class": "form-select"}),

            "temporary_address": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 1
                }
            ),
            "permanent_address": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 1
                }
            ),

            "email": forms.EmailInput(
                attrs={"class": "form-control"}
            ),

            "father_name": forms.TextInput(attrs={"class": "form-control"}),
            "mother_name": forms.TextInput(attrs={"class": "form-control"}),

            "guardian_name": forms.TextInput(
                attrs={"class": "form-control"}
            ),

            "guardian_phone": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "telephone_number": forms.TextInput(
                attrs={"class": "form-control"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["section"].queryset = Section.objects.all()

    # filter by class via POST
        if self.data.get("class_id"):
            self.fields["section"].queryset = Section.objects.filter(
            class_obj_id=self.data.get("class_id")
             )
    
    # GLOBAL VALIDATION
    
    def clean(self):
        cleaned_data = super().clean()


        section = cleaned_data.get("section")
        roll_number = cleaned_data.get("roll_number")
        academic_year = cleaned_data.get("academic_year")

        if section and roll_number and academic_year:
            exists = StudentProfile.objects.filter(

                section=section,
                roll_number=roll_number,
                academic_year=academic_year
            )

            if self.instance.pk:
                exists = exists.exclude(pk=self.instance.pk)

            if exists.exists():
                raise ValidationError(
                    "Roll number already exists for this section and academic year."
                )

        return cleaned_data
    


# STUDENT STATUS FORM (ADMIN ONLY)

class StudentStatusForm(forms.ModelForm):

    class Meta:
        model = StudentProfile
        fields = ["status"]

