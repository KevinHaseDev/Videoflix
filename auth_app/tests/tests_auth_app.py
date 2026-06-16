"""Tests for the auth app: serializers, utils, views, and authentication."""

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from auth_app.api.serializer import (
    LoginSerializer,
    PasswordConfirmSerializer,
    PasswordResetSerializer,
    RegisterSerializer,
)
from auth_app.api.utils import (
    account_activation_token,
    get_user_from_uidb64,
    send_activation_email,
    send_password_reset_email,
)

VALID_PASSWORD = "Sup3rSecret!2024"


class Uidb64LookupTests(TestCase):
    """Tests for the get_user_from_uidb64 helper."""

    def test_valid_uidb64_returns_user(self):
        """A valid uidb64 returns the matching user."""
        user = User.objects.create_user(username="u@example.com")
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        self.assertEqual(get_user_from_uidb64(uidb64), user)

    def test_unknown_pk_returns_none(self):
        """A valid uidb64 for a missing user yields None."""
        uidb64 = urlsafe_base64_encode(force_bytes(999999))
        self.assertIsNone(get_user_from_uidb64(uidb64))

    def test_invalid_uidb64_returns_none(self):
        """A malformed uidb64 yields None instead of raising."""
        self.assertIsNone(get_user_from_uidb64("@@@invalid@@@"))


class AccountActivationTokenTests(TestCase):
    """Tests for the activation token generator."""

    def setUp(self):
        """Create an inactive user to issue tokens for."""
        self.user = User.objects.create_user(
            username="token@example.com", is_active=False
        )

    def test_token_is_valid_for_unchanged_user(self):
        """A freshly issued token validates for the same user."""
        token = account_activation_token.make_token(self.user)
        self.assertTrue(account_activation_token.check_token(self.user, token))

    def test_token_invalid_after_activation(self):
        """Activating the user invalidates a previously issued token."""
        token = account_activation_token.make_token(self.user)
        self.user.is_active = True
        self.user.save()
        self.assertFalse(account_activation_token.check_token(self.user, token))


class AuthEmailTests(TestCase):
    """Tests for the activation and password reset email helpers."""

    def setUp(self):
        """Create a user and reset the mail outbox."""
        self.user = User.objects.create_user(
            username="mail@example.com", email="mail@example.com"
        )
        mail.outbox = []

    def test_send_activation_email(self):
        """The activation email is sent to the user with an HTML alternative."""
        token = account_activation_token.make_token(self.user)
        send_activation_email(self.user, token)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["mail@example.com"])
        self.assertIn("Activate", message.subject)
        self.assertTrue(message.alternatives)

    def test_send_password_reset_email(self):
        """The password reset email is sent to the user with an HTML alternative."""
        send_password_reset_email(self.user)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["mail@example.com"])
        self.assertIn("Reset", message.subject)
        self.assertTrue(message.alternatives)


class RegisterSerializerTests(TestCase):
    """Tests for RegisterSerializer validation and user creation."""

    def _data(self, **overrides):
        """Return a valid registration payload with optional overrides."""
        data = {
            "email": "new@example.com",
            "password": VALID_PASSWORD,
            "confirmed_password": VALID_PASSWORD,
        }
        data.update(overrides)
        return data

    def test_valid_data_creates_inactive_user(self):
        """A valid payload creates a user with is_active=False."""
        serializer = RegisterSerializer(data=self._data())
        self.assertTrue(serializer.is_valid(), serializer.errors)
        user = serializer.save()
        self.assertFalse(user.is_active)
        self.assertEqual(user.username, "new@example.com")
        self.assertEqual(user.email, "new@example.com")

    def test_duplicate_email_is_rejected(self):
        """An already registered email fails on the email field."""
        User.objects.create_user(
            username="new@example.com",
            email="new@example.com",
            password=VALID_PASSWORD,
        )
        serializer = RegisterSerializer(data=self._data())
        self.assertFalse(serializer.is_valid())
        self.assertIn("email", serializer.errors)

    def test_password_mismatch_is_rejected(self):
        """Mismatched passwords fail on the confirmed_password field."""
        data = self._data(confirmed_password="Different!2024")
        serializer = RegisterSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("confirmed_password", serializer.errors)

    def test_weak_password_is_rejected(self):
        """A password failing Django's validators is rejected."""
        data = self._data(password="12345", confirmed_password="12345")
        serializer = RegisterSerializer(data=data)
        self.assertFalse(serializer.is_valid())


class LoginSerializerTests(TestCase):
    """Tests for LoginSerializer authentication logic."""

    def setUp(self):
        """Create an active user to authenticate against."""
        self.user = User.objects.create_user(
            username="user@example.com",
            email="user@example.com",
            password=VALID_PASSWORD,
            is_active=True,
        )

    def test_valid_credentials_return_user(self):
        """Correct credentials expose the user in validated_data."""
        data = {"email": "user@example.com", "password": VALID_PASSWORD}
        serializer = LoginSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["user"], self.user)

    def test_wrong_password_is_rejected(self):
        """An incorrect password fails validation."""
        data = {"email": "user@example.com", "password": "Wrong!2024"}
        serializer = LoginSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_inactive_user_is_rejected(self):
        """An inactive account cannot log in."""
        self.user.is_active = False
        self.user.save()
        data = {"email": "user@example.com", "password": VALID_PASSWORD}
        serializer = LoginSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_unknown_email_is_rejected(self):
        """An unregistered email fails validation."""
        data = {"email": "ghost@example.com", "password": VALID_PASSWORD}
        serializer = LoginSerializer(data=data)
        self.assertFalse(serializer.is_valid())


class PasswordResetSerializerTests(TestCase):
    """Tests for PasswordResetSerializer email validation."""

    def test_valid_email_passes(self):
        """A well-formed email address validates."""
        serializer = PasswordResetSerializer(data={"email": "user@example.com"})
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_invalid_email_is_rejected(self):
        """A malformed email address fails validation."""
        serializer = PasswordResetSerializer(data={"email": "not-an-email"})
        self.assertFalse(serializer.is_valid())


class PasswordConfirmSerializerTests(TestCase):
    """Tests for PasswordConfirmSerializer password validation."""

    def test_matching_strong_passwords_pass(self):
        """Matching, policy-compliant passwords validate."""
        data = {
            "new_password": VALID_PASSWORD,
            "confirm_password": VALID_PASSWORD,
        }
        serializer = PasswordConfirmSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_password_mismatch_is_rejected(self):
        """Mismatched passwords fail on the confirm_password field."""
        data = {
            "new_password": VALID_PASSWORD,
            "confirm_password": "Other!2024",
        }
        serializer = PasswordConfirmSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("confirm_password", serializer.errors)

    def test_weak_password_is_rejected(self):
        """A password failing Django's validators is rejected."""
        data = {"new_password": "12345", "confirm_password": "12345"}
        serializer = PasswordConfirmSerializer(data=data)
        self.assertFalse(serializer.is_valid())
