import datetime
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.core.management.base import BaseCommand
from notifications.models import Customer, Alert

class Command(BaseCommand):
    help = 'Send payment reminders to customers'

    def handle(self, *args, **kwargs):
        today = timezone.now().date()
        one_week_from_now = today + datetime.timedelta(days=7)

        customers = Customer.objects.all()
        for customer in customers:
            if customer.payment_date == one_week_from_now:
                self.send_email(customer, 'Payment Due in One Week')
                self.create_alert(customer, 'Payment Due in One Week')
            elif customer.payment_date == today:
                self.send_email(customer, 'Payment Due Today')
                self.create_alert(customer, 'Payment Due Today')

    def send_email(self, customer, subject):
        message = f"Dear {customer.name},\n\nYour payment of {customer.amount} is due on {customer.payment_date}."
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [customer.email],
            fail_silently=False,
        )

    def create_alert(self, customer, subject):
        Alert.objects.create(
            category='Subscription',
            subject=subject,
            message=f"Your payment of {customer.amount} is due on {customer.payment_date}.",
            date_sent=timezone.now(),
            read=False,
        )
