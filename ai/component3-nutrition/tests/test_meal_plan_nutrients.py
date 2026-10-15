"""Tests for deterministic planned-meal nutrient aggregation."""

import math
import sys
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from meal_plan_nutrients import (  # noqa: E402
    NutrientProfile,
    PlannedFoodEntry,
    aggregate_meal_plan,
)


def entry(food="oats", day="2026-10-12", quantity=1, **nutrients):
    return PlannedFoodEntry(food, day, quantity, NutrientProfile(**nutrients))


def test_one_food_entry_returns_scaled_daily_and_total_summary():
    result = aggregate_meal_plan(
        [entry(quantity=2, sodium_mg=100, potassium_mg=200, energy_kcal=300, sat_fat_g=4)]
    )

    assert result.daily["2026-10-12"].sodium_mg == 200
    assert result.daily["2026-10-12"].potassium_mg == 400
    assert result.daily["2026-10-12"].energy_kcal == 600
    assert result.daily["2026-10-12"].sat_fat_g == 8
    assert result.daily["2026-10-12"].na_k_ratio == 0.5
    assert result.total == result.daily["2026-10-12"]


def test_multiple_foods_on_one_day_are_summed():
    result = aggregate_meal_plan(
        [
            entry(food="oats", sodium_mg=100, potassium_mg=200, energy_kcal=300, sat_fat_g=4),
            entry(food="banana", quantity=2, sodium_mg=5, potassium_mg=400, energy_kcal=100, sat_fat_g=0.3),
        ]
    )

    summary = result.daily["2026-10-12"]
    assert (summary.sodium_mg, summary.potassium_mg) == (110, 1000)
    assert (summary.energy_kcal, summary.sat_fat_g) == (500, 4.6)
    assert summary.na_k_ratio == 0.11


def test_multiple_days_have_daily_sums_and_weekly_total_sum():
    result = aggregate_meal_plan(
        [
            entry(day="2026-10-12", sodium_mg=100, potassium_mg=200, energy_kcal=300, sat_fat_g=4),
            entry(day="2026-10-13", sodium_mg=50, potassium_mg=100, energy_kcal=150, sat_fat_g=2),
        ]
    )

    assert set(result.daily) == {"2026-10-12", "2026-10-13"}
    assert result.total.sodium_mg == 150
    assert result.total.energy_kcal == 450
    assert result.total.na_k_ratio == 0.5


def test_quantity_is_proportional_to_reference_quantity():
    result = aggregate_meal_plan(
        [
            entry(
                quantity=150,
                reference_quantity=100,
                sodium_mg=80,
                potassium_mg=120,
                energy_kcal=200,
                sat_fat_g=5,
            )
        ]
    )

    assert result.total.sodium_mg == 120
    assert result.total.potassium_mg == 180
    assert result.total.energy_kcal == 300
    assert result.total.sat_fat_g == 7.5


@pytest.mark.parametrize("quantity", [-1, math.nan, math.inf, -math.inf])
def test_invalid_or_negative_quantities_are_rejected(quantity):
    with pytest.raises(ValueError):
        aggregate_meal_plan([entry(quantity=quantity)])


def test_invalid_reference_quantity_is_rejected():
    with pytest.raises(ValueError):
        aggregate_meal_plan([entry(reference_quantity=0, sodium_mg=1)])


def test_missing_nutrient_in_one_of_multiple_foods_remains_unknown_in_daily_and_total_sums():
    result = aggregate_meal_plan(
        [
            entry(sodium_mg=100, potassium_mg=200, energy_kcal=300, sat_fat_g=4),
            entry(food="banana", sodium_mg=None, potassium_mg=400, energy_kcal=100, sat_fat_g=0.3),
        ]
    )

    daily = result.daily["2026-10-12"]
    assert daily.sodium_mg is None
    assert result.total.sodium_mg is None
    assert daily.potassium_mg == 600
    assert daily.energy_kcal == 400
    assert daily.sat_fat_g == 4.3
    assert daily.na_k_ratio is None


def test_missing_nutrient_is_explicitly_unknown_not_zero():
    result = aggregate_meal_plan(
        [entry(sodium_mg=None, potassium_mg=200, energy_kcal=300, sat_fat_g=4)]
    )

    assert result.total.sodium_mg is None
    assert result.total.na_k_ratio is None
    assert result.total.potassium_mg == 200


def test_zero_potassium_does_not_create_ratio():
    result = aggregate_meal_plan(
        [entry(sodium_mg=100, potassium_mg=0, energy_kcal=300, sat_fat_g=4)]
    )

    assert result.total.potassium_mg == 0
    assert result.total.na_k_ratio is None


@pytest.mark.parametrize("quantity", [True, False])
def test_boolean_quantities_are_rejected(quantity):
    with pytest.raises(ValueError):
        aggregate_meal_plan([entry(quantity=quantity)])


@pytest.mark.parametrize("nutrient", [True, False])
def test_boolean_nutrient_values_are_rejected(nutrient):
    with pytest.raises(ValueError):
        aggregate_meal_plan([entry(sodium_mg=nutrient)])


@pytest.mark.parametrize("reference_quantity", [-1, math.nan, math.inf, -math.inf, True, False])
def test_negative_non_finite_or_boolean_reference_quantities_are_rejected(reference_quantity):
    with pytest.raises(ValueError):
        aggregate_meal_plan([entry(reference_quantity=reference_quantity, sodium_mg=1)])


def test_empty_meal_plan_is_rejected():
    with pytest.raises(ValueError, match="at least one"):
        aggregate_meal_plan([])


@pytest.mark.parametrize(
    "day",
    ["Monday", "2026-2-03", "2026-02-30", " 2026-10-12", "2026-10-12 "],
)
def test_invalid_calendar_dates_are_rejected(day):
    with pytest.raises(ValueError, match="ISO date"):
        aggregate_meal_plan([entry(day=day)])


def test_malformed_nutrient_profile_is_rejected():
    malformed_entry = PlannedFoodEntry("oats", "2026-10-12", 1, object())

    with pytest.raises(TypeError, match="NutrientProfile"):
        aggregate_meal_plan([malformed_entry])


@pytest.mark.parametrize("nutrient", [math.nan, math.inf, -math.inf, -1])
def test_invalid_or_non_finite_nutrient_data_is_rejected(nutrient):
    with pytest.raises(ValueError):
        aggregate_meal_plan([entry(sodium_mg=nutrient)])