"""Evidence-informed nutrient checks, kept separate from ML predictions.

The sodium value is a general US adult reference (2,300 mg/day), not a
personalised prescription. Assessment only reflects foods entered for a day.
"""
from __future__ import annotations
from typing import Any

GENERAL_ADULT_SODIUM_REFERENCE_MG = 2300.0

def assess_daily_nutrition(summary: Any) -> dict[str, object]:
    sodium = getattr(summary, "sodium_mg", None)
    if sodium is None:
        sodium_status = "unknown"
        sodium_message = "Sodium could not be fully assessed because one or more food records lack sodium data."
    elif float(sodium) > GENERAL_ADULT_SODIUM_REFERENCE_MG:
        sodium_status = "above_reference"
        sodium_message = (
            "The sodium total for the foods entered is above the general adult reference "
            "of 2,300 mg/day. Review portions, ingredients and the complete day's intake."
        )
    else:
        sodium_status = "at_or_below_reference"
        sodium_message = (
            "The sodium total for the foods entered is at or below the general adult reference "
            "of 2,300 mg/day. This does not establish that the complete day's intake is suitable."
        )
    concerns = []
    if sodium_status == "above_reference":
        concerns.append("sodium")
    if getattr(summary, "potassium_mg", None) is None:
        concerns.append("potassium information incomplete")
    if getattr(summary, "sat_fat_g", None) is None:
        concerns.append("saturated-fat information incomplete")
    return {
        "sodium_reference_mg": GENERAL_ADULT_SODIUM_REFERENCE_MG,
        "sodium_status": sodium_status,
        "sodium_message": sodium_message,
        "nutritional_concerns": concerns,
        "scope_note": (
            "This check covers only the foods entered for this date. Missing meals or food items "
            "can change totals. The reference is general adult guidance, not an individual prescription."
        ),
    }
