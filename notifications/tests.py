from django.test import TestCase

# Create your tests here.
from notifications.models import Subscription
from django.utils import timezone
from datetime import timedelta

today = timezone.now().date()
Subscription.objects.filter(
    is_active=True,
    end_date=today + timedelta(days=5)
)
