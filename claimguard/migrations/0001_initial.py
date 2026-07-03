# Generated manually for ClaimGuard hackathon module.

import uuid

import core.fields
import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("claim", "0035_merge_20241004_1020"),
        ("core", "0031_alter_mutationlog_client_mutation_id"),
    ]

    operations = [
        migrations.CreateModel(
            name="ClaimFraudScore",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        db_column="UUID",
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("is_deleted", models.BooleanField(db_column="isDeleted", default=False)),
                ("json_ext", models.JSONField(blank=True, db_column="Json_ext", null=True)),
                (
                    "date_created",
                    core.fields.DateTimeField(
                        db_column="DateCreated",
                        default=None,
                        null=True,
                    ),
                ),
                (
                    "date_updated",
                    core.fields.DateTimeField(
                        db_column="DateUpdated",
                        default=None,
                        null=True,
                    ),
                ),
                (
                    "risk_score",
                    models.PositiveSmallIntegerField(
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(100),
                        ]
                    ),
                ),
                (
                    "risk_tier",
                    models.CharField(
                        choices=[
                            ("green", "Auto-approve (0–30)"),
                            ("amber", "Flag for review (31–70)"),
                            ("red", "Auto-hold (71–100)"),
                        ],
                        db_index=True,
                        max_length=10,
                    ),
                ),
                ("ml_score", models.FloatField(blank=True, null=True)),
                (
                    "rule_score",
                    models.PositiveSmallIntegerField(
                        default=0,
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(100),
                        ],
                    ),
                ),
                ("triggered_rules", models.JSONField(blank=True, default=list)),
                ("feature_vector", models.JSONField(blank=True, default=dict)),
                ("decision_reason", models.TextField(blank=True)),
                (
                    "fhir_claim_response_id",
                    models.CharField(
                        blank=True, db_index=True, max_length=64, null=True
                    ),
                ),
                ("is_overridden", models.BooleanField(default=False)),
                ("override_reason", models.TextField(blank=True)),
                ("overridden_at", models.DateTimeField(blank=True, null=True)),
                ("model_version", models.CharField(default="untrained", max_length=32)),
                ("scored_at", models.DateTimeField(auto_now_add=True)),
                (
                    "claim",
                    models.OneToOneField(
                        db_column="ClaimID",
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="fraud_score",
                        to="claim.claim",
                    ),
                ),
                (
                    "overridden_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="OverriddenByUUID",
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="claimguard_overrides",
                        to="core.user",
                    ),
                ),
                (
                    "user_created",
                    models.ForeignKey(
                        blank=True,
                        db_column="UserCreatedUUID",
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="claimguard_score_created",
                        to="core.user",
                    ),
                ),
                (
                    "user_updated",
                    models.ForeignKey(
                        blank=True,
                        db_column="UserUpdatedUUID",
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="claimguard_score_updated",
                        to="core.user",
                    ),
                ),
            ],
            options={
                "verbose_name": "Claim fraud score",
                "verbose_name_plural": "Claim fraud scores",
                "db_table": "claimguard_ClaimFraudScore",
                "managed": True,
            },
        ),
        migrations.CreateModel(
            name="FraudAuditLog",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        db_column="UUID",
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("is_deleted", models.BooleanField(db_column="isDeleted", default=False)),
                ("json_ext", models.JSONField(blank=True, db_column="Json_ext", null=True)),
                (
                    "date_created",
                    core.fields.DateTimeField(
                        db_column="DateCreated",
                        default=None,
                        null=True,
                    ),
                ),
                (
                    "date_updated",
                    core.fields.DateTimeField(
                        db_column="DateUpdated",
                        default=None,
                        null=True,
                    ),
                ),
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("scored", "Automated scoring"),
                            ("overridden", "Manual override"),
                            ("fhir_published", "FHIR ClaimResponse published"),
                        ],
                        max_length=20,
                    ),
                ),
                ("detail", models.JSONField(blank=True, default=dict)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        db_column="ActorUUID",
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        to="core.user",
                    ),
                ),
                (
                    "claim",
                    models.ForeignKey(
                        db_column="ClaimID",
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="fraud_audit_logs",
                        to="claim.claim",
                    ),
                ),
                (
                    "fraud_score",
                    models.ForeignKey(
                        blank=True,
                        db_column="FraudScoreUUID",
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="audit_logs",
                        to="claimguard.claimfraudscore",
                    ),
                ),
                (
                    "user_created",
                    models.ForeignKey(
                        blank=True,
                        db_column="UserCreatedUUID",
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="claimguard_audit_created",
                        to="core.user",
                    ),
                ),
                (
                    "user_updated",
                    models.ForeignKey(
                        blank=True,
                        db_column="UserUpdatedUUID",
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="claimguard_audit_updated",
                        to="core.user",
                    ),
                ),
            ],
            options={
                "db_table": "claimguard_FraudAuditLog",
                "ordering": ["-date_created"],
                "managed": True,
            },
        ),
        migrations.AddIndex(
            model_name="claimfraudscore",
            index=models.Index(
                fields=["risk_tier", "scored_at"],
                name="claimguard__risk_ti_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="claimfraudscore",
            index=models.Index(
                fields=["risk_score"],
                name="claimguard__risk_sc_idx",
            ),
        ),
    ]
