"""Tests for mapping planned daily summaries to classifier features."""

import math
import sys
from dataclasses import replace
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from meal_plan_classifier_features import build_classifier_features  # noqa: E402
from meal_plan_nutrients import (  # noqa: E402
    MealPlanSummary,
    NutrientProfile,
    NutrientSummary,
    PlannedFoodEntry,
    aggregate_meal_plan,
)
from train_selected_model import FEATURE_COLUMNS  # noqa: E402


def entry(day, sodium, potassium, energy, sat_fat):
    return PlannedFoodEntry(
        "meal",
        day,
        1,
        NutrientProfile(
            sodium_mg=sodium,
            potassium_mg=potassium,
            energy_kcal=energy,
            sat_fat_g=sat_fat,
        ),
    )


def make_summary(*entries):
    return aggregate_meal_plan(entries)


def test_builds_ordered_features_from_selected_daily_means():
    summary = make_summary(
        entry("2026-10-12", 1000, 2000, 2000, 10),
        entry("2026-10-13", 3000, 4000, 3000, 20),
    )

    result = build_classifier_features(
        summary,
        age=58,
        sex_female=1,
        bmi=26.4,
        selected_days=["2026-10-12", "2026-10-13"],
    )

    assert list(result) == FEATURE_COLUMNS
    assert result == {
        "age": 58.0,
        "sex_female": 1.0,
        "bmi": 26.4,
        "sodium_mg_mean": 2000.0,
        "potassium_mg_mean": 3000.0,
        "energy_kcal_mean": 2500.0,
        "sat_fat_g_mean": 15.0,
        "na_k_ratio_mean": 2 / 3,
    }


def test_uses_selected_daily_summaries_not_period_total():
    daily = make_summary(
        entry("2026-10-12", 1000, 2000, 2000, 10),
        entry("2026-10-13", 3000, 4000, 3000, 20),
    )
    summary = MealPlanSummary(
        daily=daily.daily,
        total=NutrientSummary(999999, 1, 999999, 999999, 999999),
    )

    result = build_classifier_features(
        summary,
        age=80,
        sex_female=0,
        bmi=24,
        selected_days=["2026-10-12"],
    )

    assert result["sodium_mg_mean"] == 1000
    assert result["potassium_mg_mean"] == 2000
    assert result["energy_kcal_mean"] == 2000
    assert result["sat_fat_g_mean"] == 10
    assert result["na_k_ratio_mean"] == 0.5


def test_rejects_invalid_selected_daily_summary_type():
    summary = make_summary(entry("2026-10-12", 100, 200, 300, 4))
    invalid_summary = MealPlanSummary(daily={"2026-10-12": object()}, total=summary.total)

    with pytest.raises(TypeError, match="NutrientSummary"):
        build_classifier_features(
            invalid_summary,
            age=58,
            sex_female=1,
            bmi=26.4,
            selected_days=["2026-10-12"],
        )


@pytest.mark.parametrize("nutrient", ["sodium_mg", "potassium_mg", "energy_kcal", "sat_fat_g"])
def test_rejects_non_finite_nutrient_mean(nutrient):
    values = {
        "sodium_mg": 100.0,
        "potassium_mg": 200.0,
        "energy_kcal": 300.0,
        "sat_fat_g": 4.0,
        "na_k_ratio": 0.5,
    }
    values[nutrient] = float.fromhex("0x1.fffffffffffffp+1023")
    summary = MealPlanSummary(
        daily={
            "2026-10-12": NutrientSummary(**values),
            "2026-10-13": NutrientSummary(**values),
        },
        total=NutrientSummary(100, 200, 300, 4, 0.5),
    )

    with pytest.raises(ValueError, match=f"mean {nutrient} must be finite"):
        build_classifier_features(
            summary,
            age=58,
            sex_female=1,
            bmi=26.4,
            selected_days=["2026-10-12", "2026-10-13"],
        )


def test_rejects_non_finite_ratio_after_division():
    summary = MealPlanSummary(
        daily={
            "2026-10-12": NutrientSummary(
                float.fromhex("0x1.fffffffffffffp+1023"), 1e-308, 300, 4, None
            ),
        },
        total=NutrientSummary(100, 200, 300, 4, 0.5),
    )

    with pytest.raises(ValueError, match="na_k_ratio_mean must be finite"):
        build_classifier_features(
            summary,
            age=58,
            sex_female=1,
            bmi=26.4,
            selected_days=["2026-10-12"],
        )


