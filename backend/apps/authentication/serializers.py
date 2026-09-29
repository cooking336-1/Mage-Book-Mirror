"""Serializers for authentication endpoints."""

from django.contrib.auth import authenticate
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

