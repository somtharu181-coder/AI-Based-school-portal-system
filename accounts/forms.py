from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import (
    UserCreationForm,
    UserChangeForm,
)
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

User = get_user_model()



# GLOBAL BOOTSTRAP STYLING MIXIN

class BootstrapFormMixin:
    """
    Enterprise-level reusable Bootstrap form styling.
    """

    def apply_bootstrap_classes(self):

        for field_name, field in self.fields.items():

            css_class = "form-control"

            # Checkbox styling
            if isinstance(field.widget, forms.CheckboxInput):
                css_class = "form-check-input"

            # Select styling
            elif isinstance(field.widget, forms.Select):
                css_class = "form-select"

            existing_class = field.widget.attrs.get("class", "")

            field.widget.attrs["class"] = (
                f"{existing_class} {css_class}"
            ).strip()

            field.widget.attrs.setdefault(
                "placeholder",
                field.label
            )



# LOGIN FORM

class LoginForm(BootstrapFormMixin, forms.Form):
    """
    Enterprise authentication form.
    """

    username = forms.CharField(
        max_length=150,
        label=_("Username"),
        widget=forms.TextInput(
            attrs={
                "autocomplete": "username",
                "autofocus": True,
            }
        )
    )

    password = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "current-password",
            }
        )
    )

    remember_me = forms.BooleanField(
        required=False,
        initial=False
    )

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.apply_bootstrap_classes()



# USER CREATION FORM

class CustomUserCreationForm(
    BootstrapFormMixin,
    UserCreationForm
):
    """
    Enterprise-level user creation form.
    """

    class Meta:

        model = User

        fields = (
            "username",
            "email",
            "phone",
            "role",
            "password1",
            "password2",
        )

        widgets = {

            "username": forms.TextInput(
                attrs={
                    "autocomplete": "username"
                }
            ),

            "email": forms.EmailInput(
                attrs={
                    "autocomplete": "email"
                }
            ),

            "phone": forms.TextInput(
                attrs={
                    "autocomplete": "tel"
                }
            ),
        }

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.apply_bootstrap_classes()

    
    # EMAIL VALIDATION
    
    def clean_email(self):

        email = self.cleaned_data.get("email")

        if not email:
            raise ValidationError(
                _("Email is required.")
            )

        email = email.lower().strip()

        if User.objects.filter(
            email__iexact=email
        ).exists():

            raise ValidationError(
                _("Email already exists.")
            )

        return email

    
    # PHONE VALIDATION
    
    def clean_phone(self):

        phone = self.cleaned_data.get("phone")

        if not phone:
            raise ValidationError(
                _("Phone number is required.")
            )

        phone = phone.strip()

        if User.objects.filter(
            phone=phone
        ).exists():

            raise ValidationError(
                _("Phone already exists.")
            )

        return phone

    
    # USERNAME VALIDATION
    
    def clean_username(self):

        username = self.cleaned_data.get("username")

        if not username:
            raise ValidationError(
                _("Username is required.")
            )

        username = username.strip()

        if User.objects.filter(
            username__iexact=username
        ).exists():

            raise ValidationError(
                _("Username already exists.")
            )

        return username



# USER UPDATE FORM

class CustomUserUpdateForm(
    BootstrapFormMixin,
    UserChangeForm
):
    """
    Enterprise-level user update form.
    """

    password = None

    class Meta:

        model = User

        fields = (
            "username",
            "email",
            "phone",
            "role",
            "is_active",
        )

        widgets = {

            "username": forms.TextInput(),

            "email": forms.EmailInput(),

            "phone": forms.TextInput(),

            "role": forms.Select(),
        }

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.apply_bootstrap_classes()

    
    # EMAIL VALIDATION
    
    def clean_email(self):

        email = self.cleaned_data.get("email")

        if not email:
            raise ValidationError(
                _("Email is required.")
            )

        email = email.lower().strip()

        queryset = User.objects.exclude(
            pk=self.instance.pk
        )

        if queryset.filter(
            email__iexact=email
        ).exists():

            raise ValidationError(
                _("Email already exists.")
            )

        return email

    
    # PHONE VALIDATION
    
    def clean_phone(self):

        phone = self.cleaned_data.get("phone")

        if not phone:
            raise ValidationError(
                _("Phone number is required.")
            )

        phone = phone.strip()

        queryset = User.objects.exclude(
            pk=self.instance.pk
        )

        if queryset.filter(
            phone=phone
        ).exists():

            raise ValidationError(
                _("Phone already exists.")
            )

        return phone

    
    # USERNAME VALIDATION
    
    def clean_username(self):

        username = self.cleaned_data.get("username")

        if not username:
            raise ValidationError(
                _("Username is required.")
            )

        username = username.strip()

        queryset = User.objects.exclude(
            pk=self.instance.pk
        )

        if queryset.filter(
            username__iexact=username
        ).exists():

            raise ValidationError(
                _("Username already exists.")
            )

        return username



# CHANGE CREDENTIALS FORM (self-service for all roles)

class ChangeCredentialsForm(BootstrapFormMixin, forms.Form):
    """
    Allows any logged-in user to change their own username and/or password.
    """

    username = forms.CharField(
        max_length=150,
        label=_("New Username"),
        required=False,
        widget=forms.TextInput(attrs={"autocomplete": "username"}),
    )

    current_password = forms.CharField(
        label=_("Current Password"),
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    new_password = forms.CharField(
        label=_("New Password"),
        required=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text=_("Leave blank to keep your current password."),
    )

    confirm_password = forms.CharField(
        label=_("Confirm New Password"),
        required=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        # Pre-fill current username
        self.fields["username"].initial = user.username
        self.apply_bootstrap_classes()

    def clean_current_password(self):
        password = self.cleaned_data.get("current_password")
        if not self.user.check_password(password):
            raise ValidationError(_("Current password is incorrect."))
        return password

    def clean_username(self):
        username = self.cleaned_data.get("username", "").strip()
        if not username:
            return self.user.username  # keep existing if blank
        if (
            User.objects.exclude(pk=self.user.pk)
            .filter(username__iexact=username)
            .exists()
        ):
            raise ValidationError(_("That username is already taken."))
        return username

    def clean(self):
        cleaned = super().clean()
        new_pw  = cleaned.get("new_password", "")
        confirm = cleaned.get("confirm_password", "")
        if new_pw and new_pw != confirm:
            self.add_error("confirm_password", _("Passwords do not match."))
        return cleaned

    def save(self):
        username = self.cleaned_data.get("username")
        new_pw   = self.cleaned_data.get("new_password")
        if username:
            self.user.username = username
        if new_pw:
            self.user.set_password(new_pw)
        self.user.save()
        return self.user