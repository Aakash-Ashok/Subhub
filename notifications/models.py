from django.db import models
from django.utils import timezone
from datetime import timedelta, date
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin

# ----------------------------
# Custom User Manager
# ----------------------------
class UserManager(BaseUserManager):
    def create_user(self, username, email, password=None, role='customer', **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, role=role, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'admin')  # Admin role

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(username, email, password, **extra_fields)

# ----------------------------
# Custom User Model (Merged)
# ----------------------------
class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('customer', 'Customer'),
    )

    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    mobile_number = models.CharField(max_length=15, unique=True, null=True, blank=True)
    state = models.CharField(max_length=100, blank=True)
    district = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    pin_code = models.CharField(max_length=10, blank=True)

    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='customer')

    # Payment / subscription fields from old Customer model
    payment_date = models.DateField(null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    payment_method = models.CharField(
        max_length=50,
        choices=[('UPI','UPI'), ('Netbanking','Netbanking'), ('Pay Later','Pay Later')],
        default='UPI'
    )
    due_date = models.DateField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return f"{self.username} ({self.role})"

    # Payment helper methods from old Customer
    def payment_date_approaching(self):
        if self.payment_date:
            return timezone.now().date() == self.payment_date - timedelta(days=7)
        return False

    def payment_date_today(self):
        if self.payment_date:
            return timezone.now().date() == self.payment_date
        return False

# ----------------------------
# Notification
# ----------------------------
class Notification(models.Model):
    TYPE_CHOICES = [
        ('Payment', 'Payment'),
        ('Subscription', 'Subscription'),
        ('Discount', 'Discount'),
    ]
    title = models.CharField(max_length=255)
    recipient = models.CharField(max_length=20)
    type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    details = models.TextField()
    date_sent = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.title

# ----------------------------
# Alert
# ----------------------------
class Alert(models.Model):
    CATEGORY_CHOICES = [
        ('Subscription', 'Subscription'),
    ]
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    subject = models.CharField(max_length=100)
    message = models.TextField()
    date_sent = models.DateTimeField(default=timezone.now)
    read = models.BooleanField(default=False)
    email = models.EmailField(default='default@example.com')

    def send_email(self):
        from django.core.mail import send_mail
        from django.conf import settings
        send_mail(self.subject, self.message, settings.DEFAULT_FROM_EMAIL, [self.email], fail_silently=False)

    def __str__(self):
        return self.subject

# ----------------------------
# Category
# ----------------------------
class Category(models.Model):
    name = models.CharField(max_length=100)
    category=models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_date = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="categories")
    modified_date = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


# ----------------------------
# Plan (Updated with Category)
# ----------------------------
class Plan(models.Model):
    DURATION_CHOICES = [('monthly', 'Monthly'), ('yearly', 'Yearly')]
    STATUS_CHOICES = [('active', 'Active'), ('expired', 'Expired')]

    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="plans")  # New relation
    name = models.CharField(max_length=255, unique=True)
    details = models.TextField(blank=True)
    duration = models.CharField(max_length=10, choices=DURATION_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    discount_activated_date = models.DateTimeField(null=True, blank=True)
    discount_deactivated_date = models.DateTimeField(null=True, blank=True)
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.category.name})"

    @property
    def final_price(self):
        now = timezone.now()
        if self.discount_activated_date and self.discount_deactivated_date and (
            self.discount_activated_date <= now <= self.discount_deactivated_date
        ):
            return self.price - (self.price * (self.discount_percent or 0) / 100)
        return self.price

    @property
    def discount_status(self):
        now = timezone.now()
        if self.status == 'expired':
            return 'expired'
        if self.discount_activated_date and self.discount_deactivated_date:
            if self.discount_activated_date <= now <= self.discount_deactivated_date:
                return 'active'
            return 'expired'
        return 'NIL'
# ----------------------------
# Subscription
# ----------------------------
class Subscription(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('credit_card', 'Credit Card'),
        ('paypal', 'PayPal'),
        ('bank_transfer', 'Bank Transfer'),
        ('other', 'Other'),
    ]
    customer = models.ForeignKey('User', on_delete=models.CASCADE, related_name='subscriptions')
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField(null=True, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='credit_card')
    address = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    subscription_status = models.CharField(max_length=10, default='Active')

    def __str__(self):
        return f"{self.customer.email} - {self.plan.name}"

    def save(self, *args, **kwargs):
        # ✅ Automatically set end_date if missing
        if not self.end_date:
            if self.plan.duration == 'monthly':
                self.end_date = self.start_date + timedelta(days=30)
            elif self.plan.duration == 'yearly':
                self.end_date = self.start_date + timedelta(days=365)
        super().save(*args, **kwargs)


    def next_due_date(self):
        if self.plan.duration == 'monthly':
            return self.start_date + timedelta(days=30)
        elif self.plan.duration == 'yearly':
            return self.start_date + timedelta(days=365)
        return self.start_date + timedelta(days=30)  # fallback