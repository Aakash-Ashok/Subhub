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

class SignUpForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    re_password = forms.CharField(widget=forms.PasswordInput, label="Confirm Password")

    ROLE_CHOICES = (
        ('customer', 'Customer'),
        ('admin', 'Admin'),
    )
    role = forms.ChoiceField(choices=ROLE_CHOICES)

    # Customer profile fields (optional for admin)
    state = forms.CharField(max_length=100, required=False)
    district = forms.CharField(max_length=100, required=False)
    city = forms.CharField(max_length=100, required=False)
    pin_code = forms.CharField(max_length=10, required=False)

    class Meta:
        model = User
        fields = ['username', 'email', 'mobile_number', 'role', 'password', 're_password', 'state', 'district', 'city', 'pin_code']

    def clean_password(self):
        password = self.cleaned_data.get('password')
        # Password pattern: at least 8 chars, letters, numbers, special chars
        import re
        pattern = r'^(?=.*[A-Za-z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$'
        if not re.match(pattern, password):
            raise forms.ValidationError(
                "Password must be at least 8 characters and include letters, numbers, and special characters."
            )
        return password

    def clean(self):
        cleaned_data = super().clean()
        pw = cleaned_data.get('password')
        rp = cleaned_data.get('re_password')
        if pw and rp and pw != rp:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
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
    
class NotificationForm(forms.ModelForm):
    class Meta:
        model = Notification
        fields = ['title', 'recipient', 'type', 'details']

    def clean_recipient(self):
        phone = self.cleaned_data['recipient']
        # Regex for Indian phone numbers: 10 digits, optional +91
        pattern = re.compile(r'^(\+91)?[6-9]\d{9}$')
        if not pattern.match(phone):
            raise forms.ValidationError("Enter a valid Indian phone number (10 digits, may include +91).")
        return phone

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