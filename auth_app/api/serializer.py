"""Serializers for authentication: registration, login, and password management."""

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

GENERIC_ERROR = "Please check your input and try again."


class RegisterSerializer(serializers.ModelSerializer):
    """Validates and creates a new inactive user account."""

    confirmed_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["email", "password", "confirmed_password"]
        extra_kwargs = {"password": {"write_only": True}}

    def validate_email(self, value: str) -> str:
        """Reject duplicate email addresses with a generic error message."""
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(GENERIC_ERROR)
        return value

    def validate(self, attrs: dict) -> dict:
        """Ensure passwords match and satisfy Django's password validators."""
        if attrs["password"] != attrs["confirmed_password"]:
            raise serializers.ValidationError(
                {"confirmed_password": "Passwords do not match."})
        validate_password(attrs["password"])
        return attrs

    def create(self, validated_data: dict) -> User:
        """Create the user with is_active=False pending email activation."""
        validated_data.pop("confirmed_password")
        return User.objects.create_user(
            username=validated_data["email"],
            email=validated_data["email"],
            password=validated_data["password"],
            is_active=False,
        )


class LoginSerializer(serializers.Serializer):
    """Validates email/password credentials and returns the authenticated user."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs: dict) -> dict:
        """Authenticate user; raise a generic error for any invalid input."""
        user = User.objects.filter(email=attrs["email"]).first()
        if user is None or not user.check_password(attrs["password"]) or not user.is_active:
            raise serializers.ValidationError(GENERIC_ERROR)
        attrs["user"] = user
        return attrs


class PasswordResetSerializer(serializers.Serializer):
    """Validates the email field for the password reset request."""

    email = serializers.EmailField()


class PasswordConfirmSerializer(serializers.Serializer):
    """Validates that both password fields match and meet password policy."""

    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, attrs: dict) -> dict:
        """Ensure both passwords match and pass Django's password validators."""
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."})
        validate_password(attrs["new_password"])
        return attrs
