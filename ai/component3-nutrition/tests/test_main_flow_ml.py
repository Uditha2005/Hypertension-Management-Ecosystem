from pathlib import Path
import sys
from types import SimpleNamespace

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))
from api import estimate_daily_alignment


def test_main_flow_ml_reports_missing_features_instead_of_filling_zero():
    result = estimate_daily_alignment(
        SimpleNamespace(potassium_mg=1000, fiber_g=None, protein_g=50, carbs_g=200,
                        calcium_mg=800, magnesium_mg=250, vitamin_c_mg=50),
        age_years=55, sex_code=1,
    )
    assert result["status"] == "unavailable"
    assert "DR1TFIBE" in result["missing_features"]


def test_main_flow_ml_runs_saved_classifier_for_complete_features():
    result = estimate_daily_alignment(
        SimpleNamespace(potassium_mg=2500, fiber_g=25, protein_g=70, carbs_g=250,
                        calcium_mg=900, magnesium_mg=300, vitamin_c_mg=75),
        age_years=55, sex_code=1,
    )
    assert result["status"] == "estimated"
    assert result["predicted_daily_alignment_proxy"] in {
        "reference_aligned_proxy", "needs_review_proxy"
    }
    assert result["target_type"] == "rule-derived daily nutrient-reference alignment proxy"
