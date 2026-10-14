"""Mocked tests for the USDA FoodData Central adapter."""

import sys
from pathlib import Path

import pytest
import requests

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from usda_fooddata import (  # noqa: E402
    USDAConfigurationError,
    USDAEmptySearchError,
    USDAFoodDataClient,
    USDARequestError,
    USDAResponseError,
    USDAUnsupportedUnitError,
)


class FakeResponse:
    def __init__(self, payload=None, status_code=200, json_error=False):
        self.payload = payload
        self.status_code = status_code
        self.json_error = json_error

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)

    def json(self):
        if self.json_error:
            raise ValueError("invalid json")
        return self.payload


class FakeSession:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def get(self, url, *, params, timeout):
        self.calls.append((url, params, timeout))
        if self.error:
            raise self.error
        return self.response


def client(session, monkeypatch, api_key="test-key"):
    monkeypatch.setenv("USDA_FDC_API_KEY", api_key)
    return USDAFoodDataClient(session=session, base_url="https://example.test/fdc", timeout=3)


def per_100g_payload(**overrides):
    payload = {
        "fdcId": 123,
        "description": "Sample oats",
        "dataType": "Foundation",
        "foodNutrients": [
            {"nutrientId": 1093, "nutrientName": "Sodium, Na", "unitName": "mg", "value": 120},
            {"nutrientId": 1092, "nutrientName": "Potassium, K", "unitName": "mg", "value": 340},
            {"nutrientId": 1008, "nutrientName": "Energy", "unitName": "kcal", "value": 250},
            {"nutrientId": 1258, "nutrientName": "Fatty acids, total saturated", "unitName": "g", "value": 2.5},
        ],
    }
    payload.update(overrides)
    return payload


def test_search_maps_multiple_candidates_and_request_parameters(monkeypatch):
    session = FakeSession(
        FakeResponse(
            {
                "foods": [
                    {"fdcId": 123, "description": "Oats", "dataType": "Foundation", "servingSize": 40, "servingSizeUnit": "g"},
                    {"fdcId": 456, "description": "Oat cereal", "dataType": "Branded"},
                ]
            }
        )
    )
    api = client(session, monkeypatch)

    results = api.search_foods("oats")

    assert [(result.fdc_id, result.description) for result in results] == [(123, "Oats"), (456, "Oat cereal")]
    assert results[0].serving_size == 40
    assert results[0].serving_size_unit == "g"
    assert session.calls[0][0].endswith("/v1/foods/search")
    assert session.calls[0][1]["query"] == "oats"
    assert session.calls[0][1]["api_key"] == "test-key"
    assert session.calls[0][2] == 3.0


def test_get_food_uses_explicit_id_and_preserves_per_100g_reference(monkeypatch):
    session = FakeSession(FakeResponse(per_100g_payload()))
    api = client(session, monkeypatch)

    record = api.get_food(123)

    assert session.calls[0][0].endswith("/v1/food/123")
    assert record.fdc_id == 123
    assert record.reference_quantity == 100
    assert record.reference_unit == "g"
    assert record.serving_size is None
    assert record.serving_size_unit is None
    assert record.nutrients.sodium_mg == 120
    assert record.nutrients.potassium_mg == 340
    assert record.nutrients.energy_kcal == 250
    assert record.nutrients.sat_fat_g == 2.5


def test_get_food_parses_serving_values_without_guessing_mass(monkeypatch):
    session = FakeSession(
        FakeResponse(
            {
                "fdcId": 123,
                "description": "Branded soup",
                "dataType": "Branded",
                "servingSize": 240,
                "servingSizeUnit": "ml",
                "labelNutrients": {
                    "sodium": {"value": 500},
                    "potassium": {"value": 200},
                    "calories": {"value": 180},
                    "saturatedFat": {"value": 3},
                },
            }
        )
    )
    record = client(session, monkeypatch).get_food(123)

    assert (record.reference_quantity, record.reference_unit) == (1, "serving")
    assert (record.serving_size, record.serving_size_unit) == (240, "ml")
    assert record.nutrients.sodium_mg == 500
    assert record.nutrients.energy_kcal == 180


