"""Transparent reference-based meal assessment; deliberately not a classifier."""
from __future__ import annotations
from typing import Any

SODIUM_DAILY_REFERENCE_MG = 2300.0
SAT_FAT_ENERGY_SHARE = 0.06


def assess_meal(nutrients: dict[str, float | None], requirements: list[str] | None = None) -> dict[str, Any]:
    """Describe nutrient contribution against daily reference context, not meal limits.

    2,300 mg sodium/day is presented as a general adult daily reference, not a
    personalized prescription or a per-meal limit. Saturated fat is compared to
    a 6%-of-energy reference; this is contextual and not a diagnosis.
    """
    sodium = nutrients.get("sodium_mg")
    energy = nutrients.get("energy_kcal")
    sat_fat = nutrients.get("sat_fat_g")
    potassium = nutrients.get("potassium_mg")
    items: list[dict[str, Any]] = []
    if sodium is None:
        items.append({"nutrient":"Sodium", "status":"unknown", "value":None,
                      "message":"Sodium was not available for every selected food; the total cannot be confirmed."})
    else:
        pct = sodium / SODIUM_DAILY_REFERENCE_MG * 100
        status = "higher_contribution" if pct >= 30 else "moderate_contribution" if pct >= 15 else "lower_contribution"
        items.append({"nutrient":"Sodium", "status":status, "value":round(sodium, 2), "unit":"mg",
                      "daily_reference_mg":SODIUM_DAILY_REFERENCE_MG, "daily_reference_share_pct":round(pct, 1),
                      "message":f"This meal contributes about {pct:.1f}% of the general daily reference of 2,300 mg sodium/day."})
    if sat_fat is None or energy is None:
        items.append({"nutrient":"Saturated fat", "status":"unknown", "value":sat_fat,
                      "message":"Saturated-fat or energy data are missing, so the share-of-energy comparison cannot be calculated."})
    else:
        limit_g = energy * SAT_FAT_ENERGY_SHARE / 9.0
        pct = (sat_fat / limit_g * 100) if limit_g > 0 else None
        status = "above_context_reference" if sat_fat > limit_g else "within_context_reference"
        items.append({"nutrient":"Saturated fat", "status":status, "value":round(sat_fat, 2), "unit":"g",
                      "energy_kcal":round(energy, 2), "reference_share_of_energy_pct":6.0,
                      "meal_sat_fat_g_at_6pct_energy":round(limit_g, 2),
                      "message":("Saturated fat is above" if sat_fat > limit_g else "Saturated fat is at or below") +
                      " the amount corresponding to 6% of this meal's energy. This is a contextual comparison, not a per-meal clinical limit."})
    items.append({"nutrient":"Potassium", "status":"informational" if potassium is not None else "unknown", "value":None if potassium is None else round(potassium, 2),
                  "unit":"mg", "message":"Potassium is reported for context only; no universal meal-level threshold is applied." if potassium is not None else "Potassium data were incomplete or unavailable."})
    reqs = [str(x).strip() for x in (requirements or []) if str(x).strip()]
    suggestions: list[str] = []
    if sodium is not None and sodium / SODIUM_DAILY_REFERENCE_MG >= 0.30:
        suggestions.append("Review the highest-sodium ingredients and compare lower-sodium alternatives; sauces, seasoning mixes, cured foods, and packaged foods can contribute sodium, but verify each product label.")
    elif sodium is not None and sodium / SODIUM_DAILY_REFERENCE_MG >= 0.15:
        suggestions.append("If you are trying to reduce sodium, compare product labels and consider a lower-sodium version where available.")
    if sat_fat is not None and energy is not None and sat_fat > energy * SAT_FAT_ENERGY_SHARE / 9.0:
        suggestions.append("Consider whether an unsaturated-fat option or a lower-saturated-fat ingredient could work in this meal; check the actual food nutrient values before substituting.")
    if not suggestions:
        suggestions.append("No change is automatically prescribed by these reference checks. Consider overall daily intake, portion size, and your own clinical dietary advice.")
    notes = []
    if reqs:
        notes.append("Your stated requirements are recorded, but this nutrient assessment cannot verify allergies, ingredients, religious restrictions, or other requirements unless the relevant food data explicitly contain them: " + ", ".join(reqs) + ".")
    notes.append("This is a transparent nutrient-reference assessment, not a trained meal-suitability prediction. Daily reference values must not be interpreted as meal-specific limits.")
    return {"method":"transparent_nutrient_reference_assessment", "label":"Nutrient reference assessment", "items":items, "suggestions":suggestions, "notes":notes,
            "references":[{"name":"FDA: Sodium in Your Diet", "url":"https://www.fda.gov/food/nutrition-education-resources-materials/sodium-your-diet", "use":"General daily sodium reference context (less than 2,300 mg/day)."},
                           {"name":"American Heart Association: Saturated Fat", "url":"https://www.heart.org/en/healthy-living/healthy-eating/eat-smart/fats/saturated-fats", "use":"Contextual reference of less than 6% of calories from saturated fat for heart-health guidance."}]}
