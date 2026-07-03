"""
Rule-based fraud checks for ClaimGuard.

Each rule returns zero or more TriggeredRule records. Rule points are summed
and capped at 100 before blending with the ML anomaly score.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List

from claim.models import Claim


@dataclass
class TriggeredRule:
    """A single fired rule with its contribution to the risk score."""

    code: str
    label: str
    points: int
    detail: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Individual rules — one function per fraud pattern from the hackathon brief
# ---------------------------------------------------------------------------


def _ghost_patients(features: Dict[str, Any]) -> List[TriggeredRule]:
    """Patient claims from multiple facilities on the same day."""
    count = features.get("same_day_other_facilities", 0)
    if count >= 2:
        return [
            TriggeredRule(
                code="GHOST_PATIENT",
                label="Ghost patient — multiple facilities same day",
                points=min(40, 15 * count),
                detail=f"Insuree has claims at {count + 1} facilities on the same date.",
            )
        ]
    return []


def _duplicate_billing(features: Dict[str, Any]) -> List[TriggeredRule]:
    """Same visit billed more than once (duplicate claim code)."""
    count = features.get("duplicate_code_count", 0)
    if count >= 1:
        return [
            TriggeredRule(
                code="DUPLICATE_BILLING",
                label="Duplicate billing",
                points=min(35, 20 + 10 * count),
                detail=f"Found {count} prior claim(s) with identical code.",
            )
        ]
    return []


def _upcoding(features: Dict[str, Any], claim: Claim) -> List[TriggeredRule]:
    """Claimed amount far above typical line-item averages."""
    claimed = features.get("claimed_total", 0)
    avg_price = max(
        features.get("avg_item_price", 0),
        features.get("avg_service_price", 0),
    )
    if claimed > 50000 and avg_price > 0 and claimed > avg_price * 15:
        return [
            TriggeredRule(
                code="UPCODING",
                label="Upcoding — amount far above service average",
                points=30,
                detail=f"Claimed {claimed:.0f} vs avg line price {avg_price:.0f}.",
            )
        ]
    if claimed > 100000:
        return [
            TriggeredRule(
                code="HIGH_VALUE",
                label="Unusually high claim value",
                points=20,
                detail=f"Total claimed amount {claimed:.0f} exceeds threshold.",
            )
        ]
    return []


def _impossible_combos(features: Dict[str, Any]) -> List[TriggeredRule]:
    """Medically implausible service combinations (proxy: too many line items)."""
    lines = features.get("total_line_items", 0)
    if lines >= 20:
        return [
            TriggeredRule(
                code="IMPOSSIBLE_COMBO",
                label="Implausible service combination",
                points=min(25, 5 + lines),
                detail=f"Claim has {lines} line items — unusually high.",
            )
        ]
    return []


def _facility_spike(features: Dict[str, Any]) -> List[TriggeredRule]:
    """Facility suddenly submits far more claims than its recent baseline."""
    count = features.get("facility_30d_claim_count", 0)
    if count >= 50:
        return [
            TriggeredRule(
                code="FACILITY_SPIKE",
                label="Facility claim volume spike",
                points=min(30, count // 5),
                detail=f"Facility submitted {count} claims in the last 30 days.",
            )
        ]
    return []


def _late_submission(features: Dict[str, Any]) -> List[TriggeredRule]:
    """Unusually long gap between service date and claim submission."""
    lag = features.get("submission_lag_days", 0)
    if lag >= 90:
        return [
            TriggeredRule(
                code="LATE_SUBMISSION",
                label="Late claim submission",
                points=min(25, lag // 10),
                detail=f"Submitted {lag} days after service date.",
            )
        ]
    if lag >= 30:
        return [
            TriggeredRule(
                code="LATE_SUBMISSION",
                label="Delayed claim submission",
                points=10,
                detail=f"Submitted {lag} days after service date.",
            )
        ]
    return []


# Ordered registry — evaluated on every claim.
RULE_REGISTRY = [
    _ghost_patients,
    _duplicate_billing,
    _upcoding,
    _impossible_combos,
    _facility_spike,
    _late_submission,
]


def evaluate_rules(claim: Claim, features: Dict[str, Any]) -> tuple[int, List[Dict[str, Any]]]:
    """
    Run all rules and return (rule_score, triggered_rules_as_dicts).

    The rule_score is capped at 100.
    """
    triggered: List[TriggeredRule] = []

    for rule_fn in RULE_REGISTRY:
        # _upcoding needs the claim object; others only need features.
        if rule_fn is _upcoding:
            triggered.extend(_upcoding(features, claim))
        else:
            triggered.extend(rule_fn(features))

    rule_score = min(100, sum(r.points for r in triggered))
    return rule_score, [r.to_dict() for r in triggered]
