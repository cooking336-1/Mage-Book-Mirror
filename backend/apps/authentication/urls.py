"""URL patterns for authentication endpoints."""

from django.urls import path

from apps.authentication.views import (
    CSRFTokenView,
    CurrentUserView,
    LoginView,
    LogoutView,
    PasswordResetRequestView,
    RefreshTokenView,
    RegisterView,
    VerifyPasswordView,
)

app_name = "authentication"

urlpatterns = [
    path("csrf/", CSRFTokenView.as_view(), name="csrf"),
    path("register/", RegisterView.as_view(), name="register"),
    path("signup/", RegisterView.as_view(), name="signup"),
    path("login/", LoginView.as_view(), name="login"),
    path("refresh/", RefreshTokenView.as_view(), name="refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", CurrentUserView.as_view(), name="me"),
    path("verify-password/", VerifyPasswordView.as_view(), name="verify-password"),
    path("password-reset/", PasswordResetRequestView.as_view(), name="password-reset"),
]
