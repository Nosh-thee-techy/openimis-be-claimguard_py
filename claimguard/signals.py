"""
Django signals that trigger ClaimGuard scoring on claim lifecycle events.

We listen to claim.Claim post_save so every newly submitted or updated claim
is scored without modifying openIMIS core code.
"""

import logging

from claim.models import Claim
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Claim)
def score_claim_on_save(sender, instance: Claim, created: bool, **kwargs) -> None:
    """
    Score a claim immediately after it is saved.

    Only processes claims in 'submitted' status (status >= 2 in openIMIS) to
  avoid re-scoring drafts. Re-submissions after edit trigger a fresh score.
    """
    # Status 2 = entered/submitted in standard openIMIS claim workflow.
    if instance.status is None or instance.status < 2:
        return

    try:
        from claimguard.scoring.engine import score_claim

        score_claim(instance, is_new=created)
    except Exception:
        # Never block claim submission because fraud scoring failed.
        logger.exception("ClaimGuard failed to score claim %s", instance.id)
