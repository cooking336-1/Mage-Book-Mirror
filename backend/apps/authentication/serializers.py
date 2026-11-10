"""Serializers for authentication endpoints."""

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers

from apps.authentication.models import CustomUser


class LoginSerializer(serializers.Serializer):
    """Serializer validating email and password credentials."""

    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        required=True,
        write_only=True,
        style={"input_type": "password"},
    )

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        user = authenticate(
            request=self.context.get("request"),
            username=email,
            password=password,
        )

        if not user:
            raise serializers.ValidationError(
                {"detail": "Unable to log in with provided credentials."}
            )

        if not user.is_active:
            raise serializers.ValidationError({"detail": "User account is disabled."})

        attrs["user"] = user
        return attrs


class UserResponseSerializer(serializers.ModelSerializer):
    """Public profile serializer for CustomUser."""

    full_name = serializers.CharField(source="get_full_name", read_only=True)

    class Meta:
        model = CustomUser
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "phone_number",
            "is_active",
            "date_joined",
        )
        read_only_fields = fields


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating mutable profile fields for CustomUser."""

    class Meta:
        model = CustomUser
        fields = ("first_name", "last_name", "phone_number")


class RegisterSerializer(serializers.ModelSerializer):
    """Serializer for registering a new user account."""

    password = serializers.CharField(
        write_only=True,
        required=True,
        min_length=8,
        style={"input_type": "password"},
    )

    def validate_email(self, value: str) -> str:
        """Normalize email address to lowercase and strip whitespace."""
        normalized = value.strip().lower()
        if CustomUser.objects.filter(email__iexact=normalized).exists():
            raise serializers.ValidationError("User with this email already exists.")
        return normalized

    class Meta:
        model = CustomUser
        fields = ("email", "password", "first_name", "last_name", "phone_number")
        extra_kwargs = {
            "first_name": {"required": False, "allow_blank": True},
            "last_name": {"required": False, "allow_blank": True},
            "phone_number": {"required": False, "allow_blank": True},
        }

    def create(self, validated_data):
        return CustomUser.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
            phone_number=validated_data.get("phone_number", ""),
        )


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Validates token, user identification, and password reset constraints."""

    uid = serializers.CharField(required=True)
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        min_length=8,
        style={"input_type": "password"},
    )
    confirm_password = serializers.CharField(
        required=True,
        write_only=True,
        style={"input_type": "password"},
    )

    def validate(self, attrs):
        uid = attrs.get("uid")
        token = attrs.get("token")
        new_password = attrs.get("new_password")
        confirm_password = attrs.get("confirm_password")

        if new_password != confirm_password:
            raise serializers.ValidationError({"confirm_password": ["Passwords do not match."]})

        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user = CustomUser.objects.filter(pk=user_id, is_active=True).first()
        except (TypeError, ValueError, OverflowError):
            user = None

        if not user:
            raise serializers.ValidationError(
                {"token": ["Password reset link is invalid or has expired."]}
            )

        if not default_token_generator.check_token(user, token):
            raise serializers.ValidationError(
                {"token": ["Password reset link is invalid or has expired."]}
            )

        try:
            validate_password(new_password, user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": list(exc.messages)}) from exc

        attrs["user"] = user
        return attrs
