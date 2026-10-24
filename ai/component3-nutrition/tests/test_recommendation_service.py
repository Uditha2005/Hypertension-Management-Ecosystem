from pathlib import Path
import sys

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))
from recommendation_service import build_suggestions, screen_medication_precautions


def test_rice_meal_suggestion_mentions_rice_only_when_present():
    suggestions = build_suggestions(["White rice", "Fish curry"], {"sodium_mg": 500}, [], meal_name="Lunch")
    veg = next(item for item in suggestions if item["type"] == "food_group")
    assert veg["title"] == "Add a vegetable side"
    assert "alongside the rice" in veg["text"]
    assert "rice" not in next(item for item in suggestions if item["title"] == "Consider a lentil or legume dish")["text"] or "rice" in veg["text"]


def test_non_rice_meal_does_not_mention_rice():
    suggestions = build_suggestions(["Pancakes", "Butter", "Syrup", "Orange juice"], {"sodium_mg": 100}, [], meal_name="Breakfast")
    combined = " ".join(item["title"] + " " + item["text"] for item in suggestions).lower()
    assert "rice" not in combined
    assert any(item["title"] == "Consider a fruit or vegetable option" for item in suggestions)
    assert any(item["title"] == "Consider a lentil or legume dish" for item in suggestions)


def test_does_not_suggest_missing_food_groups_when_present():
    suggestions = build_suggestions(["Rice", "Spinach", "Lentil curry"], {"sodium_mg": 300}, [])
    assert not any(item["type"] == "food_group" for item in suggestions)


def test_sodium_suggestion_is_single_and_does_not_repeat_assessment_text():
    generic_assessment = ["Review the highest-sodium ingredients and compare lower-sodium alternatives"]
    suggestions = build_suggestions(["Pancakes", "Butter", "Syrup", "Orange juice"], {"sodium_mg": 948.8}, generic_assessment, meal_name="Breakfast")
    sodium = [item for item in suggestions if "sodium" in (item["title"] + " " + item["text"]).lower()]
    assert len(sodium) == 1
    assert all(item["title"] != "Nutrition reference suggestion" for item in suggestions)


def test_unknown_nutrients_do_not_trigger_nutrient_specific_suggestions():
    suggestions = build_suggestions(["Rice", "Fish curry"], {"sodium_mg": None, "sat_fat_g": None, "energy_kcal": None})
    assert not any(item["type"] == "nutrient" for item in suggestions)


def test_saturated_fat_suggestion_requires_available_values_and_context_threshold():
    suggestions = build_suggestions(["Butter", "Pancakes"], {"sodium_mg": 100, "sat_fat_g": 8, "energy_kcal": 500})
    assert any(item["title"] == "Review saturated-fat sources" for item in suggestions)
    unknown = build_suggestions(["Butter", "Pancakes"], {"sodium_mg": 100, "sat_fat_g": None, "energy_kcal": 500})
    assert not any(item["title"] == "Review saturated-fat sources" for item in unknown)


def test_potassium_precaution_requires_confirmed_ingredient_and_relevant_food():
    assert screen_medication_precautions([], ["salt substitute"]) == []
    # A medicine alone must not produce a food interaction warning unrelated to the meal.
    assert screen_medication_precautions(["spironolactone"], ["rice", "fish curry"]) == []
    warnings = screen_medication_precautions(["spironolactone 25mg"], ["potassium salt substitute"])
    assert warnings and "potassium" in warnings[0]["message"].lower()
    assert warnings[0]["source"].startswith("https://www.nhs.uk/")
    assert warnings[0]["evidence_type"] == "official_patient_guidance"


def test_grapefruit_warning_only_when_relevant_food_and_medicine_present():
    assert not screen_medication_precautions(["verapamil"], ["rice"])
    warnings = screen_medication_precautions(["verapamil 40mg"], ["grapefruit juice"])
    assert warnings and "grapefruit" in warnings[0]["message"].lower()
    assert warnings[0]["source"].startswith("https://www.nhs.uk/")


