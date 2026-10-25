from fastapi.testclient import TestClient
import api

client = TestClient(api.app)

def test_photo_identification_requires_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    response = client.post("/foods/identify-image", json={
        "image_data_url": "data:image/png;base64," + ("A" * 120),
        "meal_context": "Lunch",
    })
    assert response.status_code == 503
    assert "GEMINI_API_KEY" in response.json()["detail"]

def test_photo_identification_rejects_unsupported_data_url(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    response = client.post("/foods/identify-image", json={
        "image_data_url": "data:image/gif;base64," + ("A" * 120),
        "meal_context": "Lunch",
    })
    assert response.status_code == 422
    assert "JPG, PNG, or WEBP" in response.json()["detail"]

def test_photo_identification_returns_editable_food_suggestions(monkeypatch):
    import base64
    import requests

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    class FakeResponse:
        def raise_for_status(self):
            return None
        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": '{"foods":[{"food_name":"cooked rice","estimated_quantity_g":180,"confidence":"medium","notes":"Portion is approximate"}]}'}]}}]}

    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: FakeResponse())
    image = "data:image/png;base64," + base64.b64encode(b"fake-image-bytes" * 20).decode("ascii")
    response = client.post("/foods/identify-image", json={"image_data_url": image, "meal_context": "Lunch"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["foods"][0]["food_name"] == "cooked rice"
    assert payload["foods"][0]["estimated_quantity_g"] == 180
    assert "confirm" in payload["limitation"].lower()
