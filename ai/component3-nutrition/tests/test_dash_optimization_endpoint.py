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
