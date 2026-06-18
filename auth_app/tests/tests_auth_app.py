"""Tests for the auth app: serializers, utils, views, and authentication."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from auth_app.api.authentication import (
    AutoRefreshAccessTokenMiddleware,
    CookieJWTAuthentication,
)
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
    send_activation_email_task,
    send_password_reset_email,
    send_password_reset_email_task,
)

User = get_user_model()
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
        self.user = User.objects.create_user(username="token@example.com", is_active=False)

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


class AuthEmailTaskTests(TestCase):
    """Tests for the email tasks that run inside the RQ worker."""

    def setUp(self):
        """Create a user and reset the mail outbox."""
        self.user = User.objects.create_user(username="mail@example.com", email="mail@example.com")
        mail.outbox = []

    def test_activation_email_task_sends_mail(self):
        """The activation task sends the email to the user with an HTML alternative."""
        token = account_activation_token.make_token(self.user)
        send_activation_email_task(self.user.pk, token)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["mail@example.com"])
        self.assertIn("Activate", message.subject)
        self.assertTrue(message.alternatives)

    def test_password_reset_email_task_sends_mail(self):
        """The password reset task sends the email to the user with an HTML alternative."""
        send_password_reset_email_task(self.user.pk)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["mail@example.com"])
        self.assertIn("Reset", message.subject)
        self.assertTrue(message.alternatives)


class AuthEmailDispatchTests(TestCase):
    """Tests that the email helpers enqueue their tasks on the high-priority queue."""

    def setUp(self):
        """Create a user to dispatch emails for."""
        self.user = User.objects.create_user(username="mail@example.com", email="mail@example.com")

    @patch("auth_app.api.utils.django_rq.get_queue")
    def test_send_activation_email_enqueues_on_high_queue(self, mock_get_queue):
        """Dispatching the activation email enqueues the task on the high queue."""
        token = account_activation_token.make_token(self.user)
        send_activation_email(self.user, token)
        mock_get_queue.assert_called_once_with("high")
        mock_get_queue.return_value.enqueue.assert_called_once_with(
            send_activation_email_task, self.user.pk, token
        )

    @patch("auth_app.api.utils.django_rq.get_queue")
    def test_send_password_reset_email_enqueues_on_high_queue(self, mock_get_queue):
        """Dispatching the password reset email enqueues the task on the high queue."""
        send_password_reset_email(self.user)
        mock_get_queue.assert_called_once_with("high")
        mock_get_queue.return_value.enqueue.assert_called_once_with(
            send_password_reset_email_task, self.user.pk
        )


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


class RegisterViewTests(APITestCase):
    """Tests for POST /api/register/."""

    def setUp(self):
        """Resolve the register endpoint URL."""
        self.url = reverse("register")

    @patch("auth_app.api.utils.django_rq.get_queue")
    def test_register_creates_user_and_sends_email(self, mock_get_queue):
        """A valid payload returns 201, creates the user, and enqueues an activation email."""
        data = {
            "email": "fresh@example.com",
            "password": VALID_PASSWORD,
            "confirmed_password": VALID_PASSWORD,
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["user"]["email"], "fresh@example.com")
        mock_get_queue.return_value.enqueue.assert_called_once()
        self.assertFalse(User.objects.get(email="fresh@example.com").is_active)

    def test_register_duplicate_email_returns_400(self):
        """Registering an existing email returns 400."""
        User.objects.create_user(username="dup@example.com", email="dup@example.com")
        data = {
            "email": "dup@example.com",
            "password": VALID_PASSWORD,
            "confirmed_password": VALID_PASSWORD,
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ActivateViewTests(APITestCase):
    """Tests for GET /api/activate/<uidb64>/<token>/."""

    def setUp(self):
        """Create an inactive user and encode its uidb64."""
        self.user = User.objects.create_user(
            username="act@example.com", email="act@example.com", is_active=False
        )
        self.uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))

    def _url(self, uidb64, token):
        """Build the activation URL for the given uidb64 and token."""
        return reverse("activate", kwargs={"uidb64": uidb64, "token": token})

    def test_activate_success(self):
        """A valid token activates the user and returns 200."""
        token = account_activation_token.make_token(self.user)
        response = self.client.get(self._url(self.uidb64, token))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_activate_invalid_token_returns_400(self):
        """An invalid token leaves the user inactive and returns 400."""
        response = self.client.get(self._url(self.uidb64, "bad-token"))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_activate_invalid_uid_returns_400(self):
        """An unknown uidb64 returns 400."""
        bad_uid = urlsafe_base64_encode(force_bytes(999999))
        token = account_activation_token.make_token(self.user)
        response = self.client.get(self._url(bad_uid, token))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class LoginViewTests(APITestCase):
    """Tests for POST /api/login/."""

    def setUp(self):
        """Create an active user and resolve the login URL."""
        self.url = reverse("login")
        self.user = User.objects.create_user(
            username="login@example.com",
            email="login@example.com",
            password=VALID_PASSWORD,
            is_active=True,
        )

    def test_login_sets_auth_cookies(self):
        """Valid credentials return 200 and set both auth cookies."""
        data = {"email": "login@example.com", "password": VALID_PASSWORD}
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", response.cookies)
        self.assertIn("refresh_token", response.cookies)

    def test_login_invalid_credentials_returns_400(self):
        """Wrong credentials return 400."""
        data = {"email": "login@example.com", "password": "Wrong!2024"}
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class LogoutViewTests(APITestCase):
    """Tests for POST /api/logout/."""

    def setUp(self):
        """Create an active user and resolve the logout URL."""
        self.url = reverse("logout")
        self.user = User.objects.create_user(username="logout@example.com", is_active=True)

    def test_logout_with_valid_token_returns_200(self):
        """A valid refresh cookie blacklists the token and returns 200."""
        refresh = RefreshToken.for_user(self.user)
        self.client.cookies["refresh_token"] = str(refresh)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_logout_missing_token_returns_400(self):
        """A missing refresh cookie returns 400."""
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_logout_invalid_token_returns_400(self):
        """An invalid refresh cookie returns 400."""
        self.client.cookies["refresh_token"] = "not-a-real-token"
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TokenRefreshViewTests(APITestCase):
    """Tests for POST /api/token/refresh/."""

    def setUp(self):
        """Create an active user and resolve the refresh URL."""
        self.url = reverse("token_refresh")
        self.user = User.objects.create_user(username="refresh@example.com", is_active=True)

    def test_refresh_sets_new_access_cookie(self):
        """A valid refresh cookie returns 200 and sets a new access cookie."""
        refresh = RefreshToken.for_user(self.user)
        self.client.cookies["refresh_token"] = str(refresh)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", response.cookies)

    def test_refresh_missing_token_returns_400(self):
        """A missing refresh cookie returns 400."""
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_refresh_invalid_token_returns_401(self):
        """An invalid refresh cookie returns 401."""
        self.client.cookies["refresh_token"] = "not-a-real-token"
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PasswordResetViewTests(APITestCase):
    """Tests for POST /api/password_reset/."""

    def setUp(self):
        """Resolve the reset URL and clear the mail outbox."""
        self.url = reverse("password_reset")
        mail.outbox = []

    @patch("auth_app.api.utils.django_rq.get_queue")
    def test_reset_sends_email_for_existing_user(self, mock_get_queue):
        """A known email enqueues a reset email and returns 200."""
        User.objects.create_user(username="reset@example.com", email="reset@example.com")
        response = self.client.post(self.url, {"email": "reset@example.com"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_get_queue.return_value.enqueue.assert_called_once()

    @patch("auth_app.api.utils.django_rq.get_queue")
    def test_reset_unknown_email_still_returns_200(self, mock_get_queue):
        """An unknown email returns 200 but enqueues no email."""
        response = self.client.post(self.url, {"email": "ghost@example.com"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_get_queue.return_value.enqueue.assert_not_called()


class PasswordConfirmViewTests(APITestCase):
    """Tests for POST /api/password_confirm/<uidb64>/<token>/."""

    def setUp(self):
        """Create an active user and encode its uidb64."""
        self.user = User.objects.create_user(
            username="confirm@example.com",
            password=VALID_PASSWORD,
            is_active=True,
        )
        self.uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))

    def _url(self, uidb64, token):
        """Build the password confirm URL."""
        return reverse("password_confirm", kwargs={"uidb64": uidb64, "token": token})

    def _payload(self, password="NewPass!2024word"):
        """Return a matching new-password payload."""
        return {"new_password": password, "confirm_password": password}

    def test_confirm_success_changes_password(self):
        """A valid token sets the new password and returns 200."""
        token = default_token_generator.make_token(self.user)
        response = self.client.post(self._url(self.uidb64, token), self._payload())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewPass!2024word"))

    def test_confirm_invalid_token_returns_400(self):
        """An invalid token returns 400."""
        response = self.client.post(self._url(self.uidb64, "bad-token"), self._payload())
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_confirm_invalid_uid_returns_400(self):
        """An unknown uidb64 returns 400."""
        bad_uid = urlsafe_base64_encode(force_bytes(999999))
        token = default_token_generator.make_token(self.user)
        response = self.client.post(self._url(bad_uid, token), self._payload())
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class CookieJWTAuthenticationTests(TestCase):
    """Tests for cookie-based JWT authentication."""

    def setUp(self):
        """Create a user, request factory, and the authenticator."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="jwt@example.com", is_active=True)
        self.auth = CookieJWTAuthentication()

    def test_no_cookie_returns_none(self):
        """Without an access_token cookie, authentication is skipped."""
        request = self.factory.get("/")
        self.assertIsNone(self.auth.authenticate(request))

    def test_valid_cookie_returns_user(self):
        """A valid access_token cookie authenticates the user."""
        request = self.factory.get("/")
        request.COOKIES["access_token"] = str(AccessToken.for_user(self.user))
        user, _validated = self.auth.authenticate(request)
        self.assertEqual(user, self.user)


