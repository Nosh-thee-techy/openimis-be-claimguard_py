"""Django admin registrations for ClaimGuard."""

from claimguard.models import ClaimFraudScore, FraudAuditLog
from django.contrib import admin


@admin.register(ClaimFraudScore)
class ClaimFraudScoreAdmin(admin.ModelAdmin):
    list_display = ("claim_id", "risk_score", "risk_tier", "rule_score", "ml_score", "scored_at")
    list_filter = ("risk_tier", "is_overridden")
    search_fields = ("claim_id", "decision_reason")
    readonly_fields = ("scored_at", "feature_vector", "triggered_rules")


@admin.register(FraudAuditLog)
class FraudAuditLogAdmin(admin.ModelAdmin):
    list_display = ("claim_id", "action", "date_created")
    list_filter = ("action",)
