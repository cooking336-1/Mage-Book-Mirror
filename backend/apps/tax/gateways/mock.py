"""Deterministic Mock GRA E-VAT Client Adapter (Rules 4 & 5).

Provides offline, reproducible statutory invoice clearance for tests and local development
without requiring external network connectivity to GRA servers.
"""

import uuid
from typing import Any

from django.utils import timezone

from apps.tax.gateways.base import (
    BaseGraEvatClient,
    GraClearanceResponse,
    GraClearanceStatus,
    GraNetworkException,
    GraRejectionException,
)


class MockGraEvatClient(BaseGraEvatClient):
    """Deterministic mock adapter simulating the Ghana Revenue Authority E-VAT endpoint."""

    def __init__(
        self,
        simulate_network_error: bool = False,
        simulate_rejection: bool = False,
        network_failure_countdown: int = 0,
    ) -> None:
        """Initializes mock with failure simulation options.

        Args:
            simulate_network_error: Always raise GraNetworkException.
            simulate_rejection: Always raise GraRejectionException.
            network_failure_countdown: Number of times to raise GraNetworkException before
                succeeding (useful for testing Celery task retries).
        """
        self.simulate_network_error = simulate_network_error
        self.simulate_rejection = simulate_rejection
        self.network_failure_countdown = network_failure_countdown
        self.submitted_payloads: list[dict[str, Any]] = []

    def submit_invoice(self, payload: dict[str, Any]) -> GraClearanceResponse:
        """Simulates statutory validation and returns cryptographic clearance tokens."""
        self.submitted_payloads.append(payload)

        # 1. Simulate Transient Network Failure
        if self.simulate_network_error:
            raise GraNetworkException("Simulated network timeout connecting to GRA E-VAT gateway.")

        if self.network_failure_countdown > 0:
            self.network_failure_countdown -= 1
            msg = (
                f"Simulated transient network timeout "
                f"({self.network_failure_countdown + 1} remaining)."
            )
            raise GraNetworkException(msg)

        # 2. Simulate Rejection by GRA
        if self.simulate_rejection:
            raise GraRejectionException(
                "GRA Statutory Rejection: Seller TIN or buyer tax identification invalid."
            )

        # 3. Defensive Validation
        seller_tin = payload.get("seller_tin")
        if not seller_tin:
            raise GraRejectionException("Missing mandatory 'seller_tin' in clearance payload.")

        invoice_num = payload.get("invoice_number", "UNKNOWN")
        unique_seed = uuid.uuid4().hex[:8].upper()

        sdc_id = f"SDC-GH-2026-{unique_seed}"
        clearance_code = f"GRA-2026-{unique_seed}"
        qr_url = f"https://gra.gov.gh/verify/{clearance_code}"
        now = timezone.now()

        return GraClearanceResponse(
            sdc_id=sdc_id,
            clearance_code=clearance_code,
            qr_code_url=qr_url,
            timestamp=now,
            status=GraClearanceStatus.CLEARED,
            raw_response={
                "status": "SUCCESS",
                "sdc_id": sdc_id,
                "clearance_code": clearance_code,
                "verification_url": qr_url,
                "invoice_number": invoice_num,
                "submitted_at": now.isoformat(),
            },
        )
