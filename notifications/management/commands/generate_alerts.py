from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from notifications.models import Customer, Alert
from celery import shared_task


@shared_task
def generate_alerts():
    now = timezone.now()
    one_week_from_now = now + timedelta(weeks=1)

    # Generate alerts for due dates today and one week from now
    customers = Customer.objects.filter(due_date__in=[now.date(), one_week_from_now.date()])

    for customer in customers:
        Alert.objects.create(
            category='Subscription',
            subject='Payment Due Alert',
            message=f'Dear {customer.name}, your payment of {customer.amount} is due on {customer.due_date}.',
            date_sent=now,
            email=customer.email
        )


class Command(BaseCommand):
    help = 'Generate alerts for upcoming payment due dates'

    def handle(self, *args, **kwargs):
        now = timezone.now().date()
        upcoming_due_date = now + timedelta(days=7)

        # Check for payments due today
        customers_due_today = Customer.objects.filter(payment_date=now)
        for customer in customers_due_today:
            Alert.objects.create(
                category='Subscription',
                subject='Payment Due Today',
                message=f'Your payment is due today: {customer.amount}.',
                date_sent=now,
                email=customer.email
            )

        # Check for payments due in a week
        customers_due_soon = Customer.objects.filter(payment_date=upcoming_due_date)
        for customer in customers_due_soon:
            Alert.objects.create(
                category='Subscription',
                subject='Payment Due Soon',
                message=f'Your payment is due in a week: {customer.amount}.',
                date_sent=now,
                email=customer.email
            )

        self.stdout.write(self.style.SUCCESS('Successfully generated alerts'))
