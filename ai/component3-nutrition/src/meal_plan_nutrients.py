"""Deterministic nutrient aggregation for planned meals.

This module processes planned meal data supplied by the application. It does
not read NHANES recalls, call USDA APIs, or infer a BP category.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from numbers import Real
from typing import Iterable


NUTRIENT_FIELDS = (
    "sodium_mg",
    "potassium_mg",
    "energy_kcal",
    "sat_fat_g",
)


@dataclass(frozen=True)
class NutrientProfile:
    """Nutrients provided for one reference quantity of a food.

    Values use milligrams for sodium and potassium, kilocalories for energy,
    and grams for saturated fat. A ``None`` value means the nutrient is
    unknown, not zero. ``reference_quantity`` uses the same unit as the
    planned entry quantity.
    """

    reference_quantity: float = 1.0
    sodium_mg: float | None = None
    potassium_mg: float | None = None
    energy_kcal: float | None = None
    sat_fat_g: float | None = None


@dataclass(frozen=True)
class PlannedFoodEntry:
    """One food and its quantity in a planned meal day."""

    food: str
    day: str
    quantity: float
    nutrients: NutrientProfile


@dataclass(frozen=True)
class NutrientSummary:
    """Nutrient sums for a day or the complete plan, never daily averages."""

    sodium_mg: float | None
    potassium_mg: float | None
    energy_kcal: float | None
    sat_fat_g: float | None
    na_k_ratio: float | None


@dataclass(frozen=True)
class MealPlanSummary:
    """Daily nutrient sums and the complete planned-period nutrient sum."""

    daily: dict[str, NutrientSummary]
    total: NutrientSummary


def _validate_number(value: object, name: str, *, allow_none: bool = False) -> float | None:
    if value is None and allow_none:
        return None
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be a finite number")
    if number < 0:
        raise ValueError(f"{name} must not be negative")
    return number


def _validate_entry(entry: PlannedFoodEntry) -> None:
    if not isinstance(entry, PlannedFoodEntry):
        raise TypeError("entries must contain PlannedFoodEntry values")
    if not isinstance(entry.food, str) or not entry.food.strip():
        raise ValueError("food must be a non-empty string")
    if not isinstance(entry.day, str) or entry.day != entry.day.strip():
        raise ValueError("day must be an ISO date in YYYY-MM-DD format")
    try:
        parsed_day = date.fromisoformat(entry.day)
    except ValueError as error:
        raise ValueError("day must be a real ISO date in YYYY-MM-DD format") from error
    if parsed_day.isoformat() != entry.day:
        raise ValueError("day must be an ISO date in YYYY-MM-DD format")

    if not isinstance(entry.nutrients, NutrientProfile):
        raise TypeError("nutrients must be a NutrientProfile")

    _validate_number(entry.quantity, "quantity")
    _validate_number(entry.nutrients.reference_quantity, "reference_quantity")
    if entry.nutrients.reference_quantity <= 0:
        raise ValueError("reference_quantity must be greater than zero")
    for field in NUTRIENT_FIELDS:
        _validate_number(getattr(entry.nutrients, field), field, allow_none=True)


def _summary(values: dict[str, list[float | None]]) -> NutrientSummary:
    totals: dict[str, float | None] = {
        field: None if any(value is None for value in field_values) else sum(field_values)
        for field, field_values in values.items()
    }
    potassium = totals["potassium_mg"]
    sodium = totals["sodium_mg"]
    ratio = None if potassium is None or potassium <= 0 or sodium is None else sodium / potassium
    return NutrientSummary(
        sodium_mg=totals["sodium_mg"],
        potassium_mg=totals["potassium_mg"],
        energy_kcal=totals["energy_kcal"],
        sat_fat_g=totals["sat_fat_g"],
        na_k_ratio=ratio,
    )


def aggregate_meal_plan(entries: Iterable[PlannedFoodEntry]) -> MealPlanSummary:
    """Return daily sums and a complete planned-period sum.

    Nutrients are scaled by ``quantity / reference_quantity``. Missing values
    remain unknown in the corresponding summary field. The result contains
    sums only; it does not calculate a per-day average or represent observed
    NHANES dietary recall data.
    """

    daily_values: dict[str, dict[str, list[float | None]]] = {}
    total_values = {field: [] for field in NUTRIENT_FIELDS}
    entry_count = 0

    for entry in entries:
        _validate_entry(entry)
        scale = entry.quantity / entry.nutrients.reference_quantity
        day_values = daily_values.setdefault(entry.day, {field: [] for field in NUTRIENT_FIELDS})
        for field in NUTRIENT_FIELDS:
            nutrient = getattr(entry.nutrients, field)
            scaled = None if nutrient is None else nutrient * scale
            day_values[field].append(scaled)
            total_values[field].append(scaled)
        entry_count += 1

    if entry_count == 0:
        raise ValueError("entries must contain at least one planned food entry")

    return MealPlanSummary(
        daily={day: _summary(values) for day, values in daily_values.items()},
        total=_summary(total_values),
    )