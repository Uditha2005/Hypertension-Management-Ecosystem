"""Input validation tests for the daily DASH optimizer API."""
from fastapi.testclient import TestClient
import api


client = TestClient(api.app)


def test_current_day_optimizer_reports_unmapped_foods():
    response = client.post("/dash/optimize-current-day", json={"items": [
        {"food_name": "Unclassified mixed dish", "quantity_grams": 200}
    ]})
    assert response.status_code == 422
    assert "unmatched_foods" in response.json()["detail"]


def test_current_day_optimizer_rejects_invalid_quantity():
    response = client.post("/dash/optimize-current-day", json={"items": [
        {"food_name": "Rice", "quantity_grams": 0}
    ]})
    assert response.status_code == 422
