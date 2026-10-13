"""Inference helpers for the experimental BP-associated category classifier."""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Real
from typing import Mapping

import numpy as np
import pandas as pd
from xgboost import XGBClassifier

try:
    from train_selected_model import FEATURE_COLUMNS, LABEL_MAPPING, MODEL_PATH
except ModuleNotFoundError:
    from .train_selected_model import FEATURE_COLUMNS, LABEL_MAPPING, MODEL_PATH


_CATEGORY_BY_ID = {class_id: category for category, class_id in LABEL_MAPPING.items()}
_MODEL: XGBClassifier | None = None


@dataclass(frozen=True)
class BPCategoryPrediction:
    """Experimental BP-associated classification result."""

    predicted_class_id: int
    predicted_category: str
    probabilities: dict[str, float]
    experimental_result: str = (
        "Experimental BP-associated classification result; not a diagnosis "
        "or a prediction of future blood pressure."
    )


def _load_model() -> XGBClassifier:
    global _MODEL
    if _MODEL is None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(f"Saved model not found: {MODEL_PATH}")
        _MODEL = XGBClassifier()
        _MODEL.load_model(MODEL_PATH)
    return _MODEL


def _features_to_frame(features: Mapping[str, Real]) -> pd.DataFrame:
    missing = [column for column in FEATURE_COLUMNS if column not in features]
    if missing:
        raise ValueError(f"Missing required feature(s): {', '.join(missing)}")

    values = [features[column] for column in FEATURE_COLUMNS]
    invalid = [
        column
        for column, value in zip(FEATURE_COLUMNS, values)
        if isinstance(value, bool) or not isinstance(value, Real)
    ]
    if invalid:
        raise ValueError(f"Feature values must be numeric: {', '.join(invalid)}")

    frame = pd.DataFrame([values], columns=FEATURE_COLUMNS, dtype=float)
    if not np.isfinite(frame.to_numpy()).all():
        raise ValueError("Feature values must be finite and must not be missing")
    return frame


def predict_bp_category(features: Mapping[str, Real]) -> BPCategoryPrediction:
    """Predict an experimental BP-associated category from one feature mapping."""
    if not isinstance(features, Mapping):
        raise TypeError("features must be a mapping of feature names to numeric values")

    input_frame = _features_to_frame(features)
    model = _load_model()
    predicted_class_id = int(model.predict(input_frame)[0])
    probabilities_array = np.asarray(model.predict_proba(input_frame)[0], dtype=float)

    if predicted_class_id not in _CATEGORY_BY_ID:
        raise ValueError(f"Model returned unknown class ID: {predicted_class_id}")
    class_ids = np.asarray(model.classes_)
    if class_ids.shape != (len(LABEL_MAPPING),):
        raise ValueError("Model returned an unexpected number of classes")
    if any(int(class_id) not in _CATEGORY_BY_ID for class_id in class_ids):
        raise ValueError("Model returned an unknown class ID")
    if probabilities_array.shape != class_ids.shape:
        raise ValueError("Model returned an unexpected number of class probabilities")
    if not np.isfinite(probabilities_array).all():
        raise ValueError("Model returned non-finite class probabilities")

    probabilities = {
        _CATEGORY_BY_ID[int(class_id)]: float(probabilities_array[index])
        for index, class_id in enumerate(class_ids)
    }
    return BPCategoryPrediction(
        predicted_class_id=predicted_class_id,
        predicted_category=_CATEGORY_BY_ID[predicted_class_id],
        probabilities=probabilities,
    )
