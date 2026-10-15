"""Resolve planned foods through USDA and aggregate their nutrients."""

from __future__ import annotations

import math
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


def _validate_quantity(quantity: object) -> float:
    if isinstance(quantity, bool) or not isinstance(quantity, Real):
        raise MealPlanValidationError("quantity must be a finite non-negative number")
    value = float(quantity)
    if not math.isfinite(value) or value < 0:
        raise MealPlanValidationError("quantity must be a finite non-negative number")
    return value


def _normalize_unit(unit: object) -> str:
    if not isinstance(unit, str) or not unit or unit != unit.strip():
        raise MealPlanValidationError("unit must be a supported non-empty unit")
    normalized = _UNIT_ALIASES.get(unit.casefold())
    if normalized is None:
        raise MealPlanValidationError(f"unsupported quantity unit: {unit}")
    return normalized


def _convert_quantity(quantity: float, unit: str, record: USDAFoodRecord) -> float:
    if not isinstance(record.reference_unit, str) or not record.reference_unit.strip():
        raise MealPlanValidationError("USDA food record has no usable reference unit")
    reference_unit = record.reference_unit.casefold().strip()
    reference_quantity = record.reference_quantity
    if isinstance(reference_quantity, bool) or not isinstance(reference_quantity, Real):
        raise MealPlanValidationError("USDA food record has an invalid reference quantity")
    if not math.isfinite(float(reference_quantity)) or reference_quantity <= 0:
        raise MealPlanValidationError("USDA food record has an invalid reference quantity")

    if reference_unit == "g":
        if unit == "g":
            return quantity
        if unit == "kg":
            return quantity * 1000
    elif reference_unit == "serving" and unit == "serving":
        return quantity
    else:
        raise MealPlanValidationError(
            f"cannot safely convert quantity unit {unit} to USDA reference unit {reference_unit}"
        )
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
        quantity = _validate_quantity(selection.quantity)
        unit = _normalize_unit(selection.unit)

        if fdc_id not in cache:
            fetched_record = client.get_food(fdc_id)
            cache[fdc_id] = _validate_record(fetched_record, fdc_id)
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