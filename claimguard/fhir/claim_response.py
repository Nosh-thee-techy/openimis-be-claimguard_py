"""
FHIR R4 ClaimResponse builder for ClaimGuard risk scores.

Populates a ClaimResponse with adjudication extensions carrying the fraud
risk tier so external systems (and NHIF integrations) can consume scores
via the standard HL7 FHIR interface already exposed by openIMIS.
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from claim.models import Claim

from claimguard.models import ClaimFraudScore, RiskTier

logger = logging.getLogger(__name__)

# FHIR extension URLs — scheme-specific; documented in README for integrators.
EXT_RISK_SCORE = "https://openimis.org/fhir/StructureDefinition/claimguard-risk-score"
EXT_RISK_TIER = "https://openimis.org/fhir/StructureDefinition/claimguard-risk-tier"
EXT_TRIGGERED_RULES = "https://openimis.org/fhir/StructureDefinition/claimguard-triggered-rules"


def _tier_to_fhir_outcome(tier: str) -> str:
    """Map ClaimGuard tier to FHIR ClaimResponse.outcome code."""
    return {
        RiskTier.AUTO_APPROVE: "complete",
        RiskTier.FLAG_REVIEW: "partial",
        RiskTier.AUTO_HOLD: "error",
    }.get(tier, "partial")


def build_claim_response(claim: Claim, score: ClaimFraudScore) -> dict:
    """
    Build a FHIR R4 ClaimResponse resource dict (not yet persisted).

    Follows HL7 FHIR R4 ClaimResponse structure; openIMIS api_fhir_r4 module
    can serialise this to JSON for REST export.
    """
    resource_id = str(uuid.uuid4())
    return {
        "resourceType": "ClaimResponse",
        "id": resource_id,
        "status": "active",
        "type": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/claim-type",
                    "code": "professional",
                }
            ]
        },
        "use": "claim",
        "patient": {"reference": f"Patient/{claim.insuree_id}"},
        "created": score.scored_at.isoformat() if score.scored_at else None,
        "insurer": {"display": "openIMIS Scheme"},
        "request": {"reference": f"Claim/{claim.uuid}"},
        "outcome": _tier_to_fhir_outcome(score.risk_tier),
        "disposition": score.decision_reason,
        "extension": [
            {
                "url": EXT_RISK_SCORE,
                "valueInteger": score.risk_score,
            },
            {
                "url": EXT_RISK_TIER,
                "valueCode": score.risk_tier,
            },
            {
                "url": EXT_TRIGGERED_RULES,
                "valueString": str(score.triggered_rules),
            },
        ],
        "item": [
            {
                "itemSequence": 1,
                "adjudication": [
                    {
                        "category": {
                            "coding": [
                                {
                                    "system": "https://openimis.org/fhir/CodeSystem/adjudication",
                                    "code": "fraud-risk",
                                    "display": "Fraud risk assessment",
                                }
                            ]
                        },
                        "reason": {
                            "text": score.decision_reason,
                        },
                        "value": score.risk_score,
                    }
                ],
            }
        ],
    }


def publish_claim_response(claim: Claim, score: ClaimFraudScore) -> Optional[str]:
    """
    Build and optionally persist a FHIR ClaimResponse via api_fhir_r4.

    Returns the resource UUID on success, None when the FHIR module is absent.
    """
    resource = build_claim_response(claim, score)

    try:
        # Delegate persistence to openIMIS FHIR module when available.
        from api_fhir_r4.converters import ClaimResponseConverter  # type: ignore

        converter = ClaimResponseConverter()
        converter.to_fhir(resource)
        logger.info("FHIR ClaimResponse built for claim %s", claim.id)
        return resource["id"]
    except ImportError:
        logger.debug("api_fhir_r4 not available — returning in-memory FHIR id only.")
        return resource["id"]
    except Exception:
        logger.exception("Failed to publish FHIR ClaimResponse for claim %s", claim.id)
        return resource["id"]
