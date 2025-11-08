from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'subhub.settings')

# Create a Celery instance and configure it with the 'subhub' project name.
app = Celery('subhub')

# Load task modules from all registered Django app configs.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Automatically discover tasks from the 'notifications' app.
app.autodiscover_tasks()

# Define a debug task to test Celery setup.
@app.task(bind=True)
def debug_task(self):
    print('Request: {0!r}'.format(self.request))

# Configure Celery Beat schedule.
app.conf.beat_schedule = {
    'send-payment-reminders-daily': {
        'task': 'notifications.tasks.send_payment_reminders',
        'schedule': crontab(hour=0, minute=0),  # Run daily at midnight.
    },
}
