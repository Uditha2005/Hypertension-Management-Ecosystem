"""Integration checks for the trained DASH next-day preference model."""
from pathlib import Path

import joblib
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DASH_ROOT = ROOT / "research" / "dash_servings"
ARTIFACT = DASH_ROOT / "models" / "dash_next_day_preference_ridge.joblib"


def _sample_feature_frame(bundle):
    # Representative non-empty day profile in the model's declared input schema.
    return pd.DataFrame(
        [[0.0 if i % 3 else 0.5 for i in range(len(bundle["feature_columns"]))]],
        columns=bundle["feature_columns"],
    )


def test_trained_model_artifact_has_complete_schema_and_expected_metadata():
    assert ARTIFACT.is_file(), f"Missing trained model artifact: {ARTIFACT}"
    bundle = joblib.load(ARTIFACT)

    assert bundle["selected_model"] == "Ridge"
    assert bundle["blend_weight"] == 0.30
    assert len(bundle["feature_columns"]) == 50
    assert len(bundle["target_columns"]) == 50
    assert len(set(bundle["feature_columns"])) == 50
    assert len(set(bundle["target_columns"])) == 50
    assert all(name.startswith("food_") for name in bundle["feature_columns"])
    assert all(name.startswith("food_") for name in bundle["target_columns"])
    assert bundle["model"] is not None
    assert "day 2" in bundle["target_definition"].lower() and "day 1" in bundle["target_definition"].lower()
    assert "NHANES" in bundle["dataset"]


def test_saved_model_can_run_inference_with_declared_features():
    bundle = joblib.load(ARTIFACT)
    features = _sample_feature_frame(bundle)

    prediction = np.asarray(bundle["model"].predict(features), dtype=float)

    assert prediction.shape == (1, len(bundle["target_columns"]))
    assert np.isfinite(prediction).all()
    # The integration clips negative regression predictions to zero; the raw
    # estimator is allowed to predict below zero, so do not assert raw >= 0.


def test_live_daily_optimizer_uses_model_and_returns_auditable_output():
    from dash_recommendation import optimize_daily_food_entries

    result = optimize_daily_food_entries([
        {"food_name": "Rice, white, cooked", "quantity_grams": 200},
        {"food_name": "Chicken, roasted", "quantity_grams": 150},
        {"food_name": "Spinach, cooked", "quantity_grams": 80},
        {"food_name": "Orange juice", "quantity_grams": 200},
    ])

    assert result["status"] in {
        "optimal", "solver_or_residual_warning", "infeasible_constraints"
    }
    assert result["ml_preference_model"]["used"] is True
    assert result["ml_preference_model"]["model"] == "Ridge multi-output regression"
    assert result["ml_preference_model"]["blend_weight"] == 0.30
    assert result["ml_preference_model"]["prediction_target"] == "next-day observed food-group servings"
    assert "clinically validated" in result["ml_preference_model"]["warning"]
    assert "not a healthiness classifier" in result["ml_preference_model"]["warning"]
    assert result["matched_foods"]
    assert result["servings_before"]
    assert result["servings_after"]
    assert "optimizer_diagnostics" in result
    assert "limitations" in result


def test_optimizer_falls_back_safely_when_model_artifact_is_unavailable(monkeypatch, tmp_path):
    import dash_recommendation

    # Redirect only the model lookup; nutrient matrices remain the real project data.
    monkeypatch.setattr(dash_recommendation, "DASH_ROOT", tmp_path)
    result = dash_recommendation.optimize_daily_food_entries([
        {"food_name": "Rice, white, cooked", "quantity_grams": 200},
        {"food_name": "Chicken, roasted", "quantity_grams": 150},
    ])

    assert result["status"] in {
        "optimal", "solver_or_residual_warning", "infeasible_constraints"
    }
    assert result["ml_preference_model"]["used"] is False
    assert result["matched_foods"]
    assert result["servings_before"]
    assert result["servings_after"]
