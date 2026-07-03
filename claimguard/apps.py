"""ClaimGuard application configuration and openIMIS module registration."""

from django.apps import AppConfig

MODULE_NAME = "claimguard"

DEFAULT_CFG = {
    # GraphQL permission IDs — align with core role management in production.
    "gql_query_fraud_scores_perms": ["121001"],
    "gql_mutation_override_fraud_score_perms": ["121002"],
    # Scoring thresholds (override via ModuleConfiguration in Django admin).
    "auto_approve_max": 30,
    "flag_review_max": 70,
    # ML model artefact path inside the container / module root.
    "model_path": "claimguard/ml_artifacts/isolation_forest.joblib",
    # Weight blend: final = rule_weight * rule + ml_weight * ml  (must sum to 1).
    "rule_weight": 0.6,
    "ml_weight": 0.4,
}


class ClaimGuardConfig(AppConfig):
    """Registers ClaimGuard with Django and loads openIMIS module configuration."""

    default_auto_field = "django.db.models.BigAutoField"
    name = MODULE_NAME
    verbose_name = "ClaimGuard Fraud Detection"

    gql_query_fraud_scores_perms = None
    gql_mutation_override_fraud_score_perms = None
    auto_approve_max = 30
    flag_review_max = 70
    model_path = DEFAULT_CFG["model_path"]
    rule_weight = 0.6
    ml_weight = 0.4

    @classmethod
    def _load_config(cls, cfg: dict) -> None:
        """Apply ModuleConfiguration values onto this AppConfig class."""
        for field, value in cfg.items():
            if hasattr(cls, field):
                setattr(cls, field, value)

    def ready(self) -> None:
        """
        Hook called once Django starts.

        Loads module config from the database and connects claim signals.
        """
        from core.models import ModuleConfiguration

        cfg = ModuleConfiguration.get_or_default(MODULE_NAME, DEFAULT_CFG)
        self.__class__._load_config(cfg)

        # Import here to avoid AppRegistryNotReady during Django startup.
        import claimguard.signals  # noqa: F401
