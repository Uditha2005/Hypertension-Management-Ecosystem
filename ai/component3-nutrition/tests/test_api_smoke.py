from pathlib import Path
import sys
SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))
from fastapi.testclient import TestClient
from api import app
client = TestClient(app)

def test_health_exposes_new_flow_and_research_models():
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["meal_assessment"] == "transparent_nutrient_reference_rules"
    assert "ml_research" in payload
    assert "daily_reference_alignment_proxy_model_available" in payload["ml_research"]

def test_daily_optimizer_route_is_registered():
    paths = {route.path for route in app.routes}
    assert "/dash/optimize-daily-pattern" in paths
