"""Permission classes for authentication endpoints."""
from rest_framework.permissions import AllowAny


class AllowAnyAuth(AllowAny):
    """Allow any access to public auth endpoints (register, login, password reset, activate)."""
