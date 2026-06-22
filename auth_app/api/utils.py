"""Helper functions for token generation, user lookup, and auth emails."""

from email.message import MIMEPart
from pathlib import Path

import django_rq
from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.tokens import (
    PasswordResetTokenGenerator,
    default_token_generator,
)
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

# The logo is embedded as an inline image attachment instead of an external URL
# or inline SVG, because mail clients (Gmail, Outlook, Apple Mail) strip inline
# SVG and block remote images by default. The templates reference it as
# ``cid:logo``; the file lives next to the email templates.
EMAIL_LOGO_PATH = ("templates", "static", "logo.png")
EMAIL_LOGO_CID = "logo"


def _send_html_email(
    subject: str, text_body: str, template_name: str, context: dict, recipient: str
) -> None:
    """Render an HTML email with a plain-text fallback and the inline logo, then send.

    The logo PNG is attached inline with the ``cid:logo`` Content-ID referenced
    by the templates.
    """
    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient],
    )
    message.attach_alternative(render_to_string(template_name, context), "text/html")

    logo_path = Path(apps.get_app_config("auth_app").path).joinpath(*EMAIL_LOGO_PATH)
    logo = MIMEPart()
    logo.set_content(
        logo_path.read_bytes(),
        maintype="image",
        subtype="png",
        disposition="inline",
        cid=f"<{EMAIL_LOGO_CID}>",
    )
    message.attach(logo)
    message.send(fail_silently=False)


class TokenGenerator(PasswordResetTokenGenerator):
    """Generates activation tokens tied to the user's pk, timestamp, and active state."""

    def _make_hash_value(self, user: User, timestamp: int) -> str:
        """Return a hash value unique to this user's activation state."""
        return str(user.pk) + str(timestamp) + str(user.is_active)


account_activation_token = TokenGenerator()


def get_user_from_uidb64(uidb64: str) -> User | None:
    """Decode a base64 user ID and return the matching User, or None on failure."""
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        return User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, ObjectDoesNotExist):
        return None


def send_activation_email_task(user_pk: int, token: str) -> None:
    """Render and send the account activation email. Runs in the RQ worker."""
    user = User.objects.get(pk=user_pk)
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    activation_link = (
        f"{settings.FRONTEND_URL}" f"/pages/auth/activate.html?uid={uidb64}&token={token}"
    )
    context = {
        "activation_link": activation_link,
        "user_name": user.get_full_name() or user.username,
    }
    _send_html_email(
        subject="Activate your Videoflix account",
        text_body=(
            "Welcome to Videoflix!\n\n"
            "Please click the link below to activate your account:\n"
            f"{activation_link}"
        ),
        template_name="email/account_activation.html",
        context=context,
        recipient=user.email,
    )


def send_activation_email(user: User, token: str) -> None:
    """Enqueue the activation email on the high-priority queue."""
    queue = django_rq.get_queue("high")
    queue.enqueue(send_activation_email_task, user.pk, token)


def send_password_reset_email_task(user_pk: int) -> None:
    """Render and send the password reset email. Runs in the RQ worker."""
    user = User.objects.get(pk=user_pk)
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    reset_link = (
        f"{settings.FRONTEND_URL}" f"/pages/auth/confirm_password.html?uid={uidb64}&token={token}"
    )
    context = {"reset_link": reset_link}
    _send_html_email(
        subject="Reset your Videoflix password",
        text_body=(
            "You requested a password reset for your Videoflix account.\n\n"
            "Please click the link below to set a new password:\n"
            f"{reset_link}\n\n"
            "If you did not request this, you can ignore this email."
        ),
        template_name="email/password_reset.html",
        context=context,
        recipient=user.email,
    )


def send_password_reset_email(user: User) -> None:
    """Enqueue the password reset email on the high-priority queue."""
    queue = django_rq.get_queue("high")
    queue.enqueue(send_password_reset_email_task, user.pk)
