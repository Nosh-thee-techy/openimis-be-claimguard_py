"""One-off: resync risk_tier from risk_score for all ClaimGuard records."""
from claimguard.models import ClaimFraudScore, tier_for_score
from claimguard.scoring.engine import _sync_claim_json_ext

updated = 0
for score in ClaimFraudScore.objects.filter(is_deleted=False).select_related("claim"):
    correct = tier_for_score(score.risk_score)
    if score.risk_tier != correct:
        score.risk_tier = correct
        score.save(update_fields=["risk_tier", "date_updated"])
        _sync_claim_json_ext(score.claim, score)
        updated += 1

print(f"Resynced {updated} fraud score tiers")
