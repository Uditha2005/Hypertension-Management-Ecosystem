"""Resolve planned foods through USDA and aggregate their nutrients."""

from __future__ import annotations

import math
import logging
import re
from dataclasses import dataclass, replace
from datetime import date
from numbers import Real
from typing import Iterable

try:
    from meal_plan_nutrients import (
        NutrientProfile,
        PlannedFoodEntry,
        MealPlanSummary,
        aggregate_meal_plan,
    )
    from usda_fooddata import USDAFoodDataClient, USDAFoodRecord
except ModuleNotFoundError:
    from .meal_plan_nutrients import (
        NutrientProfile,
        PlannedFoodEntry,
        MealPlanSummary,
        aggregate_meal_plan,
    )
    from .usda_fooddata import USDAFoodDataClient, USDAFoodRecord


logger = logging.getLogger("nutrition.nutrient_fallback")

TARGET_NUTRIENTS = ("sodium_mg", "potassium_mg", "energy_kcal", "sat_fat_g")


class MealPlanValidationError(ValueError):
    """A planned entry cannot be safely resolved or converted."""


@dataclass(frozen=True)
class PlannedFoodSelection:
    """A planned food selected by its USDA ID and quantity basis."""

    day: str
    fdc_id: int | str
    quantity: float
    unit: str


_UNIT_ALIASES = {
    "g": "g",
    "gram": "g",
    "grams": "g",
    "kg": "kg",
    "kilogram": "kg",
    "kilograms": "kg",
    "serving": "serving",
    "servings": "serving",
}


