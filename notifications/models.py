from django.db import models
from django.utils import timezone
from datetime import timedelta, date
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin

class UserManager(BaseUserManager):
    def create_user(self, username, email, password=None, role='customer', **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, role=role, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user


# ----------------------------
# Base User Table
# ----------------------------
class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('customer', 'Customer'),
    )

    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    mobile_number = models.CharField(max_length=15, unique=True, null=True, blank=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='customer')

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # Only relevant for admin role if needed

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return f"{self.username} ({self.role})"


# ----------------------------
# Customer Profile Table
# ----------------------------
class CustomerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='customer_profile')
    state = models.CharField(max_length=100, blank=True)
    district = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    pin_code = models.CharField(max_length=10, blank=True)
    payment_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    payment_method = models.CharField(
        max_length=50,
        choices=[('UPI', 'UPI'), ('Netbanking', 'Netbanking'), ('Pay Later', 'Pay Later')],
        default='UPI'
    )

    def __str__(self):
        return f"CustomerProfile: {self.user.username}"


# ----------------------------
# Admin Profile Table
# ----------------------------
class AdminProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='admin_profile')
    department = models.CharField(max_length=100, blank=True)
    designation = models.CharField(max_length=100, blank=True)
    contact_number = models.CharField(max_length=15, blank=True)

    def __str__(self):
        return f"AdminProfile: {self.user.username}"
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
    recipient = models.EmailField(max_length=254)   # changed to EmailField
    type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    details = models.TextField()
    date_sent = models.DateTimeField(default=timezone.now)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, default='pending')
    provider = models.CharField(max_length=50, blank=True)
    provider_message_id = models.CharField(max_length=255, blank=True, null=True)
    meta = models.JSONField(default=dict, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)   # newly added
    sent_at = models.DateTimeField(null=True, blank=True)
    recipient_user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)



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
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subscriptions')
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)

    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    phone_number = models.CharField(max_length=20, blank=True)
    address = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=False)
    subscription_status = models.CharField(max_length=10, default='Pending')


    def __str__(self):
        return f"{self.customer.email} - {self.plan.name}"

    def save(self, *args, **kwargs):
        # Only auto-set end_date if start_date exists
        if self.start_date and not self.end_date:
            if self.plan.duration == 'monthly':
                self.end_date = self.start_date + timedelta(days=30)
            elif self.plan.duration == 'yearly':
                self.end_date = self.start_date + timedelta(days=365)

        super().save(*args, **kwargs)


    def next_due_date(self):
     """Calculate next renewal date"""
     if not self.start_date:
        return None

     if self.plan and self.plan.duration == 'monthly':
        return self.start_date + timedelta(days=30)
     elif self.plan and self.plan.duration == 'yearly':
        return self.start_date + timedelta(days=365)

     return self.start_date + timedelta(days=30)

    def days_left(self):
        """Return number of days remaining in subscription"""
        if self.end_date:
            delta = (self.end_date - timezone.now().date()).days
            return max(delta, 0)
        return None

    class Meta:
        ordering = ['-start_date']



class Payment(models.Model):

    # ✅ Choices defined INSIDE the class
    PAYMENT_METHOD_CHOICES = [
        ('UPI', 'UPI'),
        ('Netbanking', 'Netbanking'),
        ('Card', 'Card'),
        ('Wallet', 'Wallet'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]

    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name='payments'
    )

    transaction_id = models.CharField(
        max_length=100,
        unique=True
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    payment_date = models.DateTimeField(
        default=timezone.now
    )

    # ✅ NO USER CHOICE — internal field only
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )

    # Razorpay metadata
    razorpay_order_id = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    razorpay_payment_id = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    razorpay_signature = models.CharField(
        max_length=200,
        blank=True,
        null=True
    )

    class Meta:
        ordering = ['-payment_date']

    def __str__(self):
        return f"{self.subscription.customer.email} - ₹{self.amount}"
