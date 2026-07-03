"""GraphQL schema for ClaimGuard — exposes fraud scores to the openIMIS frontend."""

import graphene
from claimguard.models import ClaimFraudScore
from django.core.exceptions import PermissionDenied
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


class Mutation(graphene.ObjectType):
    """ClaimGuard has no public mutations yet — overrides go via REST."""

    pass
