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

_MODEL_FILES = {
    "ml3_v1.0": ("ml3_logistic_regression.joblib", "ml3_model_metadata.json"),
    "ml3_v2.0": ("v2_logistic_regression.joblib", "ml3_v2_model_metadata.json"),
}
_MODEL_CACHE = {MODEL_VERSION: (MODEL, MODEL_METADATA)}

def get_available_models() -> list[dict]:
    """Return model metadata for artifacts present in the ML directory."""
    models = []
    for version, (model_file, metadata_file) in _MODEL_FILES.items():
        metadata_path = _ML_DIR / metadata_file
        model_path = _ML_DIR / model_file
        if metadata_path.exists() and model_path.exists():
            with open(metadata_path, "r") as metadata_handle:
                metadata = json.load(metadata_handle)
            models.append({
                "model_version": metadata.get("model_version", version),
                "model_type": metadata.get("model_type", "Unknown"),
                "features": metadata.get("features", []),
            })
    return models

def _get_model(model_version: str | None):
    version = model_version or MODEL_VERSION
    if version not in _MODEL_FILES:
        raise ValueError(f"Unknown model version: {version}")
    if version not in _MODEL_CACHE:
        model_file, metadata_file = _MODEL_FILES[version]
        model_path = _ML_DIR / model_file
        metadata_path = _ML_DIR / metadata_file
        if not model_path.exists() or not metadata_path.exists():
            raise ValueError(f"Model artifacts are unavailable: {version}")
        with open(metadata_path, "r") as metadata_handle:
            metadata = json.load(metadata_handle)
        _MODEL_CACHE[version] = (joblib.load(model_path), metadata)
    return _MODEL_CACHE[version]

def predict(feature_vector: list[float], model_version: str | None = None) -> float:
    """Returns probability of high network activity."""
    # model.predict_proba returns array of shape (n_samples, n_classes)
    # class 1 (index 1) is high activity
    model, _ = _get_model(model_version)
    probas = model.predict_proba([feature_vector])
    return float(probas[0][1])

def get_feature_contributions(model_version: str | None = None) -> list[tuple[str, float]]:
    """Returns feature names and their coefficients, sorted by absolute magnitude."""
    # Logistic Regression has coef_ of shape (1, n_features)
    model, metadata = _get_model(model_version)
    coefs = model.coef_[0]
    contributions = list(zip(metadata.get("features", []), coefs))
    # Sort by absolute magnitude descending
    contributions.sort(key=lambda x: abs(x[1]), reverse=True)
    return contributions
