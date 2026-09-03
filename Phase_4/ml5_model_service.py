import os
import json
import joblib
from pathlib import Path

# Resolve path
_ML_DIR = Path(os.environ.get("NOPIS_ML_DIR", Path(__file__).resolve().parent.parent / "ml"))
MODEL_PATH = _ML_DIR / "ml3_logistic_regression.joblib"
METADATA_PATH = _ML_DIR / "ml3_model_metadata.json"

if not MODEL_PATH.exists() or not METADATA_PATH.exists():
    raise RuntimeError(f"ML5 Model initialization failed. Missing files in {_ML_DIR}")

# Load artifacts
MODEL = joblib.load(MODEL_PATH)
with open(METADATA_PATH, "r") as f:
    MODEL_METADATA = json.load(f)

MODEL_VERSION = MODEL_METADATA.get("model_version", "ml3_v1.0")
FEATURE_NAMES = MODEL_METADATA.get("features", [])

def predict(feature_vector: list[float]) -> float:
    """Returns probability of high network activity."""
    # model.predict_proba returns array of shape (n_samples, n_classes)
    # class 1 (index 1) is high activity
    probas = MODEL.predict_proba([feature_vector])
    return float(probas[0][1])

def get_feature_contributions() -> list[tuple[str, float]]:
    """Returns feature names and their coefficients, sorted by absolute magnitude."""
    # Logistic Regression has coef_ of shape (1, n_features)
    coefs = MODEL.coef_[0]
    contributions = list(zip(FEATURE_NAMES, coefs))
    # Sort by absolute magnitude descending
    contributions.sort(key=lambda x: abs(x[1]), reverse=True)
    return contributions
