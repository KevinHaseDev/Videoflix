"""Helper functions for token generation, user lookup, and auth emails."""

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.tokens import (
    PasswordResetTokenGenerator,
    default_token_generator,
)
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode


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


def send_activation_email(user: User, token: str) -> None:
    """Send the account activation email with the frontend activation link."""
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    activation_link = (
        f"{settings.FRONTEND_URL}"
        f"/pages/auth/activate.html?uid={uidb64}&token={token}"
    )
    context = {"activation_link": activation_link}
    html_message = render_to_string(
        "auth_app/emails/account_activation.html", context
    )
    send_mail(
        subject="Activate your Videoflix account",
        message=(
            "Welcome to Videoflix!\n\n"
            "Please click the link below to activate your account:\n"
            f"{activation_link}"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=False,
    )


def send_password_reset_email(user: User) -> None:
    """Send the password reset email with the frontend reset link."""
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    reset_link = (
        f"{settings.FRONTEND_URL}"
        f"/pages/auth/confirm_password.html?uid={uidb64}&token={token}"
    )
    context = {"reset_link": reset_link}
    html_message = render_to_string(
        "auth_app/emails/password_reset.html", context
    )
    send_mail(
        subject="Reset your Videoflix password",
        message=(
            "You requested a password reset for your Videoflix account.\n\n"
            "Please click the link below to set a new password:\n"
            f"{reset_link}\n\n"
            "If you did not request this, you can ignore this email."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=False,
    )
