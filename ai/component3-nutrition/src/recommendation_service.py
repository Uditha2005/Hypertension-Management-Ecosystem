"""Auditable, context-aware dietary suggestions and conservative medication screening.

This is a transparent rule-based baseline, not the planned trained ranking model.
Suggestions are scoped to the foods actually entered and do not infer a person's
whole-day intake from a single meal.
"""
from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Any

VEGETABLE_TERMS = (
    "vegetable", "spinach", "carrot", "cabbage", "broccoli", "pumpkin", "okra",
    "greens", "leafy green", "brinjal", "eggplant", "tomato", "cucumber", "beetroot",
    "cauliflower", "leek", "moringa", "gotukola", "mallung", "salad",
)
LEGUME_TERMS = ("lentil", "dhal", "dal", "chickpea", "chick peas", "bean", "peas", "cowpea")
RICE_TERMS = ("rice", "fried rice", "biriyani", "biryani", "kiribath")
PACKAGED_TERMS = ("chips", "crisps", "instant noodle", "processed meat", "sausage", "canned soup", "pickle")
SODIUM_SOURCE_TERMS = ("sauce", "soy sauce", "stock cube", "seasoning", "pickle", "chips", "crisps", "instant noodle", "sausage", "canned soup", "salted")

# Interaction rules live in a source-linked JSON registry so the evidence can be
# audited and reviewed separately from the model/ranking code. This registry is
# intentionally partial and only supports explicit, confirmed active ingredients.
_INTERACTION_REGISTRY_PATH = Path(__file__).with_name("medication_food_interactions.json")
try:
    with _INTERACTION_REGISTRY_PATH.open("r", encoding="utf-8") as _handle:
        _INTERACTION_REGISTRY = json.load(_handle)
