from pathlib import Path
import sys

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from fastapi.testclient import TestClient
from api import app

client = TestClient(app)


def test_health_exposes_current_component3_status():
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()

    assert payload["status"] == "ok"
    assert payload["service"] == "component3-nutrition-api"
    assert "photo_food_identification_available" in payload
    assert isinstance(payload["photo_food_identification_available"], bool)
    assert "daily_dash_optimizer_available" in payload
    assert isinstance(payload["daily_dash_optimizer_available"], bool)
    assert "recommendation_engine" in payload
    assert isinstance(payload["recommendation_engine"], dict)


def test_daily_optimizer_route_is_registered():
    paths = {route.path for route in app.routes}
    assert "/dash/optimize-current-day" in paths


def test_profile_routes_support_browser_put_cors():
    response = client.options(
        "/profile",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert "PUT" in response.headers.get("access-control-allow-methods", "")
