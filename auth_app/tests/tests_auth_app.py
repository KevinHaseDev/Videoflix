"""Tests for the auth app: serializers, utils, views, and authentication."""

from django.contrib.auth.models import User
from django.test import TestCase

from auth_app.api.serializer import (
    LoginSerializer,
    PasswordConfirmSerializer,
    PasswordResetSerializer,
    RegisterSerializer,
)
from auth_app.api.utils import get_user_from_uidb64

VALID_PASSWORD = "Sup3rSecret!2024"


class Uidb64LookupTests(TestCase):
    """Tests for the get_user_from_uidb64 helper."""

    def test_invalid_uidb64_returns_none(self):
        """A malformed uidb64 yields None instead of raising."""
        self.assertIsNone(get_user_from_uidb64("@@@invalid@@@"))


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
