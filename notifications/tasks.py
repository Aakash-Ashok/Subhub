from celery import shared_task
from django.core.management import call_command

@shared_task
def send_payment_reminders():
    call_command('send_reminders')

@shared_task
def generate_alerts():
    call_command('generate_alerts')


from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import Subscription, Notification

@shared_task
def check_subscription_notifications():
    today = timezone.now().date()

    # 1️⃣ Notify 5 days before expiry
    five_day_subs = Subscription.objects.filter(
        is_active=True,
        end_date=today + timedelta(days=5)
    )

    for sub in five_day_subs:
        Notification.objects.create(
            title="Your Subscription Ends Soon",
            recipient=sub.customer.email,
            type="Subscription",
            details=f"Hi {sub.customer.username}, your subscription to {sub.plan.name} will expire in 5 days.",
            date_sent=timezone.now()
        )

    # 2️⃣ Notify on expiry day
    expiring_today = Subscription.objects.filter(
        is_active=True,
        end_date=today
    )

    for sub in expiring_today:
        Notification.objects.create(
            title="Your Subscription Has Ended",
            recipient=sub.customer.email,
            type="Subscription",
            details=f"Hi {sub.customer.username}, your subscription to {sub.plan.name} has expired today.",
            date_sent=timezone.now()
        )

        # Optionally auto-deactivate
        sub.subscription_status = "Inactive"
        sub.is_active = False
        sub.save()


# notifications/tasks.py
from celery import shared_task
from django.utils import timezone
from .models import Notification, User
from .providers_email import send_email
from django.db import transaction

@shared_task
def send_email_task(notification_id):
    try:
        notif = Notification.objects.get(pk=notification_id)
    except Notification.DoesNotExist:
        return {"status": "not_found", "id": notification_id}

    subject = notif.title or "Notification from SUBHUB"
    template_name = getattr(notif, 'template', None)  # optional
    context = getattr(notif, 'context', None) or {}
    body_text = notif.details or ''

    # recipient email resolution
    if getattr(notif, 'recipient_user', None):
        recipient_email = notif.recipient_user.email
    else:
        recipient_email = notif.recipient  # assume email

    result = send_email(recipient_email, subject, template_name=template_name, context=context, body_text=body_text)

    notif.attempts = (notif.attempts or 0) + 1
    notif.last_attempt_at = timezone.now()
    if result.get("success"):
        notif.status = "sent"
        notif.sent_at = timezone.now()
        notif.meta = {"sent_via": "email"}
    else:
        notif.status = "failed"
        notif.meta = {"error": result.get("error")}
    notif.save(update_fields=['status','meta','attempts','last_attempt_at','sent_at'])
    return {"id": notification_id, "result": result}

@shared_task
def enqueue_email_broadcast(template_notification_id, batch_size=50, pause_seconds=1.0):
    """
    Create per-user Notification rows for every customer and queue send_email_task.
    """
    try:
        template = Notification.objects.get(pk=template_notification_id)
    except Notification.DoesNotExist:
        return {"status": "template_not_found"}

    customers = User.objects.filter(role='customer').only('id','email','username')
    total = customers.count()
    if total == 0:
        return {"status": "no_customers"}

    i = 0
    for cust in customers.iterator():
        with transaction.atomic():
            per_notif = Notification.objects.create(
                title=template.title,
                type=template.type,
                recipient_user=cust,
                recipient=cust.email,
                details=template.details,
                status='pending',
                date_sent=timezone.now(),
            )
        # schedule send in batches to avoid spikes
        countdown = (i // batch_size) * pause_seconds
        send_email_task.apply_async(args=[per_notif.id], countdown=countdown)
        i += 1

    template.meta = {"broadcast_total": total, "broadcasted_at": timezone.now().isoformat()}
    template.save(update_fields=['meta'])
    return {"status":"enqueued","total":total}






