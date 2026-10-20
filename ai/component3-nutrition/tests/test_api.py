"""Deterministic tests for the Component 3 FastAPI layer."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest
from fastapi.testclient import TestClient

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# The production repository contains train_selected_model.py. The uploaded source
# bundle used for isolated review may omit it, so provide only its interface when
# absent; the real project module always takes precedence.
if importlib.util.find_spec("train_selected_model") is None:
    training_stub = ModuleType("train_selected_model")
    training_stub.FEATURE_COLUMNS = [
        "age", "sex_female", "bmi", "sodium_mg_mean", "potassium_mg_mean",
        "energy_kcal_mean", "sat_fat_g_mean", "na_k_ratio_mean",
    ]
    training_stub.LABEL_MAPPING = {"Normal": 0, "Elevated": 1, "Stage 1": 2, "Stage 2": 3}
    training_stub.MODEL_PATH = SRC / "selected_model.json"
    sys.modules["train_selected_model"] = training_stub

import api  # noqa: E402
USDA_DEPENDENCY = api.get_usda_client
from meal_plan_nutrients import NutrientProfile  # noqa: E402
from predict_bp_category import BPCategoryPrediction  # noqa: E402
from usda_fooddata import (  # noqa: E402
    FoodSearchResult,
    USDAConfigurationError,
    USDAFoodDataError,
    USDAFoodRecord,
    USDARequestError,
)


class FakeUSDAClient:
    def __init__(self):
        self.calls: list[int] = []
        self.records = {
            101: USDAFoodRecord(
                fdc_id=101,
                description="Test oats",
                data_type="Foundation",
                nutrients=NutrientProfile(
                    reference_quantity=100,
                    sodium_mg=100,
                    potassium_mg=300,
                    energy_kcal=380,
                    sat_fat_g=2,
                ),
                reference_quantity=100,
                reference_unit="g",
            ),
            202: USDAFoodRecord(
                fdc_id=202,
                description="Test cereal serving",
                data_type="Branded",
                nutrients=NutrientProfile(
                    reference_quantity=1,
                    sodium_mg=250,
                    potassium_mg=100,
                    energy_kcal=150,
                    sat_fat_g=1,
                ),
                reference_quantity=1,
                reference_unit="serving",
                serving_size=40,
                serving_size_unit="g",
            ),
        }

    def search_foods(self, query: str, *, page_size: int = 25):
        return [FoodSearchResult(101, "Test oats", "Foundation", None, None)][:page_size]

    def get_food(self, fdc_id: int):
        self.calls.append(int(fdc_id))
        if int(fdc_id) not in self.records:
            raise USDAFoodDataError("not found")
        return self.records[int(fdc_id)]


@pytest.fixture
def client(monkeypatch):
    fake = FakeUSDAClient()
    api.app.dependency_overrides[USDA_DEPENDENCY] = lambda: fake
    monkeypatch.setattr(api, "predict_bp_category", lambda features: BPCategoryPrediction(
        predicted_class_id=0,
        predicted_category="Normal",
        probabilities={"Normal": 0.7, "Elevated": 0.1, "Stage 1": 0.1, "Stage 2": 0.1},
    ))
    test_client = TestClient(api.app)
    yield test_client, fake
    api.app.dependency_overrides.clear()


def valid_payload():
    return {
        "entries": [
            {"day": "2026-10-12", "fdc_id": 101, "quantity": 200, "unit": "g"},
            {"day": "2026-10-13", "fdc_id": 202, "quantity": 2, "unit": "serving"},
        ],
        "selected_days": ["2026-10-12", "2026-10-13"],
        "age": 58,
        "sex_female": 1,
        "bmi": 26.4,
    }


def test_health_endpoint_does_not_need_usda_or_model(client):
    test_client, _ = client
    response = test_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_food_search_returns_candidates_without_implicit_selection(client):
    test_client, _ = client
    response = test_client.get("/foods/search", params={"query": "oats", "limit": 5})
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["foods"][0]["fdc_id"] == 101


def test_food_search_rejects_blank_query(client):
    test_client, _ = client
    response = test_client.get("/foods/search", params={"query": "   "})
    assert response.status_code == 422


def test_analysis_resolves_foods_builds_features_and_returns_prediction(client, monkeypatch):
    test_client, fake = client
    captured = {}

    def predict(features):
        captured["features"] = dict(features)
        return BPCategoryPrediction(
            predicted_class_id=0,
            predicted_category="Normal",
            probabilities={"Normal": 0.7, "Elevated": 0.1, "Stage 1": 0.1, "Stage 2": 0.1},
        )

    monkeypatch.setattr(api, "predict_bp_category", predict)
    response = test_client.post("/meal-plans/analyze", json=valid_payload())
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["selected_days"] == ["2026-10-12", "2026-10-13"]
    assert body["daily_nutrients"]["2026-10-12"]["sodium_mg"] == pytest.approx(200)
    assert body["daily_nutrients"]["2026-10-13"]["sodium_mg"] == pytest.approx(500)
    assert body["classifier_features"]["sodium_mg_mean"] == pytest.approx(350)
    assert body["classifier_features"]["potassium_mg_mean"] == pytest.approx(400)
    assert body["classifier_features"]["energy_kcal_mean"] == pytest.approx(530)
    assert list(captured["features"]) == [
        "age", "sex_female", "bmi", "sodium_mg_mean", "potassium_mg_mean",
        "energy_kcal_mean", "sat_fat_g_mean", "na_k_ratio_mean",
    ]
    assert body["prediction"]["predicted_category"] == "Normal"
    assert "not a diagnosis" in body["prediction"]["experimental_result"]
    assert "not been clinically validated" in body["limitation"]
    assert fake.calls == [101, 202]


def test_analysis_uses_only_selected_days_not_period_total(client):
    test_client, _ = client
    payload = valid_payload()
    payload["selected_days"] = ["2026-10-12"]
    response = test_client.post("/meal-plans/analyze", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["classifier_features"]["sodium_mg_mean"] == pytest.approx(200)
    assert body["complete_plan_total"]["sodium_mg"] == pytest.approx(700)



def test_analysis_returns_nutrients_when_classifier_nutrient_is_unknown(client, monkeypatch):
    test_client, fake = client
    record = fake.records[101]
    fake.records[101] = USDAFoodRecord(
        fdc_id=record.fdc_id,
        description=record.description,
        data_type=record.data_type,
        nutrients=NutrientProfile(
            reference_quantity=100,
            sodium_mg=100,
            potassium_mg=None,
            energy_kcal=380,
            sat_fat_g=2,
        ),
        reference_quantity=100,
        reference_unit="g",
    )

    def forbidden_prediction(features):
        raise AssertionError("prediction must not run with unknown nutrients")

    monkeypatch.setattr(api, "predict_bp_category", forbidden_prediction)
    response = test_client.post("/meal-plans/analyze", json=valid_payload())

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["complete_plan_total"]["potassium_mg"] is None
    assert body["complete_plan_total"]["na_k_ratio"] is None
    assert body["prediction"] is None
    assert body["classifier_features"] is None
    assert "unknown nutrient: potassium_mg" in body["classifier_unavailable_reason"]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload.update({"selected_days": []}),
        lambda payload: payload.update({"age": 17}),
        lambda payload: payload.update({"sex_female": 2}),
        lambda payload: payload.update({"bmi": 0}),
        lambda payload: payload["entries"][0].update({"quantity": -1}),
        lambda payload: payload["entries"][0].update({"unit": "cup"}),
        lambda payload: payload["entries"][0].update({"day": "2026-02-30"}),
        lambda payload: payload.update({"selected_days": ["2026-10-12", "2026-10-12"]}),
    ],
)
def test_analysis_rejects_invalid_inputs(client, mutate):
    test_client, _ = client
    payload = valid_payload()
    mutate(payload)
    response = test_client.post("/meal-plans/analyze", json=payload)
    assert response.status_code == 422


def test_usda_upstream_request_error_returns_gateway_error(client, monkeypatch):
    def fail_search(*args, **kwargs):
        raise USDARequestError("private upstream details")

    test_client, fake = client
    monkeypatch.setattr(fake, "search_foods", fail_search)
    response = test_client.get("/foods/search", params={"query": "oats"})
    assert response.status_code == 502
    assert "private upstream details" not in response.text


def test_missing_usda_configuration_returns_service_unavailable(client, monkeypatch):
    test_client, _ = client
    api.app.dependency_overrides[USDA_DEPENDENCY] = lambda: (_ for _ in ()).throw(USDAConfigurationError("missing key"))
    response = test_client.get("/foods/search", params={"query": "oats"})
    assert response.status_code == 503
    assert "missing key" not in response.text


def test_analysis_rejects_missing_required_fields(client):
    test_client, _ = client
    response = test_client.post("/meal-plans/analyze", json={"entries": []})
    assert response.status_code == 422


@pytest.mark.parametrize(
    "field,value",
    [("sex_female", True), ("age", True), ("bmi", True)],
)
def test_analysis_rejects_boolean_demographics(client, field, value):
    test_client, _ = client
    payload = valid_payload()
    payload[field] = value
    response = test_client.post("/meal-plans/analyze", json=payload)
    assert response.status_code == 422


def test_analysis_rejects_boolean_quantity(client):
    test_client, _ = client
    payload = valid_payload()
    payload["entries"][0]["quantity"] = True
    response = test_client.post("/meal-plans/analyze", json=payload)
    assert response.status_code == 422