def _normalize_id(value: object) -> int:
    if isinstance(value, bool):
        raise MealPlanValidationError("fdc_id must be a positive integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise MealPlanValidationError("fdc_id must be a positive integer") from error
    if parsed <= 0 or str(value).strip() != str(parsed):
        raise MealPlanValidationError("fdc_id must be a positive integer")
    return parsed


def _validate_day(day: object) -> str:
    if not isinstance(day, str) or day != day.strip():
        raise MealPlanValidationError("day must be an ISO date in YYYY-MM-DD format")
    try:
        parsed = date.fromisoformat(day)
    except ValueError as error:
        raise MealPlanValidationError("day must be a real ISO date in YYYY-MM-DD format") from error
    if parsed.isoformat() != day:
        raise MealPlanValidationError("day must be an ISO date in YYYY-MM-DD format")
    return day


_MAX_QUANTITY_BY_UNIT = {"g": 5000.0, "kg": 5.0, "serving": 50.0}


def _validate_quantity(quantity: object, unit: str) -> float:
    if isinstance(quantity, bool) or not isinstance(quantity, Real):
        raise MealPlanValidationError("quantity must be a finite positive number")
    value = float(quantity)
    maximum = _MAX_QUANTITY_BY_UNIT.get(unit)
    if maximum is None:
        raise MealPlanValidationError(f"unsupported quantity unit: {unit}")
    if not math.isfinite(value) or value <= 0 or value > maximum:
        limit_text = f"{maximum:g} {unit}"
        raise MealPlanValidationError(f"quantity must be greater than 0 and no more than {limit_text}")
    return value


def _normalize_unit(unit: object) -> str:
    if not isinstance(unit, str) or not unit or unit != unit.strip():
        raise MealPlanValidationError("unit must be a supported non-empty unit")
    normalized = _UNIT_ALIASES.get(unit.casefold())
    if normalized is None:
        raise MealPlanValidationError(f"unsupported quantity unit: {unit}")
    return normalized



def _convert_quantity(quantity: float, unit: str, record: USDAFoodRecord) -> float:
    """Convert the planned quantity to the USDA nutrient reference basis."""
    if not isinstance(record.reference_unit, str) or not record.reference_unit.strip():
        raise MealPlanValidationError("USDA food record has no usable reference unit")

    reference_unit = record.reference_unit.casefold().strip()
    reference_quantity = record.reference_quantity

    if (
        isinstance(reference_quantity, bool)
        or not isinstance(reference_quantity, Real)
        or not math.isfinite(float(reference_quantity))
        or reference_quantity <= 0
    ):
        raise MealPlanValidationError("USDA food record has an invalid reference quantity")

    # Nutrients are expressed per reference quantity in grams.
    if reference_unit == "g":
        if unit == "g":
            return quantity
        if unit == "kg":
            return quantity * 1000

    # Nutrients are expressed per serving.
    elif reference_unit == "serving":
        if unit == "serving":
            return quantity

        # A serving-based record may specify its serving size in grams.
        # Convert mass to servings only when USDA explicitly provides that basis.
        serving_size = record.serving_size
        serving_unit = (record.serving_size_unit or "").casefold().strip()

        if (
            serving_unit == "g"
            and isinstance(serving_size, Real)
            and not isinstance(serving_size, bool)
            and math.isfinite(float(serving_size))
            and serving_size > 0
        ):
            grams = quantity if unit == "g" else quantity * 1000 if unit == "kg" else None
            if grams is not None:
                return grams / float(serving_size)

    raise MealPlanValidationError(
        f"cannot safely convert quantity unit {unit} to USDA reference unit {reference_unit}"
    )



def _profile_with_reference(record: USDAFoodRecord) -> NutrientProfile:
    return replace(record.nutrients, reference_quantity=record.reference_quantity)


def _validate_record(record: object, requested_id: int) -> USDAFoodRecord:
    if not isinstance(record, USDAFoodRecord):
        raise MealPlanValidationError("USDA client returned an invalid food record")
    if record.fdc_id != requested_id:
        raise MealPlanValidationError("USDA food record ID does not match the requested fdc_id")
    if not isinstance(record.nutrients, NutrientProfile):
        raise MealPlanValidationError("USDA food record has an invalid nutrient profile")
    if isinstance(record.reference_quantity, bool) or not isinstance(record.reference_quantity, Real):
        raise MealPlanValidationError("USDA food record has an invalid reference quantity")
    if not math.isfinite(float(record.reference_quantity)) or record.reference_quantity <= 0:
        raise MealPlanValidationError("USDA food record has an invalid reference quantity")
    if not isinstance(record.reference_unit, str) or not record.reference_unit.strip():
        raise MealPlanValidationError("USDA food record has no usable reference unit")
    if record.reference_unit.casefold().strip() not in {"g", "serving"}:
        raise MealPlanValidationError(
            "USDA food record has an unsupported reference unit; only g and serving are supported"
        )
    for field in ("sodium_mg", "potassium_mg", "energy_kcal", "sat_fat_g"):
        value = getattr(record.nutrients, field)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(float(value)) or value < 0:
            raise MealPlanValidationError(f"USDA food record has an invalid {field} value")
    return record



def _food_tokens(description: str) -> set[str]:
    ignored = {"and", "or", "with", "without", "the", "of", "for", "in", "raw", "plain"}
    return {token for token in re.findall(r"[a-z0-9]+", description.casefold()) if len(token) > 1 and token not in ignored}


def _fallback_value_for_reference(candidate: USDAFoodRecord, original: USDAFoodRecord, nutrient: str) -> float | None:
    """Convert a candidate nutrient to the original record's reference basis only when explicit units support it."""
    value = getattr(candidate.nutrients, nutrient)
    if value is None:
        return None
    if candidate.reference_unit == original.reference_unit == "g":
        return float(value)  # both records are per 100 g
    if candidate.reference_unit == original.reference_unit == "serving":
        c_unit = (candidate.serving_size_unit or "").casefold().strip()
        o_unit = (original.serving_size_unit or "").casefold().strip()
        c_size, o_size = candidate.serving_size, original.serving_size
        if c_unit == o_unit and c_size and o_size and math.isclose(float(c_size), float(o_size), rel_tol=0.01):
            return float(value)
        # Convert only explicit gram servings, never assume a volume-to-mass density.
        if c_unit in {"g", "grm", "gram", "grams"} and o_unit in {"g", "grm", "gram", "grams"} and c_size and o_size:
            return float(value) * float(o_size) / float(c_size)
    if candidate.reference_unit == "g" and original.reference_unit == "serving":
        o_unit = (original.serving_size_unit or "").casefold().strip()
        if o_unit in {"g", "grm", "gram", "grams"} and original.serving_size:
            return float(value) * float(original.serving_size) / 100.0
    if candidate.reference_unit == "serving" and original.reference_unit == "g":
        c_unit = (candidate.serving_size_unit or "").casefold().strip()
        if c_unit in {"g", "grm", "gram", "grams"} and candidate.serving_size:
            return float(value) * 100.0 / float(candidate.serving_size)
    return None


def _resolve_missing_nutrients(original: USDAFoodRecord, client: USDAFoodDataClient) -> USDAFoodRecord:
    """Fill missing target nutrients from a close USDA match, then explicitly default unresolved gaps to 0."""
    values = {field: getattr(original.nutrients, field) for field in TARGET_NUTRIENTS}
    missing = [field for field in TARGET_NUTRIENTS if values[field] is None]
    if not missing:
        return original

    logger.warning("NUTRIENT DATA MISSING: USDA FDC %s (%s): %s; searching USDA alternatives automatically.",
                   original.fdc_id, original.description, ", ".join(missing))
    try:
        candidates = client.search_foods(original.description, page_size=25)
    except Exception as exc:
        logger.warning("USDA fallback search failed for FDC %s: %s", original.fdc_id, exc)
        candidates = []

    original_tokens = _food_tokens(original.description)
    seen = {original.fdc_id}
    for result in candidates:
        if result.fdc_id in seen:
            continue
        seen.add(result.fdc_id)
        candidate_tokens = _food_tokens(result.description)
        similarity = len(original_tokens & candidate_tokens) / len(original_tokens) if original_tokens else 0
        if similarity < 0.75:
            continue
        try:
            candidate = client.get_food(result.fdc_id)
        except Exception as exc:
            logger.warning("Could not read fallback candidate FDC %s: %s", result.fdc_id, exc)
            continue
        for nutrient in list(missing):
            candidate_value = _fallback_value_for_reference(candidate, original, nutrient)
            if candidate_value is not None:
                values[nutrient] = candidate_value
                missing.remove(nutrient)
                logger.warning("NUTRIENT FALLBACK: %s for %s filled from FDC %s (%s), converted to original reference basis.",
                               nutrient, original.description, candidate.fdc_id, candidate.description)
        if not missing:
            break

    for nutrient in missing:
        values[nutrient] = 0.0
        logger.error("NUTRIENT FALLBACK EXHAUSTED: %s for FDC %s (%s) not found with a compatible basis; using 0 as requested.",
                     nutrient, original.fdc_id, original.description)

    return replace(original, nutrients=replace(original.nutrients, **values))


def resolve_meal_plan(
    entries: Iterable[PlannedFoodSelection],
    client: USDAFoodDataClient,
) -> MealPlanSummary:
    """Resolve selected USDA foods once and aggregate their planned nutrients.

    Quantity conversion is limited to equivalent mass, equivalent volume, or
    an explicitly serving-based USDA record. Household measures and density
    conversions are intentionally rejected because this service cannot justify
    them safely.
    """

    if not isinstance(client, USDAFoodDataClient) and not hasattr(client, "get_food"):
        raise TypeError("client must provide get_food(fdc_id)")

    cache: dict[int, USDAFoodRecord] = {}
    resolved_entries: list[PlannedFoodEntry] = []
    entry_count = 0
    for selection in entries:
        if not isinstance(selection, PlannedFoodSelection):
            raise MealPlanValidationError("entries must contain PlannedFoodSelection values")
        day = _validate_day(selection.day)
        fdc_id = _normalize_id(selection.fdc_id)
        unit = _normalize_unit(selection.unit)
        quantity = _validate_quantity(selection.quantity, unit)

        if fdc_id not in cache:
            fetched_record = client.get_food(fdc_id)
            cache[fdc_id] = _resolve_missing_nutrients(_validate_record(fetched_record, fdc_id), client)
        record = cache[fdc_id]
        converted_quantity = _convert_quantity(quantity, unit, record)
        resolved_entries.append(
            PlannedFoodEntry(
                food=record.description,
                day=day,
                quantity=converted_quantity,
                nutrients=_profile_with_reference(record),
            )
        )
        entry_count += 1

    if entry_count == 0:
        raise MealPlanValidationError("entries must contain at least one planned food selection")
    return aggregate_meal_plan(resolved_entries)