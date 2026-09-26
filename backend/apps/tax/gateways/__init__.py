"""GRA E-VAT Gateway Adapters and Factory."""

from django.conf import settings

from apps.tax.gateways.base import (
    BaseGraEvatClient,
    GraClearanceResponse,
    GraClearanceStatus,
    GraGatewayException,
    GraNetworkException,
    GraRejectionException,
)
from apps.tax.gateways.live import LiveGraEvatClient
from apps.tax.gateways.mock import MockGraEvatClient


def get_gra_client(force_mock: bool = False) -> BaseGraEvatClient:
    """Factory resolving the active GRA E-VAT clearance client adapter.

    In testing and local dev (or when USE_MOCK_GRA=True), returns MockGraEvatClient.
    In production with live credentials, returns LiveGraEvatClient.
    """
    if force_mock or getattr(settings, "USE_MOCK_GRA", True):
        return MockGraEvatClient()
    return LiveGraEvatClient()


__all__ = [
    "BaseGraEvatClient",
    "GraClearanceResponse",
    "GraClearanceStatus",
    "GraGatewayException",
    "GraNetworkException",
    "GraRejectionException",
    "LiveGraEvatClient",
    "MockGraEvatClient",
    "get_gra_client",
]
