"""Build classifier features from selected planned meal days.

The classifier was trained on observed NHANES dietary recalls. This helper
only maps planned-meal daily summaries to the trained feature shape; it does
not establish clinical validity or equivalence to observed recalls.
"""

from __future__ import annotations

import math
from datetime import date
from numbers import Integral, Real
from typing import Iterable

try:
    from meal_plan_nutrients import MealPlanSummary, NutrientSummary
    from train_selected_model import FEATURE_COLUMNS
except ModuleNotFoundError:
    from .meal_plan_nutrients import MealPlanSummary, NutrientSummary
    from .train_selected_model import FEATURE_COLUMNS


_REQUIRED_NUTRIENTS = (
    "sodium_mg",
    "potassium_mg",
    "energy_kcal",
    "sat_fat_g",
)
_MIN_TRAINING_AGE = 18
_MAX_TRAINING_AGE = 80


def _validate_numeric(value: object, name: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be a finite number")
    if positive and number <= 0:
        raise ValueError(f"{name} must be greater than zero")
    if not positive and number < 0:
        raise ValueError(f"{name} must not be negative")
    return number


def _validate_selected_days(selected_days: Iterable[str], daily: dict[str, NutrientSummary]) -> list[str]:
    if isinstance(selected_days, (str, bytes)):
        raise TypeError("selected_days must be an iterable of ISO date strings")

    try:
        days = list(selected_days)
    except TypeError as error:
        raise TypeError("selected_days must be an iterable of ISO date strings") from error
    if not days:
        raise ValueError("selected_days must not be empty")
    if len(days) != len(set(days)):
        raise ValueError("selected_days must not contain duplicate dates")

    for day in days:
        if not isinstance(day, str) or day != day.strip():
            raise ValueError("selected days must be canonical ISO dates")
        try:
            parsed_day = date.fromisoformat(day)
        except ValueError as error:
            raise ValueError("selected days must be canonical ISO dates") from error
        if parsed_day.isoformat() != day:
            raise ValueError("selected days must be canonical ISO dates")
        if day not in daily:
            raise ValueError(f"selected day is missing from the daily summary: {day}")
    return days


def _validate_demographics(age: Real, sex_female: int, bmi: Real) -> tuple[float, float]:
    age_value = _validate_numeric(age, "age")
    if not _MIN_TRAINING_AGE <= age_value <= _MAX_TRAINING_AGE:
        raise ValueError("age must be within the training dataset range of 18 through 80")

    if isinstance(sex_female, bool) or not isinstance(sex_female, Integral) or sex_female not in (0, 1):
        raise ValueError("sex_female must be the integer encoding 0 or 1")

    bmi_value = _validate_numeric(bmi, "bmi", positive=True)
    return age_value, bmi_value


def build_classifier_features(
    summary: MealPlanSummary,
    *,
    age: Real,
    sex_female: int,
    bmi: Real,
    selected_days: Iterable[str],
) -> dict[str, float]:
    """Return ordered classifier features from explicitly selected planned days."""
    if not isinstance(summary, MealPlanSummary):
        raise TypeError("summary must be a MealPlanSummary")

    age_value, bmi_value = _validate_demographics(age, sex_female, bmi)
    days = _validate_selected_days(selected_days, summary.daily)

    for day in days:
        if not isinstance(summary.daily[day], NutrientSummary):
            raise TypeError(f"daily summary for selected day {day} must be a NutrientSummary")

    nutrient_means: dict[str, float] = {}
    for nutrient in _REQUIRED_NUTRIENTS:
        values = []
        for day in days:
            value = getattr(summary.daily[day], nutrient)
            if value is None:
                raise ValueError(f"selected day {day} has unknown nutrient: {nutrient}")
            values.append(_validate_numeric(value, f"{nutrient} for {day}"))
        mean = sum(values) / len(values)
        if not math.isfinite(mean):
            raise ValueError(f"mean {nutrient} must be finite")
        nutrient_means[nutrient] = mean

    potassium_mean = nutrient_means["potassium_mg"]
    if potassium_mean <= 0:
        raise ValueError("mean potassium_mg must be greater than zero")
    ratio_mean = nutrient_means["sodium_mg"] / potassium_mean
    if not math.isfinite(ratio_mean):
        raise ValueError("na_k_ratio_mean must be finite")

    features = {
        "age": age_value,
        "sex_female": float(sex_female),
        "bmi": bmi_value,
        "sodium_mg_mean": nutrient_means["sodium_mg"],
        "potassium_mg_mean": potassium_mean,
        "energy_kcal_mean": nutrient_means["energy_kcal"],
        "sat_fat_g_mean": nutrient_means["sat_fat_g"],
        "na_k_ratio_mean": ratio_mean,
    }
    return {column: features[column] for column in FEATURE_COLUMNS}
