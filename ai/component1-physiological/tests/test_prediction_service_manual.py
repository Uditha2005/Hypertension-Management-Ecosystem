
from pathlib import Path
import sys

# Allow the test to import the component source from the repo root.
ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "ai" / "component1-physiological" / "src"
sys.path.insert(0, str(SRC))

from prediction_service import assess_patient


sample_patient = {
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

result = assess_patient(sample_patient)

print("=" * 60)
print("PREDICTION SERVICE TEST")
print("=" * 60)

for key, value in result.items():
    print(f"\n{key}:")
    print(value)

assert result["status"] == "research_prototype"
assert result["model_score_percent"] is not None
assert "shap_explanation" in result
assert result["recommendations"]

print("\nManual prediction-service test passed.")
