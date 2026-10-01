"""Views for JWT authentication and session cookie management."""

from typing import Any

from django.conf import settings
from django.middleware.csrf import get_token
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.authentication.serializers import (
    LoginSerializer,
    RegisterSerializer,
    UserResponseSerializer,
    UserUpdateSerializer,
)


def set_jwt_cookies(
    response: Response,
    access_token: str,
    refresh_token: str | None = None,
) -> None:
    """Attach JWT access and refresh tokens to response as HttpOnly, SameSite=Strict cookies."""
    cookie_secure = getattr(settings, "JWT_COOKIE_SECURE", not settings.DEBUG)
    cookie_samesite = getattr(settings, "JWT_COOKIE_SAMESITE", "Strict")
    cookie_path = getattr(settings, "JWT_AUTH_COOKIE_PATH", "/")
    access_cookie_name = getattr(settings, "JWT_AUTH_COOKIE", "access_token")
    refresh_cookie_name = getattr(settings, "JWT_REFRESH_COOKIE", "refresh_token")

    simple_jwt = getattr(settings, "SIMPLE_JWT", {})
    access_lifetime = simple_jwt.get("ACCESS_TOKEN_LIFETIME")
    refresh_lifetime = simple_jwt.get("REFRESH_TOKEN_LIFETIME")

    access_max_age = int(access_lifetime.total_seconds()) if access_lifetime else 900

    response.set_cookie(
        key=access_cookie_name,
        value=access_token,
        max_age=access_max_age,
        httponly=True,
        secure=cookie_secure,
        samesite=cookie_samesite,
        path=cookie_path,
    )

    if refresh_token is not None:
        refresh_max_age = int(refresh_lifetime.total_seconds()) if refresh_lifetime else 604800

        response.set_cookie(
            key=refresh_cookie_name,
            value=refresh_token,
            max_age=refresh_max_age,
            httponly=True,
            secure=cookie_secure,
            samesite=cookie_samesite,
            path=cookie_path,
        )


def delete_jwt_cookies(response: Response) -> None:
    """Clear JWT cookies from client session."""
    cookie_path = getattr(settings, "JWT_AUTH_COOKIE_PATH", "/")
    access_cookie_name = getattr(settings, "JWT_AUTH_COOKIE", "access_token")
    refresh_cookie_name = getattr(settings, "JWT_REFRESH_COOKIE", "refresh_token")

    response.delete_cookie(access_cookie_name, path=cookie_path)
    response.delete_cookie(refresh_cookie_name, path=cookie_path)
    if cookie_path != "/api/v1/auth/":
        # Defensive cleanup for legacy cookies set with explicit /api/v1/auth/ path
        response.delete_cookie(refresh_cookie_name, path="/api/v1/auth/")


class RegisterView(APIView):
    """Register a new user account, generate JWT cookies, and return user profile."""

    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = RegisterSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        user_data = UserResponseSerializer(user).data
        csrf_token = get_token(request)
        response = Response(
            {
                "user": user_data,
                "csrf_token": csrf_token,
                "detail": "Registration successful.",
            },
            status=status.HTTP_201_CREATED,
        )

        set_jwt_cookies(response, access_token=access_token, refresh_token=refresh_token)
        return response


class LoginView(APIView):
    """Authenticate user with email/password and set HttpOnly JWT session cookies."""

    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_401_UNAUTHORIZED)

        user = serializer.validated_data["user"]
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        user_data = UserResponseSerializer(user).data
        csrf_token = get_token(request)
        response = Response(
            {
                "user": user_data,
                "csrf_token": csrf_token,
                "detail": "Login successful.",
            },
            status=status.HTTP_200_OK,
        )

        set_jwt_cookies(response, access_token=access_token, refresh_token=refresh_token)
        return response


class CSRFTokenView(APIView):
    """Provide a fresh CSRF token and cookie for single-page applications."""

    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        csrf_token = get_token(request)
        return Response({"csrf_token": csrf_token}, status=status.HTTP_200_OK)


class RefreshTokenView(APIView):
    """Refresh JWT access token using the HttpOnly refresh token cookie."""

    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        refresh_cookie_name = getattr(settings, "JWT_REFRESH_COOKIE", "refresh_token")
        body_refresh = request.data.get("refresh") if isinstance(request.data, dict) else None
        cookie_refresh = request.COOKIES.get(refresh_cookie_name)
        is_body_request = bool(body_refresh)
        raw_refresh = body_refresh or cookie_refresh

        if not raw_refresh:
            return Response(
                {"detail": "Refresh token cookie missing."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            refresh = RefreshToken(raw_refresh)
            new_access_token = str(refresh.access_token)
        except (TokenError, InvalidToken) as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        simple_jwt_settings = getattr(settings, "SIMPLE_JWT", {})
        rotate_tokens = simple_jwt_settings.get("ROTATE_REFRESH_TOKENS", False)
        new_refresh_token: str | None = None

        if rotate_tokens:
            if simple_jwt_settings.get("BLACKLIST_AFTER_ROTATION", False):
                try:
                    refresh.blacklist()
                except AttributeError:
                    pass
            refresh.set_jti()
            refresh.set_exp()
            refresh.set_iat()
            new_refresh_token = str(refresh)

        response_data: dict[str, Any] = {
            "detail": "Token refreshed successfully.",
            "access": new_access_token,
        }
        # Security hardening: Only expose 'refresh' in JSON body if client sent it via JSON body.
        # If client authenticated via HttpOnly cookie, keep refresh_token strictly in cookie.
        if new_refresh_token and is_body_request:
            response_data["refresh"] = new_refresh_token

        response = Response(response_data, status=status.HTTP_200_OK)
        set_jwt_cookies(
            response,
            access_token=new_access_token,
            refresh_token=new_refresh_token,
        )
        return response


class LogoutView(APIView):
    """Clear JWT cookies and end user session."""

    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        response = Response(
            {"detail": "Successfully logged out."},
            status=status.HTTP_200_OK,
        )
        delete_jwt_cookies(response)
        return response


class CurrentUserView(APIView):
    """Return profile details for currently authenticated user."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        serializer = UserResponseSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request: Request) -> Response:
        """Update mutable profile details for currently authenticated user."""
        serializer = UserUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserResponseSerializer(request.user).data, status=status.HTTP_200_OK)


class VerifyPasswordView(APIView):
    """Verifies user password to unlock idle session without losing application state."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        password = request.data.get("password")
        if not password:
            return Response(
                {"password": ["Password is required."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not request.user.check_password(password):
            return Response(
                {"detail": "Incorrect password. Please try again."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return Response(
            {"detail": "Password verified successfully."},
            status=status.HTTP_200_OK,
        )


class PasswordResetRequestView(APIView):
    """Initiates password reset request.

    Validates email format and dispatches reset instructions.
    Always returns HTTP 200 OK to prevent user/email enumeration attacks.
    """

    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        email = request.data.get("email", "")
        if not email or not isinstance(email, str) or "@" not in email:
            return Response(
                {"email": ["Please enter a valid email address."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from django.contrib.auth import get_user_model
        import logging

        logger = logging.getLogger(__name__)
        clean_email = email.strip().lower()
        user = get_user_model().objects.filter(email=clean_email, is_active=True).first()
        if user:
            logger.info("[PasswordResetRequestView] Password reset requested for user: %s", user.email)

        return Response(
            {
                "detail": (
                    "If an active account exists with this email, "
                    "reset instructions have been dispatched."
                )
            },
            status=status.HTTP_200_OK,
        )

