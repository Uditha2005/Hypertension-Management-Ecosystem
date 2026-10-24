"""Tests for the legacy daily-alignment classifier's unavailable state."""
from pathlib import Path
import sys
from types import SimpleNamespace

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from api import estimate_daily_alignment  # noqa: E402


def test_daily_alignment_does_not_claim_prediction_without_legacy_classifier():
    summary = SimpleNamespace(
        potassium_mg=2500,
        fiber_g=25,
        protein_g=70,
        carbs_g=250,
        calcium_mg=900,
        magnesium_mg=300,
        vitamin_c_mg=75,
    )

    result = estimate_daily_alignment(summary, age_years=55, sex_code=1)

    assert result["status"] == "unavailable"
    assert "reason" in result
    assert "model file is missing" in result["reason"].lower()
    assert "predicted_daily_alignment_proxy" not in result
    assert "confidence" not in result
