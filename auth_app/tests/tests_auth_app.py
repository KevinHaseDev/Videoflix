"""Tests for the auth app: serializers, utils, views, and authentication."""

from django.test import TestCase

from auth_app.api.utils import get_user_from_uidb64


class Uidb64LookupTests(TestCase):
    """Tests for the get_user_from_uidb64 helper."""

    def test_invalid_uidb64_returns_none(self):
        """A malformed uidb64 yields None instead of raising."""
        self.assertIsNone(get_user_from_uidb64("@@@invalid@@@"))
