from types import SimpleNamespace
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from dietary_assessment import assess_daily_nutrition, GENERAL_ADULT_SODIUM_REFERENCE_MG


def summary(sodium, potassium=3000, sat_fat=15):
    return SimpleNamespace(sodium_mg=sodium, potassium_mg=potassium, sat_fat_g=sat_fat)


def test_sodium_above_general_reference_is_flagged():
    result = assess_daily_nutrition(summary(GENERAL_ADULT_SODIUM_REFERENCE_MG + 1))
    assert result["sodium_status"] == "above_reference"
    assert "2,300 mg/day" in result["sodium_message"]
    assert "sodium" in result["nutritional_concerns"]


def test_sodium_at_reference_is_not_flagged_as_above():
    result = assess_daily_nutrition(summary(GENERAL_ADULT_SODIUM_REFERENCE_MG))
    assert result["sodium_status"] == "at_or_below_reference"
    assert "sodium" not in result["nutritional_concerns"]


def test_unknown_nutrients_are_not_treated_as_zero():
    result = assess_daily_nutrition(summary(None, potassium=None, sat_fat=None))
    assert result["sodium_status"] == "unknown"
    assert "potassium information incomplete" in result["nutritional_concerns"]
    assert "saturated-fat information incomplete" in result["nutritional_concerns"]
    assert "only the foods entered" in result["scope_note"]