def test_ratio_is_mean_sodium_divided_by_mean_potassium():
    summary = make_summary(
        entry("2026-10-12", 100, 100, 1, 1),
        entry("2026-10-13", 900, 900, 1, 1),
    )

    result = build_classifier_features(
        summary,
        age=18,
        sex_female=0,
        bmi=20,
        selected_days=["2026-10-12", "2026-10-13"],
    )

    assert result["na_k_ratio_mean"] == 1.0


@pytest.mark.parametrize("selected_days", [[], ["2026-10-12", "2026-10-12"], ["2026-10-14"]])
def test_rejects_empty_duplicate_or_missing_selected_days(selected_days):
    summary = make_summary(entry("2026-10-12", 100, 200, 300, 4))

    with pytest.raises(ValueError):
        build_classifier_features(
            summary,
            age=58,
            sex_female=1,
            bmi=26.4,
            selected_days=selected_days,
        )


@pytest.mark.parametrize("selected_day", ["2026-10-12 ", "2026-2-12", "not-a-date", "2026-02-30"])
def test_rejects_malformed_selected_dates(selected_day):
    summary = make_summary(entry("2026-10-12", 100, 200, 300, 4))

    with pytest.raises(ValueError, match="ISO date"):
        build_classifier_features(
            summary,
            age=58,
            sex_female=1,
            bmi=26.4,
            selected_days=[selected_day],
        )


@pytest.mark.parametrize("nutrient", ["sodium_mg", "potassium_mg", "energy_kcal", "sat_fat_g"])
def test_rejects_unknown_required_nutrient_on_selected_day(nutrient):
    summary = make_summary(entry("2026-10-12", 100, 200, 300, 4))
    summary = MealPlanSummary(
        daily={"2026-10-12": replace(summary.daily["2026-10-12"], **{nutrient: None})},
        total=summary.total,
    )

    with pytest.raises(ValueError, match="unknown nutrient"):
        build_classifier_features(
            summary,
            age=58,
            sex_female=1,
            bmi=26.4,
            selected_days=["2026-10-12"],
        )


def test_unknown_nutrient_on_unselected_day_is_ignored():
    summary = make_summary(
        entry("2026-10-12", 100, 200, 300, 4),
        entry("2026-10-13", None, 200, 300, 4),
    )

    result = build_classifier_features(
        summary,
        age=58,
        sex_female=1,
        bmi=26.4,
        selected_days=["2026-10-12"],
    )

    assert result["sodium_mg_mean"] == 100


def test_rejects_non_positive_mean_potassium():
    summary = make_summary(entry("2026-10-12", 100, 0, 300, 4))

    with pytest.raises(ValueError, match="potassium"):
        build_classifier_features(
            summary,
            age=58,
            sex_female=1,
            bmi=26.4,
            selected_days=["2026-10-12"],
        )


@pytest.mark.parametrize("age", [True, False, -1, math.nan, math.inf, 17, 80.1])
def test_rejects_invalid_age(age):
    summary = make_summary(entry("2026-10-12", 100, 200, 300, 4))

    with pytest.raises(ValueError):
        build_classifier_features(
            summary,
            age=age,
            sex_female=1,
            bmi=26.4,
            selected_days=["2026-10-12"],
        )


@pytest.mark.parametrize("sex_female", [True, False, -1, 2, 0.0, "1"])
def test_rejects_invalid_sex_encoding(sex_female):
    summary = make_summary(entry("2026-10-12", 100, 200, 300, 4))

    with pytest.raises(ValueError):
        build_classifier_features(
            summary,
            age=58,
            sex_female=sex_female,
            bmi=26.4,
            selected_days=["2026-10-12"],
        )


@pytest.mark.parametrize("bmi", [True, False, 0, -1, math.nan, math.inf, "26.4"])
def test_rejects_invalid_bmi(bmi):
    summary = make_summary(entry("2026-10-12", 100, 200, 300, 4))

    with pytest.raises(ValueError):
        build_classifier_features(
            summary,
            age=58,
            sex_female=1,
            bmi=bmi,
            selected_days=["2026-10-12"],
        )
