from meal_assessment import assess_meal


def test_assessment_reports_daily_reference_share_not_meal_limit():
    result = assess_meal({"sodium_mg": 690, "potassium_mg": 500, "energy_kcal": 600, "sat_fat_g": 5}, [])
    sodium = next(item for item in result["items"] if item["nutrient"] == "Sodium")
    assert sodium["daily_reference_share_pct"] == 30.0
    assert "daily reference" in sodium["message"]
    assert result["method"] == "transparent_nutrient_reference_assessment"
    assert result["suggestions"]


def test_missing_nutrients_are_not_zero():
    result = assess_meal({"sodium_mg": None, "potassium_mg": None, "energy_kcal": None, "sat_fat_g": None}, ["vegetarian"])
    assert all(item["status"] == "unknown" for item in result["items"])
    assert any("cannot verify" in note for note in result["notes"])