class AutoRefreshMiddlewareTests(TestCase):
    """Tests for the access-token auto-refresh middleware."""

    def setUp(self):
        """Create a user and a request factory."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="mw@example.com", is_active=True)

    def _run(self, cookies):
        """Run the middleware with the given request cookies."""
        response = HttpResponse()
        middleware = AutoRefreshAccessTokenMiddleware(lambda _req: response)
        request = self.factory.get("/")
        request.COOKIES.update(cookies)
        return middleware(request), request

    def test_no_refresh_cookie_does_nothing(self):
        """Without a refresh cookie, no access token is issued."""
        response, _ = self._run({})
        self.assertNotIn("access_token", response.cookies)

    def test_valid_access_cookie_is_not_renewed(self):
        """A still-valid access token is left untouched."""
        access = str(AccessToken.for_user(self.user))
        refresh = str(RefreshToken.for_user(self.user))
        cookies = {"access_token": access, "refresh_token": refresh}
        response, _ = self._run(cookies)
        self.assertNotIn("access_token", response.cookies)

    def test_invalid_access_with_valid_refresh_is_renewed(self):
        """An invalid access token is renewed from a valid refresh token."""
        refresh = str(RefreshToken.for_user(self.user))
        cookies = {"access_token": "invalid", "refresh_token": refresh}
        response, request = self._run(cookies)
        self.assertIn("access_token", response.cookies)
        self.assertIn("access_token", request.COOKIES)

    def test_missing_access_with_valid_refresh_is_renewed(self):
        """A missing access token is issued from a valid refresh token."""
        refresh = str(RefreshToken.for_user(self.user))
        response, _ = self._run({"refresh_token": refresh})
        self.assertIn("access_token", response.cookies)

    def test_dead_refresh_cookie_does_nothing(self):
        """An invalid refresh token yields no new access token."""
        response, _ = self._run({"refresh_token": "not-a-token"})
        self.assertNotIn("access_token", response.cookies)
