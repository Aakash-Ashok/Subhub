# notifications/utils.py
import time
from django.utils import timezone
from django.conf import settings
from .providers_email import send_email
from .models import Notification

def send_and_update_notification(notification: Notification, pause_seconds: float = 0.0):
    """
    Send a Notification synchronously via email and update its DB fields.
    This version is defensive: it only updates fields that actually exist on the model.
    """
    # Resolve recipient email
    if getattr(notification, 'recipient_user', None):
        recipient_email = notification.recipient_user.email
    else:
        recipient_email = notification.recipient

    subject = notification.title or "Notification from SUBHUB"
    template_name = getattr(notification, 'template', None)
    context = getattr(notification, 'context', None) or {}
    body_text = notification.details or ''

    # Send email (synchronously)
    result = send_email(recipient_email, subject,
                        template_name=template_name,
                        context=context,
                        body_text=body_text)

    # Update DB fields defensively
    # increase attempts if exists
    if hasattr(notification, 'attempts'):
        notification.attempts = (notification.attempts or 0) + 1

    # update last_attempt_at if present
    if hasattr(notification, 'last_attempt_at'):
        notification.last_attempt_at = timezone.now()

    if result.get("success"):
        if hasattr(notification, 'status'):
            notification.status = "sent"
        if hasattr(notification, 'sent_at'):
            notification.sent_at = timezone.now()
        # meta: write if field exists (JSONField or TextField)
        if hasattr(notification, 'meta'):
            notification.meta = {"sent_via": "email"}
    else:
        if hasattr(notification, 'status'):
            notification.status = "failed"
        if hasattr(notification, 'meta'):
            notification.meta = {"error": result.get("error")}

    # build update_fields list dynamically
    update_fields = []
    for f in ('status', 'meta', 'attempts', 'last_attempt_at', 'sent_at'):
        if hasattr(notification, f):
            update_fields.append(f)

    if update_fields:
        notification.save(update_fields=update_fields)
    else:
        # fallback if nothing in update_fields (shouldn't happen)
        notification.save()

    # optional pause to avoid hitting SMTP limits
    if pause_seconds and pause_seconds > 0:
        time.sleep(pause_seconds)

    return result





