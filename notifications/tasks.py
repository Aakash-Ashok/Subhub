from celery import shared_task
from django.core.management import call_command

@shared_task
def send_payment_reminders():
    call_command('send_reminders')

@shared_task
def generate_alerts():
    call_command('generate_alerts')
