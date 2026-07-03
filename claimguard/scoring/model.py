"""
Isolation Forest ML model wrapper for ClaimGuard.

Trained offline via `manage.py train_model` and loaded at scoring time.
Falls back gracefully when no artefact exists (rules-only scoring).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional, Tuple

import joblib
import numpy as np
from django.conf import settings
from sklearn.ensemble import IsolationForest

logger = logging.getLogger(__name__)

# Default untrained model parameters — conservative for small demo datasets.
DEFAULT_CONTAMINATION = 0.1
DEFAULT_ESTIMATORS = 100
MODEL_VERSION = "isolation_forest_v1"


def _default_model_path() -> Path:
    """Resolve the on-disk path for the serialised model artefact."""
    try:
        from claimguard.apps import ClaimGuardConfig

        rel = ClaimGuardConfig.model_path
    except Exception:
        rel = "claimguard/ml_artifacts/isolation_forest.joblib"

    # Prefer path relative to the Django project root.
    base = Path(getattr(settings, "BASE_DIR", Path.cwd()))
    return base / rel


def train_isolation_forest(
    feature_matrix: np.ndarray,
    contamination: float = DEFAULT_CONTAMINATION,
) -> IsolationForest:
    """
    Fit a new Isolation Forest on the supplied feature matrix.

    Used by the train_model management command.
    """
    model = IsolationForest(
        n_estimators=DEFAULT_ESTIMATORS,
        contamination=contamination,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(feature_matrix)
    return model


def save_model(model: IsolationForest, path: Optional[Path] = None) -> Path:
    """Persist a trained model to disk, creating parent dirs as needed."""
    dest = path or _default_model_path()
    dest.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "version": MODEL_VERSION}, dest)
    logger.info("ClaimGuard model saved to %s", dest)
    return dest


def load_model(path: Optional[Path] = None) -> Optional[dict]:
    """Load a serialised model bundle, or None if the artefact is missing."""
    dest = path or _default_model_path()
    if not dest.exists():
        logger.warning("ClaimGuard ML model not found at %s — rules-only mode.", dest)
        return None
    return joblib.load(dest)


def anomaly_score(feature_vector: list, path: Optional[Path] = None) -> Tuple[Optional[float], str]:
    """
    Score a single claim feature vector.

    Returns (ml_score_0_to_100, model_version). ml_score is None when no
    trained model is available.
    """
    bundle = load_model(path)
    if bundle is None:
        return None, "untrained"

    model: IsolationForest = bundle["model"]
    version = bundle.get("version", MODEL_VERSION)

    X = np.array([feature_vector])
    # decision_function: lower (more negative) = more anomalous.
    raw = float(model.decision_function(X)[0])

    # Map to 0–100 where 100 = most anomalous. Typical raw range ≈ [-0.5, 0.5].
    normalised = int(max(0, min(100, (0.5 - raw) * 100)))
    return normalised, version
