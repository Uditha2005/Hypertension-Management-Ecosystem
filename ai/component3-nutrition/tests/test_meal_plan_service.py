"""Tests for USDA-backed planned-meal resolution."""

import math
import sys
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from meal_plan_nutrients import NutrientProfile  # noqa: E402
from meal_plan_service import (  # noqa: E402
    MealPlanValidationError,
    PlannedFoodSelection,
    resolve_meal_plan,
)
from usda_fooddata import USDAFoodDataError, USDAFoodRecord  # noqa: E402


class FakeUSDAClient:
    def __init__(self, records=None, error=None):
        self.records = records or {}
        self.error = error
        self.calls = []

    def get_food(self, fdc_id):
        self.calls.append(fdc_id)
        if self.error:
            raise self.error
        return self.records[fdc_id]


def record(
    fdc_id=123,
    description="Oats",
    reference_quantity=100,
    reference_unit="g",
    sodium_mg=100,
    potassium_mg=200,
    energy_kcal=300,
    sat_fat_g=4,
    serving_size=None,
    serving_size_unit=None,
):
    return USDAFoodRecord(
        fdc_id=fdc_id,
        description=description,
        data_type="Foundation",
        nutrients=NutrientProfile(
            sodium_mg=sodium_mg,
            potassium_mg=potassium_mg,
            energy_kcal=energy_kcal,
            sat_fat_g=sat_fat_g,
        ),
        reference_quantity=reference_quantity,
        reference_unit=reference_unit,
        serving_size=serving_size,
        serving_size_unit=serving_size_unit,
    )


def selection(fdc_id=123, day="2026-10-12", quantity=100, unit="g"):
    return PlannedFoodSelection(day=day, fdc_id=fdc_id, quantity=quantity, unit=unit)


def test_multiple_selected_foods_produce_daily_and_complete_plan_summaries():
    client = FakeUSDAClient(
        {
            123: record(),
            456: record(fdc_id=456, description="Banana", sodium_mg=5, potassium_mg=400, energy_kcal=100, sat_fat_g=0.3),
        }
    )

    result = resolve_meal_plan(
        [selection(123), selection(456, quantity=200)],
        client,
    )

    assert result.daily["2026-10-12"].sodium_mg == 110
    assert result.daily["2026-10-12"].potassium_mg == 1000
    assert result.daily["2026-10-12"].energy_kcal == 500
    assert result.total.sat_fat_g == 4.6
    assert result.total.na_k_ratio == 0.11
    assert client.calls == [123, 456]


def test_quantity_scales_from_per_100g_record():
    client = FakeUSDAClient({123: record(sodium_mg=80, potassium_mg=120, energy_kcal=200, sat_fat_g=5)})

    result = resolve_meal_plan([selection(quantity=150)], client)

    assert result.total.sodium_mg == 120
    assert result.total.potassium_mg == 180
    assert result.total.energy_kcal == 300
    assert result.total.sat_fat_g == 7.5


def test_mass_unit_conversion_is_supported_when_reference_is_grams():
    client = FakeUSDAClient({123: record(sodium_mg=80)})

    result = resolve_meal_plan([selection(quantity=0.15, unit="kg")], client)

    assert result.total.sodium_mg == 120


def test_serving_unit_matches_explicit_serving_reference():
    client = FakeUSDAClient({123: record(reference_quantity=1, reference_unit="serving", sodium_mg=500)})

    result = resolve_meal_plan([selection(quantity=2, unit="servings")], client)

    assert result.total.sodium_mg == 1000


def test_grams_convert_to_servings_when_usda_provides_gram_serving_size():
    client = FakeUSDAClient({
        123: record(
            reference_quantity=1,
            reference_unit="serving",
            serving_size=40,
            serving_size_unit="g",
            sodium_mg=500,
            potassium_mg=200,
            energy_kcal=150,
            sat_fat_g=2,
        )
    })

    result = resolve_meal_plan(
        [selection(quantity=80, unit="g")],
        client,
    )

    assert result.total.sodium_mg == 1000
    assert result.total.potassium_mg == 400
    assert result.total.energy_kcal == 300
    assert result.total.sat_fat_g == 4


def test_repeated_food_id_is_fetched_once_per_operation():
    client = FakeUSDAClient({123: record(sodium_mg=100)})

    result = resolve_meal_plan(
        [selection(quantity=100), selection(quantity=50), selection(fdc_id="123", quantity=25)],
        client,
    )

    assert client.calls == [123]
    assert result.total.sodium_mg == 175


def test_malformed_record_is_rejected_before_caching():
    client = FakeUSDAClient({123: object()})

    with pytest.raises(MealPlanValidationError, match="invalid food record"):
        resolve_meal_plan([selection()], client)

    assert client.calls == [123]


def test_record_with_different_id_is_rejected_before_caching():
    client = FakeUSDAClient({123: record(fdc_id=456)})

    with pytest.raises(MealPlanValidationError, match="does not match"):
        resolve_meal_plan([selection()], client)

    assert client.calls == [123]


