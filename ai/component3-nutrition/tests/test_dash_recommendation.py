from dash_recommendation import map_food_group, optimize_daily_food_entries


def test_common_foods_map_to_expected_groups():
    assert map_food_group("Chicken, broilers, roasted") == 24
    assert map_food_group("Pancakes, plain") == 55
    assert map_food_group("Orange juice, raw") == 61
    assert map_food_group("Spinach, cooked") == 72
    assert map_food_group("Unknown regional mixed dish") is None


def test_optimizer_reports_unknown_foods_and_returns_diagnostics():
    result = optimize_daily_food_entries([
        {"food_name": "Rice, white, cooked", "quantity_grams": 180},
        {"food_name": "Chicken, roasted", "quantity_grams": 120},
        {"food_name": "Unknown regional mixed dish", "quantity_grams": 200},
    ])
    assert result["matched_foods"]
    assert result["unmatched_foods"][0]["food_name"] == "Unknown regional mixed dish"
    assert "limitations" in result
    assert "optimizer_diagnostics" in result
    assert result["servings_before"]
    assert result["servings_after"]
