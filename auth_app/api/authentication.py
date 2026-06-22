"""Custom JWT authentication and transparent access-token renewal via cookies."""

from django.conf import settings
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken


class CookieJWTAuthentication(JWTAuthentication):
    """JWT authentication using the HttpOnly 'access_token' cookie."""

    def authenticate(self, request):
        """Authenticate via the access_token cookie, or return None if absent."""
        raw_token = request.COOKIES.get("access_token")
        if raw_token is None:
            return None
        validated_token = self.get_validated_token(raw_token)
        return self.get_user(validated_token), validated_token


class AutoRefreshAccessTokenMiddleware:
    """Renew an expired 'access_token' cookie using a still-valid 'refresh_token'.

    This lets a frontend stay authenticated without implementing token refresh
    itself: when the access token has expired but the refresh token is still
    valid, a fresh access token is issued, injected into the current request so
    CookieJWTAuthentication succeeds, and written back as an HttpOnly cookie on
    the response. If the refresh token is also dead, nothing happens and the
    request falls through to the usual 401, prompting a new login.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        new_access = self._renew_if_needed(request)
        response = self.get_response(request)
        if new_access is not None:
            response.set_cookie("access_token", new_access,
                                **settings.AUTH_COOKIE_SETTINGS)
        return response

    @staticmethod
    def _renew_if_needed(request):
        """Return a new access token string if a renewal happened, else None."""
        refresh = request.COOKIES.get("refresh_token")
        if not refresh:
            return None
        access = request.COOKIES.get("access_token")
        if access:
            try:
                AccessToken(access)
                return None  # still valid, nothing to do
            except TokenError:
                pass  # expired or invalid, try to renew below
        try:
            new_access = str(RefreshToken(refresh).access_token)
        except TokenError:
            return None  # refresh token dead, user must log in again
        # Make the new token visible to CookieJWTAuthentication in this request.
        request.COOKIES["access_token"] = new_access
        return new_access
