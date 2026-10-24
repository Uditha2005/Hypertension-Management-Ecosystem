"""Find safer USDA record alternatives when selected foods lack target nutrients.

Suggestions are advisory and must be confirmed by the user. This module never
silently changes the selected food or combines nutrient values across records.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

try:
    from usda_fooddata import (
        PER_100_GRAM_DATA_TYPES, USDAEmptySearchError, USDAFoodDataClient,
        USDAFoodDataError, USDAFoodRecord,
    )
except ModuleNotFoundError:
    from .usda_fooddata import (
        PER_100_GRAM_DATA_TYPES, USDAEmptySearchError, USDAFoodDataClient,
        USDAFoodDataError, USDAFoodRecord,
    )

TARGET_NUTRIENTS = ("sodium_mg", "potassium_mg", "energy_kcal", "sat_fat_g")
STOP_WORDS = {"and", "or", "with", "without", "the", "of", "for", "in", "raw", "plain"}

@dataclass(frozen=True)
class FoodAlternative:
    fdc_id: int
    description: str
    data_type: str
    serving_size: float | None
    serving_size_unit: str | None
    known_nutrients: list[str]
    fills_missing_nutrients: list[str]
    similarity: float
    reference_unit: str
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

def _tokens(value: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", value.casefold()) if len(t) > 1 and t not in STOP_WORDS}

def _similarity(source: str, candidate: str) -> float:
    left, right = _tokens(source), _tokens(candidate)
    if not left or not right:
        return 0.0
    # Source-token coverage helps a shorter generic description match a longer
    # branded description without rewarding unrelated extra brand words.
    return len(left & right) / len(left)

def _known(record: USDAFoodRecord) -> list[str]:
    return [name for name in TARGET_NUTRIENTS if getattr(record.nutrients, name) is not None]

def _quantity_compatible(record: USDAFoodRecord, quantity_unit: str) -> bool:
    unit = quantity_unit.casefold().strip()
    if unit in {"g", "kg"}:
        return record.reference_unit == "g" or (
            record.reference_unit == "serving"
            and (record.serving_size_unit or "").casefold().strip() in {"g", "gram", "grams", "grm"}
            and record.serving_size is not None and record.serving_size > 0
        )
    if unit in {"serving", "servings"}:
        return record.reference_unit == "serving"
    return False

def find_food_alternatives(
    client: USDAFoodDataClient,
    fdc_id: int,
    quantity_unit: str = "g",
    limit: int = 5,
) -> dict[str, Any]:
    """Return nutrient-completeness alternatives for a selected USDA food.

    The chosen food's description is used as the query. Candidates must have a
    plausible textual match, improve target nutrient coverage, and support the
    user's existing quantity unit. User confirmation is always required.
    """
    original = client.get_food(fdc_id)
    original_known = _known(original)
    missing = [name for name in TARGET_NUTRIENTS if name not in original_known]
    if not missing:
        return {"fdc_id": fdc_id, "description": original.description,
                "missing_nutrients": [], "alternatives": [],
                "message": "This record already contains all four target nutrients."}

    query = original.description.strip()
    try:
        search_results = client.search_foods(query, page_size=min(25, max(10, limit * 4)))
    except USDAEmptySearchError:
        search_results = []

    candidates: list[tuple[tuple[float, float, float], FoodAlternative]] = []
    seen = {int(fdc_id)}
    for result in search_results:
        candidate_id = int(result.fdc_id)
        if candidate_id in seen:
            continue
        seen.add(candidate_id)
        similarity = _similarity(original.description, result.description)
        if similarity < 0.34:
            continue
        try:
            candidate = client.get_food(candidate_id)
        except USDAFoodDataError:
            continue
        if not _quantity_compatible(candidate, quantity_unit):
            continue
        known = _known(candidate)
        fills = [name for name in missing if name in known]
        if not fills:
            continue
        # Prefer improved nutrient coverage, then stronger description match;
        # generic nutrient datasets are preferred only as a tie-breaker.
        generic_bonus = 1.0 if candidate.data_type in PER_100_GRAM_DATA_TYPES else 0.0
        item = FoodAlternative(
            fdc_id=candidate.fdc_id,
            description=candidate.description,
            data_type=candidate.data_type,
            serving_size=candidate.serving_size,
            serving_size_unit=candidate.serving_size_unit,
            known_nutrients=known,
            fills_missing_nutrients=fills,
            similarity=round(similarity, 3),
            reference_unit=candidate.reference_unit,
            reason=("Adds " + ", ".join(fills) + "; confirm that this description and preparation match the food eaten."),
        )
        score = (len(fills) / len(missing), similarity, generic_bonus)
        candidates.append((score, item))

    candidates.sort(key=lambda pair: pair[0], reverse=True)
    alternatives = [item.as_dict() for _, item in candidates[:limit]]
    message = ("Review the suggested USDA matches and replace the selected record only if the food identity and preparation match."
               if alternatives else "No compatible alternative with better nutrient coverage was found. Keep unavailable nutrients unknown or search manually.")
    return {"fdc_id": original.fdc_id, "description": original.description,
            "missing_nutrients": missing, "alternatives": alternatives, "message": message}
