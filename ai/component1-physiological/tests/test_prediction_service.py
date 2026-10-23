
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "ai" / "component1-physiological" / "src"

sys.path.insert(0, str(SRC))

from prediction_service import assess_patient


@pytest.fixture
def sample_patient():
    return {
        "age": 68,
        "sex": "female",
        "systolic_bp": 142,
        "diastolic_bp": 84,
        "pulse_rate": 68,
        "height_cm": 158,
        "weight_kg": 82,
        "diabetes_history": False,
        "has_existing_hypertension": False,
    }


def test_valid_patient_returns_prediction_and_explanation(
    sample_patient,
):
    result = assess_patient(sample_patient)

    assert result["status"] == "research_prototype"
    assert 0 <= result["model_score_percent"] <= 100
    assert result["model_name"] == "Random Forest"
    assert result["shap_explanation"]["reconstruction_verified"]
    assert result["recommendations"]


def test_shap_contributions_reconstruct_probability(
    sample_patient,
):
    result = assess_patient(sample_patient)
    explanation = result["shap_explanation"]

    assert explanation["reconstruction_error"] < 1e-5


def test_existing_hypertension_uses_separate_pathway(
    sample_patient,
):
    sample_patient["has_existing_hypertension"] = True

    result = assess_patient(sample_patient)

    assert result["status"] == "existing_hypertension_pathway"
    assert result["model_score_percent"] is None
    assert "shap_explanation" not in result


def test_age_outside_training_range_is_rejected(
    sample_patient,
):
    sample_patient["age"] = 80

    with pytest.raises(ValueError, match="aged 60–74"):
        assess_patient(sample_patient)


def test_missing_existing_hypertension_status_is_rejected(
    sample_patient,
):
    del sample_patient["has_existing_hypertension"]

    with pytest.raises(ValueError, match="has_existing_hypertension"):
        assess_patient(sample_patient)


def test_baseline_bp_outside_cohort_eligibility_gets_no_score(
    sample_patient,
):
    sample_patient["systolic_bp"] = 165

    result = assess_patient(sample_patient)

    assert result["status"] == "outside_training_eligibility"
    assert result["model_score_percent"] is None
