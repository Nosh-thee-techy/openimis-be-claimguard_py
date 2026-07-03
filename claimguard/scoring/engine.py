"""
ClaimGuard scoring orchestrator.

Blends rule-based and ML scores, persists results, publishes FHIR, and
writes the audit log.
"""

from __future__ import annotations

import logging
import json
from typing import Optional

from claim.models import Claim
from django.db import transaction
from django.utils import timezone

from claimguard.models import ClaimFraudScore, FraudAuditLog, tier_for_score
from claimguard.scoring.features import extract_features, features_to_vector
from claimguard.scoring.model import anomaly_score
from claimguard.scoring.rules import evaluate_rules

logger = logging.getLogger(__name__)


def _blend_scores(rule_score: int, ml_score: Optional[int]) -> int:
    """
    Combine rule and ML scores using configured weights.

    When ML is unavailable, rule_score alone drives the final result.
    """
    if ml_score is None:
        return rule_score

    try:
        from claimguard.apps import ClaimGuardConfig

        rw = float(ClaimGuardConfig.rule_weight)
        mw = float(ClaimGuardConfig.ml_weight)
    except Exception:
        rw, mw = 0.6, 0.4

    blended = int(rw * rule_score + mw * ml_score)
    return max(0, min(100, blended))


def _build_decision_reason(triggered_rules: list, final_score: int) -> str:
    """Short summary string for reviewers."""
    if not triggered_rules:
        return f"No fraud indicators detected (score {final_score})."
    labels = [r["label"] for r in triggered_rules[:3]]
    suffix = f" (+{len(triggered_rules) - 3} more)" if len(triggered_rules) > 3 else ""
    return f"Score {final_score}: " + "; ".join(labels) + suffix


def _sync_claim_json_ext(claim: Claim, score_obj: ClaimFraudScore) -> None:
    """Mirror fraud tier/score into claim.json_ext for fe-claim extFields columns."""
    ext = claim.json_ext or {}
    if isinstance(ext, str):
        try:
            ext = json.loads(ext) if ext else {}
        except json.JSONDecodeError:
            ext = {}
    ext["claimguard"] = {
        "risk_score": score_obj.risk_score,
        "risk_tier": score_obj.risk_tier,
        "badge_colour": score_obj.badge_colour,
        "decision_reason": score_obj.decision_reason,
    }
    Claim.objects.filter(pk=claim.pk).update(json_ext=ext)


@transaction.atomic
def score_claim(claim: Claim, is_new: bool = True) -> ClaimFraudScore:
    """
    Score a claim end-to-end and persist the result.

    Called from signals.py on every qualifying claim save.
    """
    features = extract_features(claim)
    vector = features_to_vector(features)

    rule_score, triggered = evaluate_rules(claim, features)
    ml_score, model_version = anomaly_score(vector)
    final_score = _blend_scores(rule_score, ml_score)
    reason = _build_decision_reason(triggered, final_score)

    score_obj, _created = ClaimFraudScore.objects.update_or_create(
        claim=claim,
        defaults={
            "risk_score": final_score,
            "risk_tier": tier_for_score(final_score),
            "ml_score": ml_score,
            "rule_score": rule_score,
            "triggered_rules": triggered,
            "feature_vector": features,
            "decision_reason": reason,
            "model_version": model_version,
            "scored_at": timezone.now(),
            "is_deleted": False,
        },
    )

    FraudAuditLog.objects.create(
        claim=claim,
        fraud_score=score_obj,
        action=FraudAuditLog.Action.SCORED,
        detail={
            "risk_score": final_score,
            "rule_score": rule_score,
            "ml_score": ml_score,
            "triggered_rules": triggered,
            "is_new_claim": is_new,
        },
    )

    _sync_claim_json_ext(claim, score_obj)

    # Publish FHIR ClaimResponse (best-effort — never blocks scoring).
    try:
        from claimguard.fhir.claim_response import publish_claim_response

        fhir_id = publish_claim_response(claim, score_obj)
        if fhir_id:
            score_obj.fhir_claim_response_id = fhir_id
            score_obj.save(update_fields=["fhir_claim_response_id"])
    except Exception:
        logger.exception("FHIR ClaimResponse publish failed for claim %s", claim.id)

    logger.info(
        "ClaimGuard scored claim %s → %s (%s)",
        claim.id,
        final_score,
        score_obj.risk_tier,
    )
    return score_obj
