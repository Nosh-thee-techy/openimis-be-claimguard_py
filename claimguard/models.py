"""
ClaimGuard data models.

Persists fraud risk scores produced when a claim is submitted or re-scored.
Each ClaimFraudScore row is a 1-to-1 companion to a claim.Claim record.

We use a lightweight UUID model (not HistoryModel) because FraudAuditLog already
provides the audit trail and avoids django-simple-history table overhead.
"""

import uuid

from claim.models import Claim
from core.fields import DateTimeField
from core.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class RiskTier(models.TextChoices):
    """
    Three-tier decision bands used by ClaimGuard reviewers.

    Maps to the UI badge colours and downstream workflow routing.
    """

    AUTO_APPROVE = "green", "Auto-approve (0–30)"
    FLAG_REVIEW = "amber", "Flag for review (31–70)"
    AUTO_HOLD = "red", "Auto-hold (71–100)"


def tier_for_score(score: int) -> str:
    """
    Convert a numeric risk score into a RiskTier value.

    Centralised here so models, API, and FHIR builders stay consistent.
    """
    if score <= 30:
        return RiskTier.AUTO_APPROVE
    if score <= 70:
        return RiskTier.FLAG_REVIEW
    return RiskTier.AUTO_HOLD


class ClaimGuardModel(models.Model):
    """Shared openIMIS-style UUID primary key and soft-delete fields."""

    id = models.UUIDField(
        primary_key=True,
        db_column="UUID",
        default=uuid.uuid4,
        editable=False,
    )
    is_deleted = models.BooleanField(db_column="isDeleted", default=False)
    json_ext = models.JSONField(db_column="Json_ext", blank=True, null=True)
    date_created = DateTimeField(db_column="DateCreated", default=timezone.now)
    date_updated = DateTimeField(db_column="DateUpdated", default=timezone.now)

    class Meta:
        abstract = True


class ClaimFraudScore(ClaimGuardModel):
    """
    Fraud risk assessment attached to a single insurance claim.

    Created automatically by the claim post_save signal (see signals.py).
    Reviewers and auditors can override the automated decision; every
    override is logged for audit compliance.
    """

    claim = models.OneToOneField(
        Claim,
        on_delete=models.DO_NOTHING,
        db_column="ClaimID",
        related_name="fraud_score",
        help_text="The claim this risk assessment belongs to.",
    )
    risk_score = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Final fraud risk score on a 0 (safe) – 100 (high risk) scale.",
    )
    risk_tier = models.CharField(
        max_length=10,
        choices=RiskTier.choices,
        db_index=True,
        help_text="Workflow routing tier derived from risk_score.",
    )
    ml_score = models.FloatField(
        blank=True,
        null=True,
        help_text="Raw Isolation Forest anomaly score (higher = more anomalous).",
    )
    rule_score = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Points contributed by rule-based checks alone.",
    )
    triggered_rules = models.JSONField(
        default=list,
        blank=True,
        help_text="List of dicts: {code, label, points, detail} for each fired rule.",
    )
    feature_vector = models.JSONField(
        default=dict,
        blank=True,
        help_text="Numeric features fed to the ML model (stored for audit/debug).",
    )
    decision_reason = models.TextField(
        blank=True,
        help_text="Human-readable summary shown to reviewers on the claims list.",
    )
    fhir_claim_response_id = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        db_index=True,
        help_text="UUID of the FHIR R4 ClaimResponse resource, when published.",
    )
    is_overridden = models.BooleanField(
        default=False,
        help_text="True when a senior auditor has manually changed the decision.",
    )
    override_reason = models.TextField(
        blank=True,
        help_text="Mandatory justification when is_overridden is True.",
    )
    overridden_by = models.ForeignKey(
        User,
        on_delete=models.DO_NOTHING,
        db_column="OverriddenByUUID",
        related_name="claimguard_overrides",
        blank=True,
        null=True,
    )
    overridden_at = models.DateTimeField(blank=True, null=True)
    model_version = models.CharField(
        max_length=32,
        default="untrained",
        help_text="Label of the Isolation Forest artefact used for this score.",
    )
    scored_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when this score was last computed.",
    )
    version = models.IntegerField(default=1)

    class Meta:
        managed = True
        db_table = "claimguard_ClaimFraudScore"
        verbose_name = "Claim fraud score"
        verbose_name_plural = "Claim fraud scores"
        indexes = [
            models.Index(fields=["risk_tier", "scored_at"]),
            models.Index(fields=["risk_score"]),
        ]

    def __str__(self) -> str:
        return f"Claim {self.claim_id} → {self.risk_score} ({self.risk_tier})"

    def save(self, *args, **kwargs):
        """Always keep risk_tier in sync with risk_score before persisting."""
        self.risk_tier = tier_for_score(self.risk_score)
        self.date_updated = timezone.now()
        super().save(*args, **kwargs)

    @property
    def badge_colour(self) -> str:
        """Frontend alias for risk_tier — used by the React risk badge."""
        return self.risk_tier

    @property
    def requires_review(self) -> bool:
        """True when the claim must be seen by a human reviewer."""
        return self.risk_tier in (RiskTier.FLAG_REVIEW, RiskTier.AUTO_HOLD)


class FraudAuditLog(ClaimGuardModel):
    """
    Immutable audit trail for scoring events and manual overrides.

    Separate from ClaimFraudScore so we retain history even when a
    score is recomputed after a claim edit.
    """

    class Action(models.TextChoices):
        SCORED = "scored", "Automated scoring"
        OVERRIDDEN = "overridden", "Manual override"
        FHIR_PUBLISHED = "fhir_published", "FHIR ClaimResponse published"

    claim = models.ForeignKey(
        Claim,
        on_delete=models.DO_NOTHING,
        db_column="ClaimID",
        related_name="fraud_audit_logs",
    )
    fraud_score = models.ForeignKey(
        ClaimFraudScore,
        on_delete=models.DO_NOTHING,
        db_column="FraudScoreUUID",
        related_name="audit_logs",
        blank=True,
        null=True,
    )
    action = models.CharField(max_length=20, choices=Action.choices)
    actor = models.ForeignKey(
        User,
        on_delete=models.DO_NOTHING,
        db_column="ActorUUID",
        blank=True,
        null=True,
    )
    detail = models.JSONField(default=dict, blank=True)
    version = models.IntegerField(default=1)

    class Meta:
        managed = True
        db_table = "claimguard_FraudAuditLog"
        ordering = ["-date_created"]
