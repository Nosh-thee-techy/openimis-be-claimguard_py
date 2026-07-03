# ClaimGuard — openIMIS Fraud Detection Module

AI-powered claims fraud detection for openIMIS hackathon Track 3.

## What it does

Scores every submitted claim (0–100) using rule-based checks + Isolation Forest ML:

| Score | Tier | Action |
|-------|------|--------|
| 0–30 | green | Auto-approve |
| 31–70 | amber | Flag for review |
| 71–100 | red | Auto-hold |

## Install (local Docker)

1. Module is mounted via `compose.base.yml`:
   ```
   ../openimis-be-claimguard_py:/openimis-be/openimis-be-claimguard_py
   ```

2. Registered in `openimis-be_py/openimis.json`:
   ```json
   { "name": "claimguard", "pip": "-e /openimis-be/openimis-be-claimguard_py" }
   ```

3. Install inside the backend container and migrate:
   ```bash
   docker exec openimis-dist_dkr-backend-1 pip install -e /openimis-be/openimis-be-claimguard_py
   docker exec openimis-dist_dkr-backend-1 python manage.py migrate claimguard
   docker compose restart backend
   ```

## Train the model

```bash
docker exec openimis-dist_dkr-backend-1 python manage.py generate_synthetic --count 100
docker exec openimis-dist_dkr-backend-1 python manage.py train_model
```

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/claimguard/scores/` | List scores (filter: `?tier=red`) |
| GET | `/api/claimguard/scores/<claim_id>/` | Score for one claim |
| POST | `/api/claimguard/scores/<claim_id>/override/` | Auditor override |
| GET | `/api/claimguard/analytics/` | Dashboard summary |

## Tests

```bash
python manage.py test claimguard
```
