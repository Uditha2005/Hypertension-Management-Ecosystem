from fastapi.testclient import TestClient
import api

client = TestClient(api.app)

class DummyClient:
    pass

def test_food_alternatives_endpoint_returns_ranked_candidates(monkeypatch):
    api.app.dependency_overrides[api.get_usda_client] = lambda: DummyClient()
    monkeypatch.setattr(api, "find_food_alternatives", lambda client, fdc_id, quantity_unit, limit: {
        "fdc_id": fdc_id,
        "description": "Romaine lettuce",
        "missing_nutrients": ["potassium_mg"],
        "alternatives": [{
            "fdc_id": 2709590,
            "description": "Romaine lettuce, raw",
            "data_type": "Survey (FNDDS)",
            "serving_size": None,
            "serving_size_unit": None,
            "known_nutrients": ["sodium_mg", "potassium_mg", "energy_kcal", "sat_fat_g"],
            "fills_missing_nutrients": ["potassium_mg"],
            "similarity": 1.0,
            "reference_unit": "g",
            "reason": "Adds potassium_mg; confirm the food match.",
        }],
        "message": "Review and confirm the alternative.",
    })
    response = client.post("/foods/alternatives", json={"fdc_id": 373763, "quantity_unit": "g", "limit": 5})
    assert response.status_code == 200
    body = response.json()
    assert body["missing_nutrients"] == ["potassium_mg"]
    assert body["alternatives"][0]["fdc_id"] == 2709590
    api.app.dependency_overrides.clear()

def test_food_alternatives_endpoint_rejects_unsupported_unit():
    api.app.dependency_overrides[api.get_usda_client] = lambda: DummyClient()
    response = client.post("/foods/alternatives", json={"fdc_id": 373763, "quantity_unit": "cup", "limit": 5})
    assert response.status_code == 422
    api.app.dependency_overrides.clear()
