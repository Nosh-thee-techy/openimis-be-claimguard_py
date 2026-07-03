"""GraphQL schema for ClaimGuard — exposes fraud scores to the openIMIS frontend."""

import graphene
from claimguard.models import ClaimFraudScore, FraudAuditLog
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from graphene_django import DjangoObjectType


class ClaimFraudScoreGQLType(DjangoObjectType):
    """GraphQL type mirroring ClaimFraudScore for the React claims list badge."""

    badge_colour = graphene.String()
    requires_review = graphene.Boolean()

    class Meta:
        model = ClaimFraudScore
        fields = (
            "id",
            "claim",
            "risk_score",
            "risk_tier",
            "ml_score",
            "rule_score",
            "triggered_rules",
            "decision_reason",
            "is_overridden",
            "override_reason",
            "fhir_claim_response_id",
            "model_version",
            "scored_at",
        )

    def resolve_badge_colour(self, info):
        return self.badge_colour

    def resolve_requires_review(self, info):
        return self.requires_review


def _ensure_authenticated(info):
    user = info.context.user
    if not user or not getattr(user, "is_authenticated", False):
        raise PermissionDenied("Authentication required")


class Query(graphene.ObjectType):
    """ClaimGuard GraphQL queries."""

    claim_fraud_score = graphene.Field(
        ClaimFraudScoreGQLType,
        claim_id=graphene.Int(required=True),
    )
    claim_fraud_scores = graphene.List(
        ClaimFraudScoreGQLType,
        tier=graphene.String(),
        limit=graphene.Int(default_value=50),
    )

    def resolve_claim_fraud_score(self, info, claim_id):
        _ensure_authenticated(info)
        return ClaimFraudScore.objects.filter(
            claim_id=claim_id, is_deleted=False
        ).first()

    def resolve_claim_fraud_scores(self, info, tier=None, limit=50):
        _ensure_authenticated(info)
        qs = ClaimFraudScore.objects.filter(is_deleted=False)
        if tier:
            qs = qs.filter(risk_tier=tier)
        return qs.order_by("-risk_score")[:limit]


class OverrideClaimFraudScoreMutation(graphene.Mutation):
    """Human-in-the-loop override — logs justification for ML retraining pipeline."""

    class Arguments:
        claim_id = graphene.Int(required=True)
        risk_score = graphene.Int(required=True)
        reason = graphene.String(required=True)

    fraud_score = graphene.Field(ClaimFraudScoreGQLType)

    @classmethod
    def mutate(cls, root, info, claim_id, risk_score, reason):
        _ensure_authenticated(info)
        reason = (reason or "").strip()
        if not reason:
            raise PermissionDenied("Override reason is required.")

        score = ClaimFraudScore.objects.filter(
            claim_id=claim_id, is_deleted=False
        ).first()
        if not score:
            raise PermissionDenied("Fraud score not found for this claim.")

        new_score = max(0, min(100, int(risk_score)))
        score.risk_score = new_score
        score.is_overridden = True
        score.override_reason = reason
        score.overridden_by = info.context.user
        score.overridden_at = timezone.now()
        score.save()

        FraudAuditLog.objects.create(
            claim_id=claim_id,
            fraud_score=score,
            action=FraudAuditLog.Action.OVERRIDDEN,
            actor=info.context.user,
            detail={"new_score": new_score, "reason": reason},
        )

        from claimguard.scoring.engine import _sync_claim_json_ext

        _sync_claim_json_ext(score.claim, score)

        return OverrideClaimFraudScoreMutation(fraud_score=score)


class Mutation(graphene.ObjectType):
    """ClaimGuard GraphQL mutations."""

    override_claim_fraud_score = OverrideClaimFraudScoreMutation.Field()