def test_supported_energy_and_saturated_fat_conversions(monkeypatch):
    payload = per_100g_payload()
    payload["foodNutrients"][2].update({"nutrientId": 1062, "unitName": "kJ", "value": 418.4})
    payload["foodNutrients"][3].update({"unitName": "mg", "value": 2500})
    record = client(FakeSession(FakeResponse(payload)), monkeypatch).get_food(123)

    assert record.nutrients.energy_kcal == pytest.approx(100)
    assert record.nutrients.sat_fat_g == pytest.approx(2.5)


def test_missing_individual_nutrients_remain_none(monkeypatch):
    payload = per_100g_payload(foodNutrients=[{"nutrientId": 1093, "unitName": "mg", "value": 10}])
    record = client(FakeSession(FakeResponse(payload)), monkeypatch).get_food(123)

    assert record.nutrients.sodium_mg == 10
    assert record.nutrients.potassium_mg is None
    assert record.nutrients.energy_kcal is None
    assert record.nutrients.sat_fat_g is None


def test_missing_api_key_is_rejected(monkeypatch):
    monkeypatch.delenv("USDA_FDC_API_KEY", raising=False)

    with pytest.raises(USDAConfigurationError, match="missing or blank"):
        USDAFoodDataClient(session=FakeSession())


def test_empty_search_results_are_rejected(monkeypatch):
    api = client(FakeSession(FakeResponse({"foods": []})), monkeypatch)

    with pytest.raises(USDAEmptySearchError):
        api.search_foods("unknown food")


@pytest.mark.parametrize("payload", [None, {"foods": {}}, {"foods": [{"fdcId": 1}]}])
def test_malformed_search_responses_are_rejected(payload, monkeypatch):
    api = client(FakeSession(FakeResponse(payload)), monkeypatch)

    with pytest.raises(USDAResponseError):
        api.search_foods("oats")


def test_invalid_json_is_rejected(monkeypatch):
    api = client(FakeSession(FakeResponse(json_error=True)), monkeypatch)

    with pytest.raises(USDAResponseError, match="valid JSON"):
        api.search_foods("oats")


@pytest.mark.parametrize("error", [requests.Timeout(), requests.ConnectionError()])
def test_timeout_and_connection_errors_are_wrapped(error, monkeypatch):
    api = client(FakeSession(error=error), monkeypatch)

    with pytest.raises(USDARequestError):
        api.search_foods("oats")


def test_http_error_is_wrapped_without_exposing_api_key(monkeypatch):
    session = FakeSession(FakeResponse(status_code=403))
    api = client(session, monkeypatch, api_key="secret-value")

    with pytest.raises(USDARequestError) as raised:
        api.search_foods("oats")

    assert "secret-value" not in str(raised.value)


@pytest.mark.parametrize("fdc_id", [0, -1, "", "abc", True])
def test_invalid_food_ids_are_rejected_before_request(fdc_id, monkeypatch):
    session = FakeSession(FakeResponse(per_100g_payload()))
    api = client(session, monkeypatch)

    with pytest.raises(USDAResponseError):
        api.get_food(fdc_id)
    assert session.calls == []


def test_unsupported_nutrient_unit_is_rejected(monkeypatch):
    payload = per_100g_payload()
    payload["foodNutrients"][0]["unitName"] = "g"

    with pytest.raises(USDAUnsupportedUnitError):
        client(FakeSession(FakeResponse(payload)), monkeypatch).get_food(123)


def test_ambiguous_reference_basis_is_rejected(monkeypatch):
    payload = per_100g_payload(dataType="Branded")

    with pytest.raises(USDAResponseError, match="reference basis"):
        client(FakeSession(FakeResponse(payload)), monkeypatch).get_food(123)


def test_malformed_food_response_is_rejected(monkeypatch):
    payload = per_100g_payload(fdcId=456)

    with pytest.raises(USDAResponseError, match="did not match"):
        client(FakeSession(FakeResponse(payload)), monkeypatch).get_food(123)