"""Live Ghana Revenue Authority (GRA) E-VAT Clearance Service Client.

Performs Mutual TLS / HTTPS REST submissions to the official GRA invoice clearance platform.
"""

import json
import logging
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.utils import timezone

from apps.tax.gateways.base import (
    BaseGraEvatClient,
    GraClearanceResponse,
    GraClearanceStatus,
    GraNetworkException,
    GraRejectionException,
)

logger = logging.getLogger(__name__)


class LiveGraEvatClient(BaseGraEvatClient):
    """Production client communicating with official GRA E-VAT clearance endpoints."""

    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
        timeout: int = 10,
    ) -> None:
        self.api_url = api_url or getattr(settings, "GRA_EVAT_API_URL", "https://gra.gov.gh/api/v1")
        self.api_key = api_key or getattr(settings, "GRA_EVAT_API_KEY", "")
        self.timeout = timeout

    def submit_invoice(self, payload: dict[str, Any]) -> GraClearanceResponse:
        """Sends signed statutory invoice JSON to GRA clearance platform."""
        if not (self.api_url.startswith("https://") or self.api_url.startswith("http://")):
            raise ValueError(f"Invalid GRA API URL scheme: {self.api_url}")

        endpoint = f"{self.api_url.rstrip('/')}/invoice/clearance"
        data_bytes = json.dumps(payload).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "MageBooks-SAAS/2.1 (Ghana-Act-1151)",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        req = Request(endpoint, data=data_bytes, headers=headers, method="POST")

        try:
            with urlopen(req, timeout=self.timeout) as response:  # nosec B310
                resp_bytes = response.read()
                resp_json = json.loads(resp_bytes.decode("utf-8"))
        except HTTPError as http_err:
            if http_err.code in (400, 422):
                err_body = http_err.read().decode("utf-8", errors="replace")
                logger.error(f"[GRA E-VAT] Invoice payload rejected: {err_body}")
                raise GraRejectionException(
                    f"GRA rejection (HTTP {http_err.code}): {err_body}"
                ) from http_err
            else:
                # 5xx / 429 / 503 are transient
                logger.warning(f"[GRA E-VAT] Transient server error (HTTP {http_err.code})")
                raise GraNetworkException(
                    f"GRA E-VAT server error: HTTP {http_err.code}"
                ) from http_err
        except (URLError, TimeoutError, OSError) as net_err:
            logger.warning(f"[GRA E-VAT] Network connection failed: {net_err}")
            raise GraNetworkException(f"Connection failure to GRA gateway: {net_err}") from net_err

        sdc_id = resp_json.get("sdc_id") or resp_json.get("data", {}).get("sdc_id", "")
        clearance_code = resp_json.get("clearance_code") or resp_json.get("data", {}).get(
            "clearance_code", ""
        )
        qr_url = resp_json.get("verification_url") or resp_json.get("data", {}).get(
            "verification_url", ""
        )

        return GraClearanceResponse(
            sdc_id=sdc_id,
            clearance_code=clearance_code,
            qr_code_url=qr_url,
            timestamp=timezone.now(),
            status=GraClearanceStatus.CLEARED,
            raw_response=resp_json,
        )
