"""Celery tasks for double-entry ledger rollups and periodic materialized snapshots."""

import datetime
import logging
from typing import Any
from uuid import UUID

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from apps.ledger.models import AccountSnapshot, ChartOfAccounts
from apps.ledger.selectors import get_account_balances
from apps.tenancy.models import Organization

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    retry_backoff=True,
    name="apps.ledger.tasks.rollup_account_snapshots_task",
)
def rollup_account_snapshots_task(
    self: Any,
    organization_id: str | None = None,
    period_end_str: str | None = None,
) -> dict[str, Any]:
    """Computes and materializes monthly AccountSnapshot rollups for tenant accounts.

    Args:
        organization_id: Optional UUID string of a specific organization to rollup.
        period_end_str: Optional ISO date string ('YYYY-MM-DD'). Defaults to last day
                        of the prior completed calendar month.

    Returns:
        dict summary with processed organizations and created/updated snapshots count.
    """
    logger.info(
        "[AccountSnapshot Worker] Starting rollup: org=%s period_end=%s",
        organization_id,
        period_end_str,
    )

    if period_end_str:
        period_end = datetime.date.fromisoformat(period_end_str)
    else:
        # Default: Last calendar day of previous month
        today = timezone.now().date()
        first_of_this_month = today.replace(day=1)
        period_end = first_of_this_month - datetime.timedelta(days=1)

    if organization_id:
        orgs = list(Organization.objects.filter(id=UUID(organization_id), is_active=True))
    else:
        orgs = list(Organization.objects.filter(is_active=True))

    processed_orgs = 0
    total_snapshots = 0

    for org in orgs:
        try:
            with transaction.atomic():
                # Compute account balances as of period_end
                balances = get_account_balances(
                    organization=org,
                    as_of_date=period_end,
                    include_zero_balances=True,
                )

                for _code, snap in balances.items():
                    try:
                        account_obj = ChartOfAccounts.objects.get(
                            id=snap.account_id,
                            organization=org,
                        )
                    except ChartOfAccounts.DoesNotExist:
                        continue

                    AccountSnapshot.objects.update_or_create(
                        organization=org,
                        account=account_obj,
                        period_end=period_end,
                        defaults={
                            "total_debits": snap.total_debits,
                            "total_credits": snap.total_credits,
                            "closing_balance": snap.net_balance,
                        },
                    )
                    total_snapshots += 1

            processed_orgs += 1
            logger.info(
                "[AccountSnapshot Worker] Org '%s' materialized %d snapshots for period %s.",
                org.name,
                len(balances),
                period_end,
            )
        except Exception as exc:
            logger.exception(
                "[AccountSnapshot Worker] Failed rollup for org '%s': %s",
                org.name,
                exc,
            )
            # If a specific org was targeted, allow task retry
            if organization_id:
                raise self.retry(exc=exc) from exc

    return {
        "status": "COMPLETED",
        "processed_organizations": processed_orgs,
        "period_end": str(period_end),
        "total_snapshots_recorded": total_snapshots,
    }
