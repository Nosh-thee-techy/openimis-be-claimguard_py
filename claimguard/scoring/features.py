"""
Feature extraction for ClaimGuard ML and rule engines.

Transforms a claim.Claim ORM instance into a flat numeric dict that both
the rule engine and the Isolation Forest model can consume.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

from claim.models import Claim, ClaimItem, ClaimService
from django.db.models import Avg, Count, Sum
from django.utils import timezone


def _days_between(start: Optional[date], end: Optional[date]) -> Optional[int]:
    """Return whole days between two dates, or None when either is missing."""
    if not start or not end:
        return None
    return (end - start).days


def extract_features(claim: Claim) -> Dict[str, Any]:
    """
    Build a feature dictionary from a single claim.

    Features are chosen to support the six fraud patterns defined in the
    hackathon brief. All values are JSON-serialisable primitives.
    """
    items = ClaimItem.objects.filter(claim=claim, validity_to__isnull=True)
    services = ClaimService.objects.filter(claim=claim, validity_to__isnull=True)

    item_count = items.count()
    service_count = services.count()
    claimed_total = float(claim.claimed or 0)

    avg_item_price = float(
        items.aggregate(avg=Avg("price_asked"))["avg"] or 0
    )
    avg_service_price = float(
        services.aggregate(avg=Avg("price_asked"))["avg"] or 0
    )

    submission_lag = _days_between(claim.date_to or claim.date_from, claim.date_claimed)

    # Ghost patient: how many distinct facilities has this insuree claimed from
    # on the same service date?
    same_day_facility_count = 0
    if claim.insuree_id and claim.date_from:
        same_day_facility_count = (
            Claim.objects.filter(
                insuree_id=claim.insuree_id,
                date_from=claim.date_from,
                validity_to__isnull=True,
            )
            .exclude(id=claim.id)
            .values("health_facility_id")
            .distinct()
            .count()
        )

    # Duplicate billing: identical claim codes for same insuree in last 90 days.
    duplicate_count = 0
    if claim.insuree_id:
        duplicate_count = (
            Claim.objects.filter(
                insuree_id=claim.insuree_id,
                code=claim.code,
                validity_to__isnull=True,
            )
            .exclude(id=claim.id)
            .count()
        )

    # Facility spike: claims submitted by this HF in the last 30 days.
    facility_recent_count = 0
    if claim.health_facility_id:
        from datetime import timedelta

        thirty_days_ago = timezone.now().date() - timedelta(days=30)
        facility_recent_count = Claim.objects.filter(
            health_facility_id=claim.health_facility_id,
            date_claimed__gte=thirty_days_ago,
            validity_to__isnull=True,
        ).count()

    return {
        "claimed_total": claimed_total,
        "item_count": item_count,
        "service_count": service_count,
        "total_line_items": item_count + service_count,
        "avg_item_price": avg_item_price,
        "avg_service_price": avg_service_price,
        "submission_lag_days": submission_lag if submission_lag is not None else 0,
        "same_day_other_facilities": same_day_facility_count,
        "duplicate_code_count": duplicate_count,
        "facility_30d_claim_count": facility_recent_count,
        "visit_duration_days": _days_between(claim.date_from, claim.date_to) or 0,
        "insuree_id": claim.insuree_id,
        "health_facility_id": claim.health_facility_id or 0,
    }


def features_to_vector(features: Dict[str, Any]) -> list:
    """
    Convert the feature dict to a fixed-order numeric list for sklearn.

    Order must stay stable between training and inference.
    """
    keys = [
        "claimed_total",
        "item_count",
        "service_count",
        "total_line_items",
        "avg_item_price",
        "avg_service_price",
        "submission_lag_days",
        "same_day_other_facilities",
        "duplicate_code_count",
        "facility_30d_claim_count",
        "visit_duration_days",
    ]
    return [float(features.get(k, 0)) for k in keys]
