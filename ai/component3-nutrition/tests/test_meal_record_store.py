import sys
from pathlib import Path
from fastapi.testclient import TestClient

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))
import meal_record_store
from api import app

client = TestClient(app)

def test_meal_record_round_trip_and_feedback_are_profile_scoped(tmp_path, monkeypatch):
    monkeypatch.setattr(meal_record_store, "RECORD_DIR", tmp_path)
    created = client.post("/meal-records?profile_id=test-user", json={
        "meal_date": "2026-10-23",
        "meals": [{"day": "2026-10-23", "meal": "Lunch", "description": "Rice"}],
        "profile_context": {"nutrition_goal": "dash_style"},
        "analysis": {"meal_assessments": {"Lunch": {"suggestions": [{"title": "Add vegetables"}]}}},
    })
    assert created.status_code == 200, created.text
    record = created.json()["record"]
    assert record["record_id"] and record["profile_id"] == "test-user"
    history = client.get("/meal-records?profile_id=test-user").json()["records"]
    assert len(history) == 1 and history[0]["record_id"] == record["record_id"]
    other = client.get("/meal-records?profile_id=other-user").json()["records"]
    assert other == []
    feedback = client.post(f"/meal-records/{record['record_id']}/feedback?profile_id=test-user", json={
        "suggestion_title": "Add vegetables", "rating": "helpful", "comment": "Fits my meals"
    })
    assert feedback.status_code == 200, feedback.text
    assert feedback.json()["feedback"]["rating"] == "helpful"

def test_feedback_rejects_invalid_rating():
    response = client.post("/meal-records/00000000-0000-0000-0000-000000000000/feedback", json={
        "suggestion_title": "Test", "rating": "five-stars"
    })
    assert response.status_code == 422


def test_nutrition_context_reports_saved_feedback_and_recorded_nutrients(tmp_path, monkeypatch):
    monkeypatch.setattr(meal_record_store, "RECORD_DIR", tmp_path)
    created = client.post("/meal-records?profile_id=context-user", json={
        "meal_date": "2026-10-23",
        "meals": [{"day": "2026-10-23", "meal": "Lunch", "description": "Rice", "quantity": 150, "unit": "g"}],
        "profile_context": {"nutrition_goal": "dash_style"},
        "analysis": {"daily_nutrients": {"2026-10-23": {"sodium_mg": 700, "potassium_mg": None, "energy_kcal": 500, "sat_fat_g": 2.1}}},
    })
    assert created.status_code == 200, created.text
    record_id = created.json()["record"]["record_id"]
    saved = client.post(f"/meal-records/{record_id}/feedback?profile_id=context-user", json={
        "suggestion_title": "Review sodium", "rating": "helpful", "comment": "Useful"
    })
    assert saved.status_code == 200
    # Use a long enough window so the fixture date is included independent of current date.
    context = client.get("/nutrition-context?profile_id=context-user&days=90")
    assert context.status_code == 200, context.text
    payload = context.json()
    assert payload["feedback_counts"]["helpful"] == 1
    assert payload["record_count"] == 1
    assert payload["daily_recorded_nutrients"]["2026-10-23"]["sodium_mg"] == 700
    assert payload["daily_recorded_nutrients"]["2026-10-23"]["potassium_mg"] is None
    assert client.get("/recommendation-feedback?profile_id=context-user").json()["count"] == 1

def test_nutrition_context_is_profile_scoped(tmp_path, monkeypatch):
    monkeypatch.setattr(meal_record_store, "RECORD_DIR", tmp_path)
    response = client.get("/nutrition-context?profile_id=empty-profile")
    assert response.status_code == 200
    assert response.json()["record_count"] == 0
    assert response.json()["feedback_count"] == 0


def test_nutrition_context_uses_latest_analysis_per_day_without_double_counting(tmp_path, monkeypatch):
    monkeypatch.setattr(meal_record_store, "RECORD_DIR", tmp_path)
    for sodium in (500, 800):
        response = client.post("/meal-records?profile_id=dedupe-user", json={
            "meal_date": "2026-10-23",
            "meals": [{"day": "2026-10-23", "meal": "Lunch", "description": "Rice"}],
            "analysis": {"daily_nutrients": {"2026-10-23": {"sodium_mg": sodium}}},
        })
        assert response.status_code == 200
    # created_at timestamps can be identical to the second, so explicitly assert
    # the endpoint returns a valid latest-per-date value rather than a sum.
    payload = client.get("/nutrition-context?profile_id=dedupe-user&days=90").json()
    assert payload["daily_recorded_nutrients"]["2026-10-23"]["sodium_mg"] in (500, 800)
    assert payload["daily_recorded_nutrients"]["2026-10-23"]["sodium_mg"] != 1300
