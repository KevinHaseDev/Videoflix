"""Authentication views: register, activate, login, logout, token refresh, password reset."""

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from auth_app.api.permissions import AllowAnyAuth
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


class RegisterView(APIView):
    """POST /api/register/ — creates an inactive user and sends an activation email."""

    permission_classes = [AllowAnyAuth]

    def post(self, request: Request) -> Response:
        """Validate input, create the user, and dispatch the activation email."""
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token = account_activation_token.make_token(user)
        send_activation_email(user, token)
        return Response(
            {"user": {"id": user.id, "email": user.email}, "token": token},
            status=status.HTTP_201_CREATED,
        )


class ActivateView(APIView):
    """GET /api/activate/<uidb64>/<token>/ — activates a user account."""

    permission_classes = [AllowAnyAuth]

    def get(self, _request: Request, uidb64: str, token: str) -> Response:
        """Verify the activation token and set the user's is_active flag."""
        user = get_user_from_uidb64(uidb64)
        if user is not None and account_activation_token.check_token(user, token):
            user.is_active = True
            user.save()
            return Response(
                {"message": "Account successfully activated."},
                status=status.HTTP_200_OK,
            )
        return Response(
            {"message": "Account activation failed."},
            status=status.HTTP_400_BAD_REQUEST,
        )


class LoginView(APIView):
    """POST /api/login/ — authenticates a user and sets JWT HttpOnly cookies."""

    permission_classes = [AllowAnyAuth]

    def post(self, request: Request) -> Response:
        """Validate credentials and issue JWT tokens as HttpOnly cookies."""
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        refresh = RefreshToken.for_user(user)
        response = Response(
            {"detail": "Login successful", "user": {"id": user.id, "username": user.username}},
            status=status.HTTP_200_OK,
        )
        response.set_cookie(
            "access_token", str(refresh.access_token), **settings.AUTH_COOKIE_SETTINGS
        )
        response.set_cookie("refresh_token", str(refresh), **settings.AUTH_COOKIE_SETTINGS)
        return response


class LogoutView(APIView):
    """POST /api/logout/ — blacklists the refresh token and clears auth cookies."""

    permission_classes = [AllowAnyAuth]

    def post(self, request: Request) -> Response:
        """Blacklist the refresh token cookie and delete both auth cookies."""
        refresh_token = request.COOKIES.get("refresh_token")
        if refresh_token is None:
            return Response(
                {"detail": "Refresh token is missing."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            RefreshToken(refresh_token).blacklist()
        except TokenError:
            return Response(
                {"detail": "Invalid refresh token."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        response = Response(
            {
                "detail": (
                    "Logout successful! All tokens will be deleted."
                    " Refresh token is now invalid."
                )
            },
            status=status.HTTP_200_OK,
        )
        response.delete_cookie("access_token")
        response.delete_cookie("refresh_token")
        return response


class CookieTokenRefreshView(APIView):
    """POST /api/token/refresh/ — issues a new access token from the refresh cookie."""

    permission_classes = [AllowAnyAuth]

    def post(self, request: Request) -> Response:
        """Read the refresh cookie, validate it, and set a new access_token cookie."""
        refresh_token = request.COOKIES.get("refresh_token")
        if refresh_token is None:
            return Response(
                {"detail": "Refresh token is missing."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = TokenRefreshSerializer(data={"refresh": refresh_token})
        try:
            serializer.is_valid(raise_exception=True)
        except (TokenError, InvalidToken, ValidationError):
            return Response(
                {"detail": "Invalid refresh token."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        access_token = serializer.validated_data["access"]
        response = Response(
            {"detail": "Token refreshed", "access": access_token},
            status=status.HTTP_200_OK,
        )
        response.set_cookie("access_token", access_token, **settings.AUTH_COOKIE_SETTINGS)
        return response


class PasswordResetView(APIView):
    """POST /api/password_reset/ — sends a password reset email if the user exists."""

    permission_classes = [AllowAnyAuth]

    def post(self, request: Request) -> Response:
        """Dispatch a reset email when a matching user exists; always respond 200."""
        serializer = PasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(email=serializer.validated_data["email"]).first()
        if user is not None:
            send_password_reset_email(user)
        return Response(
            {"detail": "An email has been sent to reset your password."},
            status=status.HTTP_200_OK,
        )


class PasswordConfirmView(APIView):
    """POST /api/password_confirm/<uidb64>/<token>/ — saves the new password."""

    permission_classes = [AllowAnyAuth]

    def post(self, request: Request, uidb64: str, token: str) -> Response:
        """Validate the reset token and persist the new password."""
        serializer = PasswordConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = get_user_from_uidb64(uidb64)
        if user is None or not default_token_generator.check_token(user, token):
            return Response(
                {"detail": "Invalid or expired token."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.set_password(serializer.validated_data["new_password"])
        user.save()
        return Response(
            {"detail": "Your Password has been successfully reset."},
            status=status.HTTP_200_OK,
        )
