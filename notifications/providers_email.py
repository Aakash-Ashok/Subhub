# notifications/providers_email.py
from django.core.mail import EmailMessage
from django.conf import settings
from django.template.loader import render_to_string

def send_email(to_email, subject, template_name=None, context=None, body_text=None, from_email=None):
    """
    Send a single email via the configured Django EMAIL backend.
    Returns {"success": True} or {"success": False, "error": "..."}
    """
    try:
        from_email = from_email or getattr(settings, "DEFAULT_FROM_EMAIL", settings.EMAIL_HOST_USER)
        html_body = None
        plain_body = ''

        if template_name:
            html_body = render_to_string(template_name, context or {})
            plain_body = body_text or ''
        else:
            plain_body = body_text or ''

        msg = EmailMessage(
            subject=subject,
            body=plain_body or html_body or '',
            from_email=from_email,
            to=[to_email],
        )

        if html_body:
            msg.attach_alternative(html_body, "text/html")

        msg.send(fail_silently=False)
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}
