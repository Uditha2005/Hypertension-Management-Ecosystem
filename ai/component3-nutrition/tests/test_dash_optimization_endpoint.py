from fastapi.testclient import TestClient
import api

def test_dash_daily_pattern_endpoint_runs():
    client=TestClient(api.app)
    response=client.post('/dash/optimize-daily-pattern',json={
        'age_years':55,'sex_code':1,'self_reported_hypertension':True})
    assert response.status_code == 200, response.text
    data=response.json()
    assert data['target_definition'].startswith('Average observed servings')
    assert data['status'] in {'ok','solver_or_residual_warning','infeasible_constraints'}
    assert 'does not predict whether an individual meal is suitable' in data['limitation']


def test_missing_dash_model_returns_503(monkeypatch):
    from pathlib import Path

    monkeypatch.setattr(api, "DASH_MODEL", Path("/tmp/nonexistent_dash_model.joblib"))

    client = TestClient(api.app)
    response = client.post(
        "/dash/optimize-daily-pattern",
        json={
            "age_years": 55,
            "sex_code": 1,
            "self_reported_hypertension": True,
        },
    )

    assert response.status_code == 503
    assert "model is not trained" in response.json()["detail"]


def test_missing_dash_constraint_files_returns_503(monkeypatch, tmp_path):
    monkeypatch.setattr(api, "DASH_RESULTS", tmp_path)

    # Keep the model available so the endpoint reaches the constraint-file check.
    monkeypatch.setattr(api, "DASH_MODEL", tmp_path / "placeholder_model.joblib")
    (tmp_path / "placeholder_model.joblib").touch()

    class FakeModel:
        def predict(self, features):
            import numpy as np
            return np.array([[1.0, 2.0]])

    import joblib
    monkeypatch.setattr(joblib, "load", lambda path: FakeModel())

    client = TestClient(api.app)
    response = client.post(
        "/dash/optimize-daily-pattern",
        json={
            "age_years": 55,
            "sex_code": 1,
            "self_reported_hypertension": True,
        },
    )

    assert response.status_code == 503
    assert "constraint parameter files are missing" in response.json()["detail"]
