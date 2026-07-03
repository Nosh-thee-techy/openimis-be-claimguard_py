"""
Generate synthetic labelled claims for training ClaimGuard.

Creates a mix of legitimate and deliberately fraudulent claims so the
Isolation Forest has enough positive/negative examples beyond the 24
real Tanzania demo claims.
"""

import random
from datetime import timedelta

from claim.models import Claim
from django.core.management.base import BaseCommand
from django.utils import timezone
from insuree.models import Insuree


class Command(BaseCommand):
    help = "Generate synthetic claims with fraud labels for ClaimGuard ML training."

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=100,
            help="Number of synthetic claims to create (default 100).",
        )
        parser.add_argument(
            "--fraud-ratio",
            type=float,
            default=0.25,
            help="Fraction of claims that should look fraudulent (default 0.25).",
        )

    def handle(self, *args, **options):
        count = options["count"]
        fraud_ratio = options["fraud_ratio"]
        insurees = list(Insuree.objects.filter(validity_to__isnull=True)[:50])
        template = (
            Claim.objects.filter(
                validity_to__isnull=True,
                health_facility__isnull=False,
                icd__isnull=False,
            )
            .select_related("health_facility", "icd")
            .first()
        )

        if not insurees:
            self.stderr.write("No insurees found — load demo data first.")
            return

        if not template:
            self.stderr.write(
                "No existing claim with health_facility and icd — load demo data first."
            )
            return

        created = 0
        today = timezone.now().date()

        for i in range(count):
            is_fraud = random.random() < fraud_ratio
            insuree = random.choice(insurees)
            date_from = today - timedelta(days=random.randint(1, 180))

            if is_fraud:
                # Fraud patterns: high value, late submission, duplicate code.
                claimed = random.uniform(80000, 250000)
                date_claimed = date_from + timedelta(days=random.randint(60, 200))
                code = f"SYN-FRAUD-{i:04d}"
            else:
                claimed = random.uniform(500, 15000)
                date_claimed = date_from + timedelta(days=random.randint(0, 14))
                code = f"SYN-LEGIT-{i:04d}"

            Claim.objects.create(
                insuree=insuree,
                health_facility=template.health_facility,
                icd=template.icd,
                code=code,
                date_from=date_from,
                date_to=date_from,
                date_claimed=date_claimed,
                status=2,
                claimed=claimed,
                audit_user_id=template.audit_user_id or 1,
            )
            created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Created {created} synthetic claims "
                f"(~{int(count * fraud_ratio)} fraudulent)."
            )
        )
