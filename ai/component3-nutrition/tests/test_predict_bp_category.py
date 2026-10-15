"""Focused tests for reusable BP-associated model inference."""

import sys
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("xgboost")

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

import predict_bp_category as predictor  # noqa: E402
from train_selected_model import FEATURE_COLUMNS, LABEL_MAPPING  # noqa: E402


VALID_FEATURES = {
    "age": 58,
    "sex_female": 1,
    "bmi": 26.4,
    "sodium_mg_mean": 2200,
    "potassium_mg_mean": 3200,
    "energy_kcal_mean": 2000,
    "sat_fat_g_mean": 19.5,
    "na_k_ratio_mean": 0.6875,
}


def test_predict_returns_structured_experimental_result():
    result = predictor.predict_bp_category(VALID_FEATURES)

    assert result.predicted_class_id in LABEL_MAPPING.values()
    assert result.predicted_category in LABEL_MAPPING
    assert set(result.probabilities) == set(LABEL_MAPPING)
    assert all(np.isfinite(value) for value in result.probabilities.values())
    assert "experimental" in result.experimental_result.lower()
    assert "not a diagnosis" in result.experimental_result.lower()


def test_predict_uses_authoritative_feature_order(monkeypatch):
    captured = {}

    class StubModel:
        classes_ = np.array([0, 1, 2, 3])

        def predict(self, input_frame):
            captured["columns"] = list(input_frame.columns)
            return np.array([0])

        def predict_proba(self, input_frame):
            return np.array([[1.0, 0.0, 0.0, 0.0]])

    monkeypatch.setattr(predictor, "_MODEL", StubModel())
    predictor.predict_bp_category(dict(reversed(list(VALID_FEATURES.items()))))

    assert captured["columns"] == FEATURE_COLUMNS


def test_predict_maps_probabilities_using_model_classes(monkeypatch):
    class StubModel:
        classes_ = np.array([2, 0, 3, 1])

        def predict(self, input_frame):
            return np.array([2])

        def predict_proba(self, input_frame):
            return np.array([[0.1, 0.7, 0.15, 0.05]])

    monkeypatch.setattr(predictor, "_MODEL", StubModel())
    result = predictor.predict_bp_category(VALID_FEATURES)

    assert result.predicted_category == "Stage 1"
    assert result.probabilities == {
        "Stage 1": 0.1,
        "Normal": 0.7,
        "Stage 2": 0.15,
        "Elevated": 0.05,
    }


@pytest.mark.parametrize(
    "invalid_features",
    [
        {key: value for key, value in VALID_FEATURES.items() if key != "bmi"},
        {**VALID_FEATURES, "bmi": "26.4"},
        {**VALID_FEATURES, "bmi": np.nan},
        {**VALID_FEATURES, "bmi": np.inf},
        {**VALID_FEATURES, "bmi": -np.inf},
    ],
)
def test_predict_rejects_missing_non_numeric_and_non_finite_values(invalid_features):
    with pytest.raises(ValueError):
        predictor.predict_bp_category(invalid_features)


def test_predict_outputs_valid_class_and_probabilities():
    result = predictor.predict_bp_category(VALID_FEATURES)

    assert result.predicted_class_id in {0, 1, 2, 3}
    assert len(result.probabilities) == 4
    assert all(0.0 <= value <= 1.0 for value in result.probabilities.values())
    assert np.isclose(sum(result.probabilities.values()), 1.0)
