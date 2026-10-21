"""End-to-end tests for planned-meal classifier integration."""

import sys
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("xgboost")

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

import predict_bp_category as predictor  # noqa: E402
from meal_plan_classifier_features import build_classifier_features  # noqa: E402
from meal_plan_nutrients import NutrientProfile  # noqa: E402
from meal_plan_service import PlannedFoodSelection, resolve_meal_plan  # noqa: E402
from predict_bp_category import BPCategoryPrediction  # noqa: E402
from train_selected_model import FEATURE_COLUMNS  # noqa: E402
from usda_fooddata import USDAFoodRecord  # noqa: E402


class FakeUSDAClient:
    def __init__(self, records):
        self.records = records
        self.calls = []

    def get_food(self, fdc_id):
        self.calls.append(fdc_id)
        return self.records[fdc_id]


def record(
    fdc_id,
    description,
    *,
    reference_quantity,
    reference_unit,
    sodium_mg,
    potassium_mg,
    energy_kcal,
    sat_fat_g,
):
    return USDAFoodRecord(
        fdc_id=fdc_id,
        description=description,
        data_type="Foundation",
        nutrients=NutrientProfile(
            sodium_mg=sodium_mg,
            potassium_mg=potassium_mg,
            energy_kcal=energy_kcal,
            sat_fat_g=sat_fat_g,
        ),
        reference_quantity=reference_quantity,
        reference_unit=reference_unit,
    )


def selection(fdc_id, day, quantity, unit):
    return PlannedFoodSelection(day=day, fdc_id=fdc_id, quantity=quantity, unit=unit)


def test_planned_meals_flow_through_features_into_structured_prediction(monkeypatch):
    client = FakeUSDAClient(
        {
            123: record(
                123,
                "Oats",
                reference_quantity=100,
                reference_unit="g",
                sodium_mg=100,
                potassium_mg=200,
                energy_kcal=300,
                sat_fat_g=4,
            ),
            456: record(
                456,
                "Soup",
                reference_quantity=1,
                reference_unit="serving",
                sodium_mg=500,
                potassium_mg=1000,
                energy_kcal=800,
                sat_fat_g=10,
            ),
        }
    )
    summary = resolve_meal_plan(
        [
            selection(123, "2026-10-12", 200, "g"),
            selection(456, "2026-10-13", 2, "servings"),
        ],
        client,
    )

    captured = {}

    class StubModel:
        classes_ = np.array([0, 1, 2, 3])

        def predict(self, input_frame):
            captured["columns"] = list(input_frame.columns)
            captured["values"] = input_frame.iloc[0].tolist()
            return np.array([2])

        def predict_proba(self, input_frame):
            return np.array([[0.1, 0.2, 0.6, 0.1]])

    monkeypatch.setattr(predictor, "_MODEL", StubModel())
    features = build_classifier_features(
        summary,
        age=68,
        sex_female=1,
        bmi=26.4,
        selected_days=["2026-10-12"],
    )
    result = predictor.predict_bp_category(features)

    assert client.calls == [123, 456]
    assert features == {
        "age": 68.0,
        "sex_female": 1.0,
        "bmi": 26.4,
        "sodium_mg_mean": 200.0,
        "potassium_mg_mean": 400.0,
        "energy_kcal_mean": 600.0,
        "sat_fat_g_mean": 8.0,
        "na_k_ratio_mean": 0.5,
    }
    assert summary.total.sodium_mg == 1200
    assert captured["columns"] == FEATURE_COLUMNS
    assert captured["values"] == [features[column] for column in FEATURE_COLUMNS]
    assert isinstance(result, BPCategoryPrediction)
    assert result.predicted_class_id == 2
    assert result.predicted_category == "Stage 1"
    assert result.probabilities == {
        "Normal": 0.1,
        "Elevated": 0.2,
        "Stage 1": 0.6,
        "Stage 2": 0.1,
    }
    assert "experimental" in result.experimental_result.lower()
    assert "not a diagnosis" in result.experimental_result.lower()


def test_missing_resolved_nutrient_is_rejected_before_prediction():
    client = FakeUSDAClient(
        {
            123: record(
                123,
                "Incomplete oats",
                reference_quantity=100,
                reference_unit="g",
                sodium_mg=None,
                potassium_mg=200,
                energy_kcal=300,
                sat_fat_g=4,
            )
        }
    )
    summary = resolve_meal_plan([selection(123, "2026-10-12", 200, "g")], client)

    with pytest.raises(ValueError, match="unknown nutrient: sodium_mg"):
        build_classifier_features(
            summary,
            age=68,
            sex_female=1,
            bmi=26.4,
            selected_days=["2026-10-12"],
        )
