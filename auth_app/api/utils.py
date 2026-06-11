from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.tokens import PasswordResetTokenGenerator, default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode


class TokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        return (
            str(user.pk) + str(timestamp) + str(user.is_active)
        )


account_activation_token = TokenGenerator()


def get_user_from_uidb64(uidb64):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        return User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return None


def send_activation_email(user, token):
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    activation_link = f"{settings.FRONTEND_URL}/pages/auth/activate.html?uid={uidb64}&token={token}"
    send_mail(
        subject="Activate your Videoflix account",
        message=(
            "Welcome to Videoflix!\n\n"
            "Please click the link below to activate your account:\n"
            f"{activation_link}"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )


def send_password_reset_email(user):
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    reset_link = f"{settings.FRONTEND_URL}/pages/auth/confirm_password.html?uid={uidb64}&token={token}"
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
        fail_silently=False,
    )
