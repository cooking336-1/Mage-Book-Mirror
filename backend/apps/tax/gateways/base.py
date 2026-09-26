"""Base Interfaces and DTOs for Ghana Revenue Authority (GRA) E-VAT Clearance Service."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any


class GraClearanceStatus:
    """Outcome status for statutory clearance submissions."""

    CLEARED = "CLEARED"
    REJECTED = "REJECTED"
    ERROR = "ERROR"


class GraGatewayException(Exception):
    """Base exception for GRA E-VAT clearance transmission failures."""

    pass


class GraNetworkException(GraGatewayException):
    """Exception raised when network connection, timeout, or DNS resolution fails."""

    pass


class GraRejectionException(GraGatewayException):
    """Exception raised when GRA platform rejects invoice payload due to invalid TIN or tax."""

    pass


@dataclass(frozen=True)
class GraClearanceResponse:
    """Cryptographic clearance response from Ghana Revenue Authority E-VAT platform."""

    sdc_id: str
    clearance_code: str
    qr_code_url: str
    timestamp: datetime
    status: str = GraClearanceStatus.CLEARED
    raw_response: dict[str, Any] | None = None
    error_message: str = ""


class BaseGraEvatClient(ABC):
    """Abstract interface for GRA E-VAT clearance service client."""

    @abstractmethod
    def submit_invoice(self, payload: dict[str, Any]) -> GraClearanceResponse:
        """Submits invoice payload to GRA clearance service for cryptographic validation.

        Args:
            payload: Statutory payload with seller TIN, buyer TIN, taxable base, and Act 1151 taxes.

        Returns:
            GraClearanceResponse: SDC ID, clearance code, and verification QR URL.

        Raises:
            GraNetworkException: On connectivity failure (triggers exponential retry).
            GraRejectionException: On statutory validation failure (unretryable).
        """
        pass
