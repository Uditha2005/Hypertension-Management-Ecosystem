"""End-to-end checks across the Component 3 API, trained model, and DASH optimizer."""
from pathlib import Path
import sys

from fastapi.testclient import TestClient

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from api import app  # noqa: E402


client = TestClient(app)


def test_end_to_end_daily_food_request_runs_trained_model_and_optimizer():
    response = client.post(
        "/dash/optimize-current-day",
        json={
            "items": [
                {"food_name": "Rice, white, cooked", "quantity_grams": 180},
                {"food_name": "Chicken, roasted", "quantity_grams": 120},
                {"food_name": "Spinach, cooked", "quantity_grams": 60},
                {"food_name": "Orange juice", "quantity_grams": 240},
            ]
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()

    assert body["status"] in {
        "optimal", "solver_or_residual_warning", "infeasible_constraints"
    }
    assert body["matched_foods"]
    assert body["unmatched_foods"] == []
    assert body["ml_preference_model"]["used"] is True
    assert body["ml_preference_model"]["model"] == "Ridge multi-output regression"
    assert body["ml_preference_model"]["blend_weight"] == 0.30
    assert body["ml_preference_model"]["prediction_target"] == "next-day observed food-group servings"
    assert body["servings_before"]
    assert body["servings_after"]
    assert isinstance(body["changes"], list)
    assert isinstance(body["nutrient_totals"], dict)
    assert isinstance(body["constraint_bounds"], dict)
    assert isinstance(body["optimizer_diagnostics"], dict)
    assert body["limitations"]


def test_end_to_end_unknown_food_is_rejected_with_mapping_diagnostics():
    response = client.post(
        "/dash/optimize-current-day",
        json={"items": [{"food_name": "Unclassified regional mixed dish", "quantity_grams": 200}]},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "unmatched_foods" in detail
    assert detail["unmatched_foods"][0]["food_name"] == "Unclassified regional mixed dish"


def test_end_to_end_invalid_quantity_is_rejected_before_optimization():
    response = client.post(
        "/dash/optimize-current-day",
        json={"items": [{"food_name": "Rice", "quantity_grams": 0}]},
    )

    assert response.status_code == 422
