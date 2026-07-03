"""Backfill fraud scores for all submitted claims."""

from claim.models import Claim
from claimguard.scoring.engine import score_claim
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Score all submitted claims that lack a fraud score (or re-score with --force)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-score claims that already have a fraud score.",
        )

    def handle(self, *args, **options):
        qs = Claim.objects.filter(status__gte=2, validity_to__isnull=True)
        if not options["force"]:
            qs = qs.filter(fraud_score__isnull=True)

        count = 0
        for claim in qs.iterator():
            score_claim(claim, is_new=False)
            count += 1

        self.stdout.write(self.style.SUCCESS(f"Scored {count} claims."))