def test_failed_lookup_does_not_poison_cache():
    class RetryClient:
        def __init__(self):
            self.calls = 0

        def get_food(self, fdc_id):
            self.calls += 1
            if self.calls == 1:
                raise USDAFoodDataError("temporary failure")
            return record(fdc_id=fdc_id)

    client = RetryClient()
    with pytest.raises(USDAFoodDataError):
        resolve_meal_plan([selection()], client)

    result = resolve_meal_plan([selection()], client)
    assert result.total.sodium_mg == 100
    assert client.calls == 2


def test_cache_does_not_persist_between_operations():
    client = FakeUSDAClient({123: record()})

    resolve_meal_plan([selection()], client)
    resolve_meal_plan([selection()], client)

    assert client.calls == [123, 123]


def test_serving_record_rejects_mass_quantity_without_conversion():
    client = FakeUSDAClient({123: record(reference_quantity=1, reference_unit="serving")})

    with pytest.raises(MealPlanValidationError, match="convert|unsupported reference unit"):
        resolve_meal_plan([selection(quantity=100, unit="g")], client)


@pytest.mark.parametrize("field", ["sodium_mg", "potassium_mg", "energy_kcal", "sat_fat_g"])
def test_invalid_nutrient_value_in_record_is_rejected(field):
    nutrients = {
        "sodium_mg": 100,
        "potassium_mg": 200,
        "energy_kcal": 300,
        "sat_fat_g": 4,
    }
    nutrients[field] = math.nan
    client = FakeUSDAClient({123: record(**nutrients)})

    with pytest.raises(MealPlanValidationError, match=f"invalid {field}"):
        resolve_meal_plan([selection()], client)


def test_missing_nutrients_default_to_zero_when_no_compatible_fallback_exists():
    client = FakeUSDAClient({123: record(sodium_mg=None, potassium_mg=200, energy_kcal=300, sat_fat_g=4)})

    result = resolve_meal_plan([selection()], client)

    assert result.total.sodium_mg == 0
    assert result.total.na_k_ratio == 0
    assert result.total.potassium_mg == 200
    assert result.total.energy_kcal == 300


@pytest.mark.parametrize("unit", ["ml", "serving", "cup", "household"])
def test_unsupported_unit_conversion_is_rejected(unit):
    client = FakeUSDAClient({123: record(reference_unit="g")})

    with pytest.raises(MealPlanValidationError, match="unsupported|convert"):
        resolve_meal_plan([selection(unit=unit, quantity=1)], client)


def test_volume_conversion_is_not_used_for_mass_record():
    client = FakeUSDAClient({123: record(reference_unit="ml", sodium_mg=100)})

    with pytest.raises(MealPlanValidationError, match="convert|unsupported reference unit"):
        resolve_meal_plan([selection(quantity=100, unit="g")], client)


@pytest.mark.parametrize("quantity", [-1, math.nan, math.inf, -math.inf, True])
def test_invalid_quantities_are_rejected(quantity):
    client = FakeUSDAClient({123: record()})

    with pytest.raises(MealPlanValidationError, match="quantity"):
        resolve_meal_plan([selection(quantity=quantity)], client)


@pytest.mark.parametrize("fdc_id", [0, -1, "abc", True])
def test_invalid_food_ids_are_rejected_before_lookup(fdc_id):
    client = FakeUSDAClient({123: record()})

    with pytest.raises(MealPlanValidationError, match="fdc_id"):
        resolve_meal_plan([selection(fdc_id=fdc_id)], client)
    assert client.calls == []


def test_invalid_date_is_rejected_before_lookup():
    client = FakeUSDAClient({123: record()})

    with pytest.raises(MealPlanValidationError, match="ISO date"):
        resolve_meal_plan([selection(day="2026-02-30")], client)
    assert client.calls == []


def test_empty_plan_is_rejected():
    with pytest.raises(MealPlanValidationError, match="at least one"):
        resolve_meal_plan([], FakeUSDAClient())


def test_usda_errors_are_propagated_clearly():
    client = FakeUSDAClient(error=USDAFoodDataError("USDA request failed"))

    with pytest.raises(USDAFoodDataError, match="USDA request failed"):
        resolve_meal_plan([selection()], client)

def test_zero_and_unit_specific_excessive_quantities_are_rejected_before_lookup():
    client = FakeUSDAClient({123: record()})
    with pytest.raises(MealPlanValidationError, match="greater than 0"):
        resolve_meal_plan([selection(quantity=0)], client)
    with pytest.raises(MealPlanValidationError, match="no more than 5000 g"):
        resolve_meal_plan([selection(quantity=5001, unit="g")], client)
    with pytest.raises(MealPlanValidationError, match="no more than 5 kg"):
        resolve_meal_plan([selection(quantity=5.1, unit="kg")], client)
    with pytest.raises(MealPlanValidationError, match="no more than 50 serving"):
        resolve_meal_plan([selection(quantity=51, unit="serving")], client)
    assert client.calls == []