except (OSError, json.JSONDecodeError):  # fail closed if evidence data are unavailable
    _INTERACTION_REGISTRY = {"rules": []}


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def build_suggestions(
    food_names: list[str],
    nutrients: dict[str, Any],
    existing: list[str] | None = None,
    meal_name: str | None = None,
    personal_profile: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    """Create non-duplicative suggestions grounded in entered foods/nutrients.

    ``existing`` is retained for API compatibility but deliberately not appended:
    the nutrient assessment already appears in its own section, and repeating its
    generic text here caused duplicate cards.
    """
    names = [_norm(x) for x in food_names if str(x or "").strip()]
    combined = " ".join(names)
    meal = _norm(meal_name or "")
    has_vegetable = _contains_any(combined, VEGETABLE_TERMS)
    has_legume = _contains_any(combined, LEGUME_TERMS)
    has_rice = _contains_any(combined, RICE_TERMS)
    suggestions: list[dict[str, str]] = []

    if names and not has_vegetable:
        if has_rice:
            title = "Add a vegetable side"
            text = "Consider adding a vegetable dish alongside the rice and other foods, choosing a preparation that fits the person's dietary needs."
        elif meal in {"breakfast", "brunch"}:
            title = "Consider a fruit or vegetable option"
            text = "If it suits this breakfast, include a fruit or vegetable option; otherwise consider adding vegetables to another meal."
        else:
            title = "Consider adding vegetables"
            text = "Add a vegetable side or include vegetables in a dish, where appropriate for the person's dietary needs."
        suggestions.append({
            "title": title,
            "text": text,
            "reason": "No clearly identifiable vegetable was recorded among the foods in this meal. This does not indicate what is missing from the rest of the day.",
            "type": "food_group",
        })

    if names and not has_legume:
        # Keep this as a separate candidate so it can be ranked later; avoid making
        # every breakfast recommendation imply lentils must be eaten at breakfast.
        if meal in {"breakfast", "brunch"}:
            text = "If suitable for the person's preferences, include a lentil or other legume dish at a meal where it fits naturally."
        elif has_rice:
            text = "A lentil, dhal, chickpea or bean dish can be served with the rice, if appropriate for the person's dietary needs."
        else:
            text = "Consider a lentil, dhal, chickpea or bean dish as part of the wider meal pattern, if appropriate for the person's dietary needs."
        suggestions.append({
            "title": "Consider a lentil or legume dish",
            "text": text,
            "reason": "No clearly identifiable legume was recorded in this meal; this is not a conclusion about the whole day's intake.",
            "type": "food_group",
        })

    sodium = nutrients.get("sodium_mg")
    try:
        sodium = float(sodium) if sodium is not None else None
        if sodium is not None and (sodium < 0 or not float("inf") > sodium):
            sodium = None
    except (TypeError, ValueError):
        sodium = None
    if sodium is not None and sodium >= 0.30 * 2300:
        if _contains_any(combined, SODIUM_SOURCE_TERMS):
            text = "Check the label or recipe for the listed sauces, seasonings or packaged item; compare sodium per portion and choose a lower-sodium option if a suitable one is available."
        else:
            text = "If salt, stock cubes, sauces or seasoning were added during preparation, review those amounts and compare product labels before making changes."
        suggestions.append({
            "title": "Review sodium in this meal",
            "text": text,
            "reason": f"The calculated sodium total ({sodium:.0f} mg) is at least 30% of the general 2,300 mg/day reference. This is context, not a meal limit, and does not identify which ingredient contributed most.",
            "type": "nutrient",
        })
    elif sodium is not None and sodium >= 0.15 * 2300:
        suggestions.append({
            "title": "Keep an eye on sodium sources",
            "text": "If reducing sodium is part of the person's dietary plan, compare labels and use less added salt or salty seasoning where the recipe allows.",
            "reason": f"The calculated sodium total ({sodium:.0f} mg) is at least 15% of the general 2,300 mg/day reference; this is context, not a meal limit.",
            "type": "nutrient",
        })

    sat_fat = nutrients.get("sat_fat_g")
    energy = nutrients.get("energy_kcal")
    try:
        sat_fat = float(sat_fat) if sat_fat is not None else None
        energy = float(energy) if energy is not None else None
    except (TypeError, ValueError):
        sat_fat, energy = None, None
    if sat_fat is not None and energy is not None and sat_fat >= 0 and energy > 0:
        contextual_amount = energy * 0.06 / 9.0
        if sat_fat > contextual_amount:
            suggestions.append({
                "title": "Review saturated-fat sources",
                "text": "If this meal includes butter, fatty meat or full-fat ingredients, consider whether a suitable lower-saturated-fat alternative would work; check the actual ingredients and nutrient values.",
                "reason": "The available saturated-fat and energy values exceed a contextual 6%-of-energy comparison. This is not a meal-specific clinical limit and does not identify the source by itself.",
                "type": "nutrient",
            })

    if any(term in combined for term in PACKAGED_TERMS) and not any(s["title"] in {"Review sodium in this meal", "Keep an eye on sodium sources"} for s in suggestions):
        suggestions.append({
            "title": "Compare packaged-food labels",
            "text": "For the packaged or preserved item entered, compare sodium per portion with similar products before choosing an alternative.",
            "reason": "A potentially packaged or preserved item was recorded, but its sodium content depends on the exact product and portion.",
            "type": "substitution",
        })

    # Apply only explicit, conservative profile constraints. This is not a complete
    # allergen checker: generic suggestions are screened for directly named terms,
    # and no ingredient-family inference is made (e.g. peanut allergy != all legumes).
    profile = personal_profile or {}
    allergies = [_norm(x) for x in profile.get("allergies", []) if str(x or "").strip()]
    restrictions = [_norm(x) for x in profile.get("dietary_restrictions", []) if str(x or "").strip()]
    preferences = [_norm(x) for x in profile.get("dietary_preferences", []) if str(x or "").strip()]
    preferred_foods = [_norm(x) for x in profile.get("preferred_foods", []) if str(x or "").strip()]

    def conflicts_with_explicit_profile(item: dict[str, str]) -> bool:
        candidate = _norm(" ".join(item.get(k, "") for k in ("title", "text")))
        # Exact named allergy terms only. Avoid treating a broad class as an
        # allergen unless the profile itself explicitly names that class.
        for allergen in allergies:
            if allergen and re.search(r"(?<![a-z0-9])" + re.escape(allergen) + r"(?![a-z0-9])", candidate):
                return True
        # Only handle unambiguous, explicit restrictions that conflict with the
        # food group named in this recommendation.
        no_legumes = any(term in restriction for restriction in restrictions for term in ("no legumes", "avoid legumes", "legume free", "legume-free", "no lentils", "avoid lentils", "lentil free", "lentil-free"))
        no_vegetables = any(term in restriction for restriction in restrictions for term in ("no vegetables", "avoid vegetables", "vegetable free", "vegetable-free"))
        vegan = any(term in value for value in restrictions + preferences for term in ("vegan",))
        vegetarian = any("vegetarian" in value for value in restrictions + preferences)
        if "legume" in candidate or "lentil" in candidate or "chickpea" in candidate or "bean dish" in candidate:
            if no_legumes:
                return True
        if ("vegetable" in candidate or "fruit or vegetable" in candidate) and no_vegetables:
            return True
        # Animal-food avoidance does not conflict with plant-food suggestions;
        # suppress only if a future candidate explicitly names animal products.
        if vegan and any(term in candidate for term in ("fish", "meat", "dairy", "egg", "butter")):
            return True
        if vegetarian and any(term in candidate for term in ("fish", "meat", "chicken", "beef", "pork")):
            return True
        return False

    suggestions = [item for item in suggestions if not conflicts_with_explicit_profile(item)]

    # Use the user's explicitly selected goal to clarify why an existing,
    # evidence-grounded suggestion may be relevant. This does not change nutrient
    # thresholds or invent foods that have not been resolved in the food database.
    goal = _norm(profile.get("nutrition_goal", ""))
    if goal and goal not in {"", "none", "unspecified"}:
        if goal in {"dash style", "dash", "hypertension", "blood pressure", "lower sodium", "reduce sodium"}:
            for item in suggestions:
                if "sodium" in _norm(item.get("title", "")):
                    item["reason"] += " The saved nutrition goal is blood-pressure-supportive eating; review this alongside the full-day pattern and clinician advice."
        elif goal in {"increase fiber", "fiber", "more fiber"}:
            for item in suggestions:
                if "legume" in _norm(item.get("title", "")) or "vegetable" in _norm(item.get("title", "")):
                    item["reason"] += " This may align with the saved fibre-related goal if the food is suitable and portions fit the overall plan."

    # When the user explicitly listed a preferred food, use it only as an
    # optional example for a matching broad food-group suggestion. Do not infer
    # nutrient content, portion size, or safety from the preference list.
    preferred_display = [str(x).strip() for x in profile.get("preferred_foods", []) if str(x or "").strip()]
    allergy_norms = [_norm(x) for x in profile.get("allergies", []) if str(x or "").strip()]
    restriction_norms = [_norm(x) for x in profile.get("dietary_restrictions", []) if str(x or "").strip()]
    safe_preferred = []
    for food in preferred_display:
        food_norm = _norm(food)
        if not food_norm:
            continue
        if any(re.search(r"(?<![a-z0-9])" + re.escape(allergen) + r"(?![a-z0-9])", food_norm) for allergen in allergy_norms if allergen):
            continue
        if any(re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", food_norm) for restriction in restriction_norms for term in ("pork", "beef", "chicken", "fish", "egg", "dairy", "milk") if term in restriction):
            continue
        safe_preferred.append(food)
    for item in suggestions:
        title_norm = _norm(item.get("title", ""))
        if "vegetable" in title_norm:
            examples = [food for food in safe_preferred if _contains_any(_norm(food), VEGETABLE_TERMS)]
            if examples:
                item["text"] += " From your saved preferences, you could consider " + ", ".join(examples[:2]) + " if suitable for this meal."
        elif "legume" in title_norm or "lentil" in title_norm:
            examples = [food for food in safe_preferred if _contains_any(_norm(food), LEGUME_TERMS)]
            if examples:
                item["text"] += " From your saved preferences, you could consider " + ", ".join(examples[:2]) + " where it fits your meal pattern."

    if not suggestions:
        suggestions.append({
            "title": "Consider the wider dietary pattern",
            "text": "Use this meal alongside the person's full-day intake and clinician-provided dietary advice. The available data do not justify a specific change to this meal.",
            "reason": "The entered food names and available nutrient values did not justify a more specific suggestion.",
            "type": "general",
        })
    return suggestions


def screen_medication_precautions(medications: list[str], food_names: list[str]) -> list[dict[str, str]]:
    """Return source-linked reminders only when a confirmed ingredient and trigger food match.

    This is a narrow evidence registry, not a complete interaction checker. An absent
    result must never be interpreted as proof that a food and medicine are compatible.
    """
    normalized_medications = [
        _norm(medication) for medication in medications if str(medication or "").strip()
    ]
    foods = " ".join(_norm(food) for food in food_names if str(food or "").strip())
    if not normalized_medications or not foods:
        return []

    results: list[dict[str, str]] = []
    seen: set[str] = set()
    for rule in _INTERACTION_REGISTRY.get("rules", []):
        ingredient = _norm(rule.get("active_ingredient", ""))
        aliases = {_norm(alias) for alias in rule.get("aliases", [])}
        aliases.add(ingredient)
        # Match an ingredient at the start of a confirmed medicine entry, optionally
        # followed by strength/brand details. Never match a loose substring inside an
        # unrelated or ambiguous catalogue label.
        ingredient_matched = any(
            alias and any(medication == alias or medication.startswith(alias + " ") for medication in normalized_medications)
            for alias in aliases
        )
        if not ingredient_matched:
            continue
        if not any(_norm(term) in foods for term in rule.get("trigger_terms", []) if _norm(term)):
            continue
        rule_id = str(rule.get("id", ""))
        if not rule_id or rule_id in seen:
            continue
        seen.add(rule_id)
        results.append({
            "severity": "check_with_professional",
            "title": str(rule.get("title", "Check medicine-specific food guidance")),
            "message": str(rule.get("message", "Check the official product information with a pharmacist or clinician.")),
            "matched_ingredients": ingredient,
            "source": str(rule.get("source_url", "")),
            "evidence_type": str(rule.get("evidence_type", "official_patient_guidance")),
            "scope": str(rule.get("scope", "")),
            "reviewed_date": str(_INTERACTION_REGISTRY.get("last_reviewed", "")),
        })
    return results