def test_clopidogrel_rule_requires_grapefruit_juice_not_whole_grapefruit():
    assert screen_medication_precautions(["clopidogrel 75mg"], ["grapefruit"]) == []
    assert screen_medication_precautions(["clopidogrel 75mg"], ["grapefruit juice"])


def test_ambiguous_catalogue_brand_is_not_assumed_to_be_nifedipine():
    # The folder label is intentionally not normalized to nifedipine automatically.
    assert screen_medication_precautions(["Nitedipine - Nicardia E 20mg"], ["grapefruit juice"]) == []


def test_interaction_registry_requires_exact_active_ingredient_match():
    assert screen_medication_precautions(["not-ramipril-like-product"], ["LoSalt"] ) == []
    assert screen_medication_precautions(["ramipril 5mg"], ["LoSalt"] )


def test_explicit_legume_restriction_suppresses_legume_suggestion_only():
    suggestions = build_suggestions(
        ["White rice", "Fish curry"], {"sodium_mg": 100},
        personal_profile={"dietary_restrictions": ["avoid legumes"]},
    )
    assert not any("legume" in item["title"].lower() or "lentil" in item["title"].lower() for item in suggestions)
    assert any("vegetable" in item["title"].lower() for item in suggestions)


def test_specific_peanut_allergy_does_not_suppress_general_legume_suggestion():
    suggestions = build_suggestions(
        ["White rice", "Fish curry"], {"sodium_mg": 100},
        personal_profile={"allergies": ["peanut"]},
    )
    assert any("legume" in item["title"].lower() for item in suggestions)


def test_allergy_matching_is_conservative_and_only_suppresses_named_candidate_term():
    suggestions = build_suggestions(
        ["Rice", "Fish curry"], {"sodium_mg": 100},
        personal_profile={"allergies": ["vegetable"]},
    )
    assert not any("vegetable" in item["title"].lower() for item in suggestions)


def test_no_profile_preserves_baseline_suggestions():
    baseline = build_suggestions(["Rice", "Fish curry"], {"sodium_mg": 100})
    explicit_empty = build_suggestions(["Rice", "Fish curry"], {"sodium_mg": 100}, personal_profile={})
    assert baseline == explicit_empty


def test_saved_dash_goal_adds_context_to_existing_sodium_reason():
    suggestions = build_suggestions(
        ["Instant noodles", "Fish"], {"sodium_mg": 900},
        personal_profile={"nutrition_goal": "dash_style"},
    )
    sodium = next(item for item in suggestions if "sodium" in item["title"].lower())
    assert "saved nutrition goal" in sodium["reason"].lower()


def test_non_sodium_goal_does_not_claim_sodium_personalization():
    suggestions = build_suggestions(
        ["Instant noodles", "Fish"], {"sodium_mg": 900},
        personal_profile={"nutrition_goal": "build muscle"},
    )
    sodium = next(item for item in suggestions if "sodium" in item["title"].lower())
    assert "saved nutrition goal" not in sodium["reason"].lower()


def test_saved_preferred_vegetable_is_used_as_optional_example():
    suggestions = build_suggestions(
        ["White rice", "Fish curry"], {"sodium_mg": 100},
        personal_profile={"preferred_foods": ["spinach", "red rice"]},
    )
    vegetable = next(item for item in suggestions if "vegetable" in item["title"].lower())
    assert "spinach" in vegetable["text"].lower()

def test_preferred_food_example_does_not_repeat_explicit_allergen():
    suggestions = build_suggestions(
        ["White rice", "Fish curry"], {"sodium_mg": 100},
        personal_profile={"preferred_foods": ["spinach", "peanut greens"], "allergies": ["peanut"]},
    )
    vegetable = next(item for item in suggestions if "vegetable" in item["title"].lower())
    assert "spinach" in vegetable["text"].lower()
    assert "peanut greens" not in vegetable["text"].lower()
