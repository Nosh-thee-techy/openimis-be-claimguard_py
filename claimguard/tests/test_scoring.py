"""
Unit tests for ClaimGuard scoring logic.

These tests run without a trained ML model (rules-only mode) so they are
fast and deterministic in CI.
"""

from unittest.mock import MagicMock, patch

from claimguard.models import RiskTier, tier_for_score
from claimguard.scoring.rules import evaluate_rules
from django.test import SimpleTestCase


class TierMappingTests(SimpleTestCase):
    """Verify the three-tier threshold boundaries."""

    def test_auto_approve_tier(self):
        self.assertEqual(tier_for_score(0), RiskTier.AUTO_APPROVE)
        self.assertEqual(tier_for_score(30), RiskTier.AUTO_APPROVE)

    def test_flag_review_tier(self):
        self.assertEqual(tier_for_score(31), RiskTier.FLAG_REVIEW)
        self.assertEqual(tier_for_score(70), RiskTier.FLAG_REVIEW)

    def test_auto_hold_tier(self):
        self.assertEqual(tier_for_score(71), RiskTier.AUTO_HOLD)
        self.assertEqual(tier_for_score(100), RiskTier.AUTO_HOLD)


class RuleEngineTests(SimpleTestCase):
    """Verify individual fraud rules fire with the expected point values."""

    def _mock_claim(self):
        claim = MagicMock()
        claim.claimed = 150000
        return claim

    def test_ghost_patient_rule_fires(self):
        features = {"same_day_other_facilities": 3}
        score, rules = evaluate_rules(self._mock_claim(), features)
        codes = [r["code"] for r in rules]
        self.assertIn("GHOST_PATIENT", codes)
        self.assertGreater(score, 0)

    def test_duplicate_billing_rule_fires(self):
        features = {"duplicate_code_count": 2}
        score, rules = evaluate_rules(self._mock_claim(), features)
        self.assertTrue(any(r["code"] == "DUPLICATE_BILLING" for r in rules))

    def test_late_submission_rule_fires(self):
        features = {"submission_lag_days": 120}
        score, rules = evaluate_rules(self._mock_claim(), features)
        self.assertTrue(any(r["code"] == "LATE_SUBMISSION" for r in rules))

    def test_clean_claim_scores_zero(self):
        features = {
            "same_day_other_facilities": 0,
            "duplicate_code_count": 0,
            "submission_lag_days": 5,
            "total_line_items": 3,
            "facility_30d_claim_count": 5,
            "claimed_total": 5000,
            "avg_item_price": 1000,
            "avg_service_price": 1000,
        }
        score, rules = evaluate_rules(self._mock_claim(), features)
        self.assertEqual(score, 0)
        self.assertEqual(rules, [])

    def test_rule_score_capped_at_100(self):
        features = {
            "same_day_other_facilities": 10,
            "duplicate_code_count": 5,
            "submission_lag_days": 200,
            "total_line_items": 50,
            "facility_30d_claim_count": 200,
            "claimed_total": 500000,
            "avg_item_price": 100,
            "avg_service_price": 100,
        }
        score, _ = evaluate_rules(self._mock_claim(), features)
        self.assertLessEqual(score, 100)


class EngineBlendTests(SimpleTestCase):
    """Verify score blending when ML is unavailable."""

    @patch("claimguard.scoring.engine.anomaly_score", return_value=(None, "untrained"))
    @patch("claimguard.scoring.engine.ClaimFraudScore.objects.update_or_create")
    @patch("claimguard.scoring.engine.FraudAuditLog.objects.create")
    @patch("claimguard.scoring.engine.extract_features")
    @patch("claimguard.scoring.engine.evaluate_rules")
    def test_rules_only_when_no_model(
        self, mock_rules, mock_features, mock_audit, mock_upsert, mock_ml
    ):
        from claimguard.scoring.engine import score_claim

        mock_features.return_value = {}
        mock_rules.return_value = (45, [{"code": "TEST", "label": "Test", "points": 45, "detail": ""}])
        mock_upsert.return_value = (MagicMock(risk_score=45, risk_tier=RiskTier.FLAG_REVIEW), True)

        claim = MagicMock(id=1, status=2)
        score_claim(claim)

        kwargs = mock_upsert.call_args[1]["defaults"]
        self.assertEqual(kwargs["risk_score"], 45)
        self.assertEqual(kwargs["rule_score"], 45)
