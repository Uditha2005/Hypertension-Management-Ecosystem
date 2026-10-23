
from pathlib import Path
import sys
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import api
from meal_plan_service import MealPlanValidationError
from usda_fooddata import USDAConfigurationError, USDARequestError


client = TestClient(api.app)


def valid_payload():
    return {
        "entries": [
            {
                "day": "2026-10-23",
                "fdc_id": 123,
                "quantity": 100,
                "unit": "g",
                "meal": "Lunch",
            }
        ],
        "selected_days": ["2026-10-23"],
        "personal_profile": {
            "age_years": 55,
            "bmi": 25,
            "sex_code": 1,
            "dietary_requirements": [],
        },
        "full_day_intake": False,
    }


def test_rejects_invalid_selected_date():
    payload = valid_payload()
    payload["selected_days"] = ["2026-02-30"]

    response = client.post("/meal-plans/analyze", json=payload)

    assert response.status_code == 422


def test_rejects_duplicate_selected_days():
    payload = valid_payload()
    payload["selected_days"] = ["2026-10-23", "2026-10-23"]

    response = client.post("/meal-plans/analyze", json=payload)

    assert response.status_code == 422
    assert "duplicates" in response.text


def test_rejects_entry_outside_selected_days():
    payload = valid_payload()
    payload["entries"][0]["day"] = "2026-10-24"

    response = client.post("/meal-plans/analyze", json=payload)

    assert response.status_code == 422
    assert "not in selected_days" in response.text


def test_rejects_missing_personal_profile():
    payload = valid_payload()
    payload.pop("personal_profile")

    response = client.post("/meal-plans/analyze", json=payload)

    assert response.status_code == 422


def test_usda_configuration_error_returns_503():
    payload = valid_payload()

    with patch.object(
        api,
        "resolve_meal_plan",
        side_effect=USDAConfigurationError("missing key"),
    ):
        response = client.post("/meal-plans/analyze", json=payload)

    assert response.status_code == 503


def test_usda_request_error_returns_502():
    payload = valid_payload()

    with patch.object(
        api,
        "resolve_meal_plan",
        side_effect=USDARequestError("upstream failure"),
    ):
        response = client.post("/meal-plans/analyze", json=payload)

    assert response.status_code == 502
