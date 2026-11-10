"""Views for JWT authentication and session cookie management."""

import logging
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.middleware.csrf import get_token
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.authentication.serializers import (
    LoginSerializer,
    PasswordResetConfirmSerializer,
    RegisterSerializer,
    UserResponseSerializer,
    UserUpdateSerializer,
)
from apps.authentication.throttles import (
    PasswordResetEmailThrottle,
    PasswordResetIPThrottle,
)
from apps.core.services.email import send_transactional_email

logger = logging.getLogger(__name__)


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
    authentication_classes = []

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

    Validates email format, generates secure HMAC token, and dispatches reset instructions.
    Always returns HTTP 200 OK to prevent user/email enumeration attacks.
    Protected by dual-tier rate limiting:
    - IP-level: 5 requests per minute.
    - Email-level: 3 requests per 15 minutes (burst) & 5 requests per 24 hours (daily cap).
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PasswordResetIPThrottle, PasswordResetEmailThrottle]

    def post(self, request: Request) -> Response:
        email = request.data.get("email", "")
        if not email or not isinstance(email, str) or "@" not in email:
            return Response(
                {"email": ["Please enter a valid email address."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        clean_email = email.strip().lower()
        user = get_user_model().objects.filter(email=clean_email, is_active=True).first()
        if user:
            logger.info(
                "[PasswordResetRequestView] Password reset requested for user: %s",
                user.email,
            )
            frontend_url = getattr(
                settings, "FRONTEND_URL", "https://magebooks-saas.vercel.app"
            ).rstrip("/")
            token = default_token_generator.make_token(user)
            uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
            reset_url = f"{frontend_url}/reset-password?uid={uidb64}&token={token}"

            display_name = getattr(user, "first_name", "") or user.email
            html_content = (
                "<!DOCTYPE html>"
                "<html><head><meta charset='utf-8'></head>"
                "<body style=\"font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', "
                'Roboto, sans-serif; background-color: #f4f7fe; margin: 0; padding: 32px 16px;">'
                '<div style="max-width: 560px; margin: 0 auto; background-color: #ffffff; '
                'border: 1px solid #c3c6d7; border-radius: 12px; padding: 40px;">'
                '<div style="text-align: center; margin-bottom: 32px;">'
                '<h2 style="color: #2563eb; margin: 0; font-size: 26px; font-weight: 800;">'
                "Mage Books</h2>"
                '<p style="color: #555f6d; font-size: 14px; margin-top: 4px;">'
                "Smart Accounting for African Enterprises</p>"
                "</div>"
                '<h1 style="color: #141b2b; font-size: 20px; font-weight: 700; '
                'margin-bottom: 16px;">'
                "Reset your password</h1>"
                f'<p style="color: #555f6d; font-size: 15px; line-height: 1.6; '
                f'margin-bottom: 24px;">'
                f"Hi {display_name},<br>"
                "We received a request to reset the password for your Mage Books account "
                f"(<strong>{user.email}</strong>). Click the button below to choose a new password:"
                "</p>"
                '<div style="text-align: center; margin: 32px 0;">'
                f'<a href="{reset_url}" style="background-color: #2563eb; color: #ffffff; '
                "text-decoration: none; padding: 14px 32px; border-radius: 8px; font-weight: 600; "
                'font-size: 15px; display: inline-block;">Reset Password</a>'
                "</div>"
                '<p style="color: #64748b; font-size: 13px; line-height: 1.5; '
                'margin-bottom: 24px;">'
                "If the button above does not work, copy and paste this link into your browser:<br>"
                f'<a href="{reset_url}" style="color: #2563eb; word-break: break-all;">'
                f"{reset_url}</a>"
                "</p>"
                '<div style="border-top: 1px solid #e2e8f0; padding-top: 20px; '
                'margin-top: 28px;">'
                '<p style="color: #dc2626; font-size: 13px; font-weight: 600; '
                'margin-bottom: 6px;">'
                "⏱ This link expires in 15 minutes.</p>"
                '<p style="color: #64748b; font-size: 12px; line-height: 1.5; margin: 0;">'
                "If you did not request this password reset, please ignore this email. "
                "Your password will remain unchanged and your account is secure."
                "</p>"
                "</div>"
                "</div></body></html>"
            )

            send_transactional_email(
                to_email=user.email,
                subject="Reset your Mage Books password",
                html_content=html_content,
                to_name=user.get_full_name() or user.email,
            )

        return Response(
            {
                "detail": (
                    "If an active account exists with this email, "
                    "reset instructions have been dispatched."
                )
            },
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmView(APIView):
    """Confirms password reset, updates credentials, and revokes active sessions."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request: Request) -> Response:
        serializer = PasswordResetConfirmSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.validated_data["user"]
        new_password = serializer.validated_data["new_password"]

        user.set_password(new_password)
        user.save()

        # Session Revocation: Invalidate all existing SimpleJWT refresh tokens
        try:
            from rest_framework_simplejwt.token_blacklist.models import (
                BlacklistedToken,
                OutstandingToken,
            )

            for token in OutstandingToken.objects.filter(user=user):
                BlacklistedToken.objects.get_or_create(token=token)
        except Exception as exc:
            logger.warning(
                "[PasswordResetConfirmView] Failed to blacklist tokens for user %s: %s",
                user.id,
                exc,
            )

        # Post-reset confirmation alert email
        security_alert_html = (
            "<!DOCTYPE html>"
            "<html><head><meta charset='utf-8'></head>"
            "<body style=\"font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', "
            'Roboto, sans-serif; background-color: #f4f7fe; padding: 32px 16px;">'
            '<div style="max-width: 560px; margin: 0 auto; background-color: #ffffff; '
            'border: 1px solid #c3c6d7; border-radius: 12px; padding: 40px;">'
            '<h2 style="color: #2563eb; margin: 0 0 16px;">Mage Books Security Alert</h2>'
            f'<p style="color: #141b2b; font-size: 15px; line-height: 1.6;">'
            f"The password for your Mage Books account (<strong>{user.email}</strong>) "
            "was successfully changed."
            "</p>"
            '<p style="color: #64748b; font-size: 13px; line-height: 1.5;">'
            "All previous active sessions have been signed out. "
            "If you made this change, you can safely disregard this email."
            "</p>"
            '<div style="background-color: #fef2f2; border: 1px solid #fecaca; '
            'border-radius: 8px; padding: 12px; margin-top: 20px;">'
            '<p style="color: #dc2626; font-size: 13px; font-weight: 600; margin: 0;">'
            "Did not perform this action? Contact security immediately at support@magebooks.com."
            "</p>"
            "</div></div></body></html>"
        )
        send_transactional_email(
            to_email=user.email,
            subject="Mage Books — Password Successfully Changed",
            html_content=security_alert_html,
            to_name=user.get_full_name() or user.email,
        )

        return Response(
            {
                "detail": (
                    "Password has been reset successfully. "
                    "You may now log in with your new password."
                )
            },
            status=status.HTTP_200_OK,
        )
