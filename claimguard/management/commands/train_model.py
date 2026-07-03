"""
Train the ClaimGuard Isolation Forest on existing claims.

Usage:
    python manage.py train_model
    python manage.py train_model --limit 500
"""

import numpy as np
from claim.models import Claim
from claimguard.scoring.features import extract_features, features_to_vector
from claimguard.scoring.model import save_model, train_isolation_forest
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Train the ClaimGuard Isolation Forest ML model on claim history."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Max claims to use (0 = all submitted claims).",
        )
        parser.add_argument(
            "--contamination",
            type=float,
            default=0.1,
            help="Expected fraud proportion for Isolation Forest.",
        )

    def handle(self, *args, **options):
        qs = Claim.objects.filter(status__gte=2, validity_to__isnull=True)
        if options["limit"]:
            qs = qs[: options["limit"]]

        claims = list(qs)
        if len(claims) < 10:
            self.stderr.write(
                f"Only {len(claims)} claims available — run generate_synthetic first."
            )
            return

        matrix = []
        for claim in claims:
            features = extract_features(claim)
            matrix.append(features_to_vector(features))

        X = np.array(matrix)
        model = train_isolation_forest(X, contamination=options["contamination"])
        path = save_model(model)

        self.stdout.write(
            self.style.SUCCESS(
                f"Trained Isolation Forest on {len(claims)} claims → {path}"
            )
        )
