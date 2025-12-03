# app/notifications/forms.py
from django import forms
from django.contrib.auth import get_user_model, authenticate
from .models import Notification, Plan, Subscription , Category , Payment
import re
from django.core.exceptions import ValidationError
from django.contrib.auth.hashers import check_password
from django.utils import timezone
from datetime import timedelta



User = get_user_model()

from django import forms
from .models import User

# notifications/forms.py
class SignUpForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    re_password = forms.CharField(widget=forms.PasswordInput, label="Confirm Password")
    ROLE_CHOICES = (('customer', 'Customer'), ('admin', 'Admin'),)
    role = forms.ChoiceField(choices=ROLE_CHOICES)
    state = forms.CharField(max_length=100, required=False)
    district = forms.CharField(max_length=100, required=False)
    city = forms.CharField(max_length=100, required=False)
    pin_code = forms.CharField(max_length=10, required=False)

    class Meta:
        model = User
        fields = ['username', 'email', 'mobile_number', 'role', 'password', 're_password', 'state', 'district', 'city', 'pin_code']

    def clean_password(self):
        password = self.cleaned_data.get('password')
        pattern = r'^(?=.*[A-Za-z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$'
        if not re.match(pattern, password):
            raise ValidationError("Password must be at least 8 characters and include letters, numbers, and special characters.")
        return password

    def clean(self):
        cleaned_data = super().clean()
        pw = cleaned_data.get('password')
        rp = cleaned_data.get('re_password')
        if pw and rp and pw != rp:
            raise ValidationError("Passwords do not match.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        # Hash password only once here
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user



class LoginForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)

    def clean(self):
        cleaned = super().clean()
        email = cleaned.get('email')
        password = cleaned.get('password')

        if email and password:
            # Use username=email because USERNAME_FIELD='email'
            user = authenticate(username=email, password=password)
            if user is None:
                raise forms.ValidationError("Invalid email or password.")
            cleaned['user'] = user

        return cleaned
    
from django import forms
from django.core.validators import validate_email
from .models import Notification


class NotificationForm(forms.ModelForm):
    class Meta:
        model = Notification
        fields = ['title', 'recipient', 'type', 'details']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Eg: SUBHUB – Payment reminder for your subscription',
            }),
            'recipient': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'customer@example.com',
            }),
            'type': forms.Select(attrs={
                'class': 'form-select',
            }),
            'details': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Write the full message that will be emailed to the user…',
            }),
        }

    def clean_recipient(self):
        email = self.cleaned_data['recipient']

        try:
            validate_email(email)
        except Exception:
            raise forms.ValidationError("Enter a valid email address.")

        return email


from django import forms
from .models import Subscription, Payment


class CustomerSubscriptionForm(forms.ModelForm):
    # ✅ Add payment_method as a standalone field (not linked to Subscription model)
    payment_method = forms.ChoiceField(
        choices=Payment.PAYMENT_METHOD_CHOICES,
        required=True,
        label="Payment Method"
    )

    class Meta:
        model = Subscription
        fields = ['start_date', 'phone_number', 'address']  # payment_method handled separately
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Optional: set default start date to today
        self.fields['start_date'].initial = timezone.now().date()




# -----------------------------
# PLAN FORM
# -----------------------------
class PlanForm(forms.ModelForm):
    class Meta:
        model = Plan
        fields = [
            'name', 'details', 'duration', 'status', 'price',
            'discount_percent', 'discount_activated_date', 
            'discount_deactivated_date','category'
        ]
        widgets = {
            'discount_activated_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'discount_deactivated_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

    def clean_name(self):
        name = self.cleaned_data['name']
        if self.instance.pk:
            if Plan.objects.filter(name=name).exclude(pk=self.instance.pk).exists():
                raise ValidationError("A plan with this name already exists.")
        else:
            if Plan.objects.filter(name=name).exists():
                raise ValidationError("A plan with this name already exists.")
        return name


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name','category', 'description']