"""
REST API views for ClaimGuard.

Exposes fraud scores to the React frontend badge and the auditor dashboard.
Mounted at /api/claimguard/ via claimguard.urls.
"""

from claimguard.models import ClaimFraudScore, FraudAuditLog, RiskTier
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


def _serialize_score(score: ClaimFraudScore) -> dict:
    """Serialise a ClaimFraudScore for JSON responses."""
    return {
        "id": str(score.id),
        "claim_id": score.claim_id,
        "risk_score": score.risk_score,
        "risk_tier": score.risk_tier,
        "badge_colour": score.badge_colour,
        "ml_score": score.ml_score,
        "rule_score": score.rule_score,
        "triggered_rules": score.triggered_rules,
        "decision_reason": score.decision_reason,
        "requires_review": score.requires_review,
        "is_overridden": score.is_overridden,
        "override_reason": score.override_reason,
        "fhir_claim_response_id": score.fhir_claim_response_id,
        "model_version": score.model_version,
        "scored_at": score.scored_at.isoformat() if score.scored_at else None,
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def claim_fraud_score(request, claim_id: int):
    """Return the fraud score for a single claim by ClaimID."""
    score = get_object_or_404(ClaimFraudScore, claim_id=claim_id, is_deleted=False)
    return Response(_serialize_score(score))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def fraud_scores_list(request):
    """
    List fraud scores with optional tier filter.

    Query params:
      tier   — green | amber | red
      limit  — max rows (default 50)
    """
    qs = ClaimFraudScore.objects.filter(is_deleted=False).select_related("claim")
    tier = request.query_params.get("tier")
    if tier in RiskTier.values:
        qs = qs.filter(risk_tier=tier)

    limit = min(int(request.query_params.get("limit", 50)), 200)
    scores = qs.order_by("-risk_score", "-scored_at")[:limit]
    return Response([_serialize_score(s) for s in scores])


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def fraud_analytics(request):
    """Summary counts per tier for the administrator dashboard."""
    from django.db.models import Count

    breakdown = (
        ClaimFraudScore.objects.filter(is_deleted=False)
        .values("risk_tier")
        .annotate(count=Count("id"))
        .order_by("risk_tier")
    )
    total = ClaimFraudScore.objects.filter(is_deleted=False).count()
    return Response({"total": total, "by_tier": list(breakdown)})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def override_fraud_score(request, claim_id: int):
    """
    Senior auditor manual override.

    Body: { "risk_score": int, "reason": str }
    """
    score = get_object_or_404(ClaimFraudScore, claim_id=claim_id, is_deleted=False)
    new_score = request.data.get("risk_score")
    reason = request.data.get("reason", "").strip()

    if new_score is None or not reason:
        return Response(
            {"error": "risk_score and reason are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    new_score = max(0, min(100, int(new_score)))
    score.risk_score = new_score
    score.risk_tier = RiskTier.AUTO_APPROVE  # recalculated in save()
    score.is_overridden = True
    score.override_reason = reason
    score.overridden_by = request.user
    from django.utils import timezone

    score.overridden_at = timezone.now()
    score.save()

    FraudAuditLog.objects.create(
        claim_id=claim_id,
        fraud_score=score,
        action=FraudAuditLog.Action.OVERRIDDEN,
        actor=request.user,
        detail={"new_score": new_score, "reason": reason},
    )
    return Response(_serialize_score(score))
