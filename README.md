# ClaimGuard — Backend Module (`openimis-be-claimguard_py`)

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Track 3](https://img.shields.io/badge/Track-3%20Claims%20%26%20Fraud-2ea44f)](https://openimis.org)
[![Hackathon](https://img.shields.io/badge/Tag-v1.0--hackathon-teal)](https://github.com/Nosh-thee-techy/openimis-be-claimguard_py/releases/tag/v1.0-hackathon)

**Technikali / openIMIS Hackathon submission** — Track 3 (Claims Management & Fraud Detection)  
Cross-tracks: Track 5 (AI & Emerging Tech) · Track 1 (Innovation)

Django backend module that scores every submitted claim (0–100) using rule-based checks and an Isolation Forest ML model, exposed via REST API and GraphQL.

---

## Related repositories

| Repo | Role |
|------|------|
| [openimis-fe-claimguard_js](https://github.com/Nosh-thee-techy/openimis-fe-claimguard_js) | React UI — dashboard, XAI panel, override workflow |
| [openimis-be_py](https://github.com/Nosh-thee-techy/openimis-be_py) | Backend assembly (`openimis.json` registration) |
| [openimis-fe_js](https://github.com/Nosh-thee-techy/openimis-fe_js) | Frontend assembly |
| [openimis-dist_dkr](https://github.com/Nosh-thee-techy/openimis-dist_dkr) | Docker Compose deployment + full setup guide |

---

## What it does

On every claim submission, ClaimGuard:

1. Fires a Django `post_save` signal (no core workflow patching)
2. Extracts facility-specific billing features from historical data
3. Runs a **rule engine** + **Isolation Forest** anomaly model
4. Persists a `ClaimFraudScore` record and syncs risk metadata to `json_ext`
5. Emits a FHIR `ClaimResponse` extension for interoperability

### Risk tiers

| Score | Tier | Default action |
|-------|------|----------------|
| 0–30 | `green` | Auto-approve |
| 31–70 | `amber` | Flag for review |
| 71–100 | `red` | Auto-hold |

---

## Architecture

```
Claim saved → signals.py → scoring/engine.py
                              ├── features.py   (ORM aggregations)
                              ├── rules.py      (deterministic checks)
                              └── model.py      (Isolation Forest)
                         → ClaimFraudScore + FraudAuditLog
                         → GraphQL schema + REST API
```

---

## Installation

### Docker (recommended)

Mount this repo in `openimis-dist_dkr/compose.base.yml`:

```yaml
- ../openimis-be-claimguard_py:/openimis-be/openimis-be-claimguard_py
```

Register in `openimis-be_py/openimis.json`:

```json
{ "name": "claimguard", "pip": "-e /openimis-be/openimis-be-claimguard_py" }
```

Then:

```bash
docker compose up -d
docker compose exec backend pip install -e /openimis-be/openimis-be-claimguard_py
docker compose exec backend python manage.py migrate claimguard
docker compose exec backend python manage.py generate_synthetic --count 100
docker compose exec backend python manage.py train_model
docker compose exec backend python manage.py score_claims
```

---

## Management commands

| Command | Description |
|---------|-------------|
| `migrate claimguard` | Apply database migrations |
| `generate_synthetic --count N` | Seed synthetic claims for training |
| `train_model` | Train Isolation Forest on feature matrix |
| `score_claims` | Batch-score existing claims in the database |

---

## API

### REST

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/claimguard/scores/` | List scores (`?tier=red`) |
| `GET` | `/api/claimguard/scores/<claim_id>/` | Score for one claim |
| `POST` | `/api/claimguard/scores/<claim_id>/override/` | Auditor override with justification |
| `GET` | `/api/claimguard/analytics/` | Dashboard summary metrics |

### GraphQL

```graphql
query {
  claimFraudScores(tier: "red", limit: 50) {
    riskScore riskTier decisionReason triggeredRules mlScore ruleScore
    claim { id uuid code }
  }
}

mutation {
  overrideClaimFraudScore(claimUuid: "...", riskScore: 15, reason: "Verified with clinic") {
    fraudScore { riskScore riskTier isOverridden }
  }
}
```

---

## Tests

Run inside the backend Docker container:

```bash
docker compose exec backend python manage.py test claimguard
```

---

## License

GNU Affero General Public License v3 — consistent with the openIMIS ecosystem.
