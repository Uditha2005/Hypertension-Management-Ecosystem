"""Map confirmed food entries to the source DASH food-group serving catalogue.

Only explicit, reviewable keyword mappings are used. Unknown foods are reported and
excluded rather than silently assigned to a food group.
"""
from __future__ import annotations

import re
import numpy as np
from pathlib import Path
from typing import Any

DASH_ROOT = Path(__file__).resolve().parent.parent / "research" / "dash_servings"
DASH_RESULTS = DASH_ROOT / "results"
COEFFICIENTS = DASH_RESULTS / "nutrient_coefficients.csv"
BOUNDS = DASH_RESULTS / "dash_nutrient_bounds.csv"
METADATA = DASH_RESULTS / "food_group_metadata.csv"

# Food groups for which the app can produce a reasonably understandable suggestion.
# Excludes dataset-specific groups such as baby foods and Puerto Rican-style foods.
SUPPORTED_OPTIMIZATION_CODES = {
    11, 14, 21, 22, 23, 24, 25, 26, 31, 41, 42, 43, 51, 55, 56, 57,
    61, 62, 63, 64, 71, 72, 73, 74, 75, 78, 81, 82, 83, 91, 92, 94, 95,
}

# The first matching rule wins. This is a conservative prototype mapping, not a
# universal USDA-to-NHANES food-code crosswalk.
_GROUP_RULES = [
    (25, ("sausage", "frankfurter", "hot dog", "salami", "pepperoni", "bologna")),
    (24, ("chicken", "turkey")),
    (23, ("lamb", "goat", "venison", "veal")),
    (22, ("pork", "ham", "bacon")),
    (21, ("beef", "steak", "ground beef", "brisket")),
    (26, ("fish", "salmon", "tuna", "cod", "sardine", "trout", "shrimp", "prawn", "crab", "seafood")),
    (31, ("egg", "eggs", "omelet", "omelette")),
    (41, ("bean", "beans", "lentil", "lentils", "chickpea", "chick peas", "dhal", "dal", "peas", "cowpea", "legume")),
    (42, ("nut", "nuts", "almond", "peanut", "cashew", "walnut", "pistachio")),
    (43, ("seed", "seeds", "chia", "flaxseed", "sesame")),
    (14, ("cheese",)),
    (13, ("ice cream", "icecream", "gelato")),
    (12, ("cream", "whipping cream")),
    (11, ("milk", "yogurt", "yoghurt", "kefir")),
    (55, ("pancake", "pancakes", "waffle", "waffles")),
    (58, ("pizza", "taco", "burrito", "enchilada", "lasagna", "lasagne")),
    (53, ("cake", "cookie", "cookies", "pie", "pastry", "muffin", "brownie")),
    (52, ("biscuit", "biscuits")),
    (54, ("cracker", "crackers")),
    (51, ("bread", "toast", "bagel", "roll", "pita", "tortilla")),
    (57, ("cereal", "oatmeal", "porridge", "granola")),
    (56, ("rice", "pasta", "noodle", "noodles", "macaroni", "spaghetti", "couscous", "quinoa")),
    (61, ("orange", "grapefruit", "lemon", "lime", "tangerine", "mandarin")),
    (64, ("juice",)),
    (62, ("raisin", "raisins", "dried fruit", "date", "dates", "prune", "prunes")),
    (63, ("apple", "banana", "pear", "mango", "grape", "berries", "berry", "strawberry", "blueberry", "pineapple", "peach", "plum", "melon", "avocado")),
    (71, ("potato", "potatoes", "french fries", "french fry")),
    (72, ("spinach", "kale", "collard", "lettuce", "romaine", "greens", "moringa")),
    (73, ("carrot", "pumpkin", "squash", "sweet potato", "yam")),
    (74, ("tomato", "salsa")),
    (75, ("vegetable", "broccoli", "cabbage", "cucumber", "cauliflower", "okra", "brinjal", "eggplant", "zucchini", "green bean", "green beans", "salad")),
    (81, ("butter",)),
    (82, ("oil", "olive oil", "vegetable oil")),
    (83, ("salad dressing", "dressing")),
    (91, ("sugar", "dessert", "candy", "chocolate", "syrup", "honey")),
    (92, ("soda", "soft drink", "coffee", "iced tea", "tea")),
    (94, ("water",)),
    (95, ("shake", "smoothie", "drink mix")),
]

def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(text or "").casefold()).strip()

def map_food_group(food_name: str) -> int | None:
    name = _normalize(food_name)
    if not name:
        return None
    for code, terms in _GROUP_RULES:
        if any(_normalize(term) in name for term in terms):
            return code
    return None

def optimize_daily_food_entries(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Optimize a day's entered foods as aggregate food-group servings.

    Source coefficients/bounds describe daily aggregate profiles. They must not be
    used to evaluate a single meal. Quantities must be grams of edible food.
    """
    import pandas as pd
    try:
        from dash_optimizer import optimize_servings
    except ModuleNotFoundError:
        from .dash_optimizer import optimize_servings

    metadata = pd.read_csv(METADATA).set_index("food_code")
    codes = [int(code) for code in pd.read_csv(COEFFICIENTS, index_col=0).columns]
    grams_by_code = {int(code): float(row["serving_grams"]) for code, row in metadata.iterrows()}
    servings = {code: 0.0 for code in codes}
    matched, unmatched = [], []
    for item in items:
        name = str(item.get("food_name") or "").strip()
        try:
            grams = float(item.get("quantity_grams"))
        except (TypeError, ValueError):
            grams = float("nan")
        if not name or not (grams > 0 and grams < float("inf")):
            unmatched.append({"food_name": name or "(unnamed)", "reason": "Missing or invalid gram quantity"})
            continue
        code = map_food_group(name)
        if code is None or code not in grams_by_code:
            unmatched.append({"food_name": name, "reason": "No conservative food-group mapping found"})
            continue
        servings[code] += grams / grams_by_code[code]
        matched.append({"food_name": name, "food_group_code": code,
                        "food_group": str(metadata.loc[code, "food_name"]),
                        "quantity_grams": grams,
                        "estimated_group_servings": grams / grams_by_code[code]})
    current_profile = [servings[code] for code in codes]
    # Experimental ML model predicts next-day observed food-group servings from
    # today's observed profile. Its prediction is blended conservatively with the
    # actual intake profile, then the existing DASH optimizer enforces constraints.
    # The model predicts observed behaviour, NOT meal healthiness or clinical benefit.
    model_path = DASH_ROOT / "models" / "dash_next_day_preference_ridge.joblib"
    ml_used = False
    ml_details = {"used": False, "model": None, "blend_weight": 0.0}
    preferred = list(current_profile)
    if model_path.exists():
        try:
            import joblib
            model_bundle = joblib.load(model_path)
            model = model_bundle["model"]
            feature_columns = model_bundle["feature_columns"]
            target_columns = model_bundle["target_columns"]
            blend_weight = float(model_bundle.get("blend_weight", 0.30))
            feature_row = pd.DataFrame(
                [[servings.get(int(col.replace("food_", "")), 0.0) for col in feature_columns]],
                columns=feature_columns,
            )
            prediction = np.maximum(np.asarray(model.predict(feature_row), dtype=float).reshape(-1), 0.0)
            predicted_by_code = {
                int(col.replace("food_", "")): float(value)
                for col, value in zip(target_columns, prediction)
            }
            preferred = [
                max(0.0, (1.0 - blend_weight) * current_profile[i]
                    + blend_weight * predicted_by_code.get(code, current_profile[i]))
                for i, code in enumerate(codes)
            ]
            ml_used = True
            ml_details = {
                "used": True,
                "model": "Ridge multi-output regression",
                "prediction_target": "next-day observed food-group servings",
                "blend_weight": blend_weight,
                "warning": "Experimental behavioural prediction; not a healthiness classifier or clinically validated recommendation model."
            }
        except Exception as exc:
            # Fail safely: preserve optimizer operation on the actual current profile.
            logger = __import__("logging").getLogger(__name__)
            logger.exception("DASH ML preference model unavailable; using current profile only: %s", exc)
            preferred = list(current_profile)
    # The optimizer operates on aggregate daily food-group nutrient profiles from
    # the supplied research dataset. Explanations compare the actual current profile
    # against the final optimized profile, not the ML-blended objective profile.
    result = optimize_servings(preferred, COEFFICIENTS, BOUNDS, METADATA, allowed_codes=SUPPORTED_OPTIMIZATION_CODES)
    coeff = pd.read_csv(COEFFICIENTS, index_col=0)
    bounds = pd.read_csv(BOUNDS).set_index("nutrient").loc[coeff.index]
    coefficient_codes = [int(code) for code in coeff.columns]
    baseline = pd.Series(current_profile, index=codes).reindex(coefficient_codes, fill_value=0.0).to_numpy(dtype=float)
    optimized = pd.Series(result.get("servings", {}), dtype=float).reindex(coefficient_codes).fillna(0.0).to_numpy(dtype=float)
    A = coeff.to_numpy(dtype=float)
    lb = bounds["lower_bound"].to_numpy(dtype=float)
    ub = bounds["upper_bound"].to_numpy(dtype=float)
    baseline_nutrients = A @ baseline
    optimized_nutrients = A @ optimized
    nutrient_names = coeff.index.tolist()
    # Explain the biggest changes using the actual baseline constraint violations
    # and each food group's signed contribution to those nutrients.
    violated = []
    for i, nutrient in enumerate(nutrient_names):
        if baseline_nutrients[i] < lb[i]:
            violated.append((i, "below", lb[i] - baseline_nutrients[i]))
        elif baseline_nutrients[i] > ub[i]:
            violated.append((i, "above", baseline_nutrients[i] - ub[i]))
    before = {str(code): float(servings[code]) for code in codes}
    after = {str(code): float(result.get("servings", {}).get(code, servings[code])) for code in codes}
    changes = []
    for code in codes:
        delta = after[str(code)] - before[str(code)]
        if abs(delta) >= 0.05:
            col_idx = coefficient_codes.index(code) if code in coefficient_codes else None
            helpful = []
            if col_idx is not None:
                for nutrient_idx, direction, magnitude in violated:
                    contribution = A[nutrient_idx, col_idx] * delta
                    improves = contribution > 1e-9 if direction == "below" else contribution < -1e-9
                    if improves:
                        helpful.append((magnitude, nutrient_names[nutrient_idx], direction))
            helpful.sort(reverse=True)
            if helpful:
                details = ", ".join(
                    f"{name} was below the dataset-derived lower bound" if direction == "below"
                    else f"{name} was above the dataset-derived upper bound"
                    for _, name, direction in helpful[:2]
                )
                reason = (
                    f"{'Increase' if delta > 0 else 'Reduce'} this food group because its modeled nutrient contribution "
                    f"moves the starting daily profile toward the source dataset's constraint range ({details})."
                )
            else:
                reason = (
                    "This adjustment is part of the solver's lowest-deviation feasible daily food-group profile; "
                    "it is not independently evidence of a clinical benefit for this food group."
                )
            changes.append({
                "food_group_code": code,
                "food_group": str(metadata.loc[code, "food_name"]),
                "current_servings": round(before[str(code)], 3),
                "suggested_servings": round(after[str(code)], 3),
                "change_servings": round(delta, 3),
                "serving_grams": grams_by_code[code],
                "approx_change_grams": round(delta * grams_by_code[code], 1),
                "reason": reason,
            })
    changes.sort(key=lambda x: abs(x["change_servings"]), reverse=True)
    return {
        "status": result.get("status", "unknown"),
        "target_definition": "Source-derived aggregate daily DASH nutrient bounds applied to mapped food-group servings",
        "servings_before": before,
        "servings_after": after,
        "changes": changes,
        "matched_foods": matched,
        "unmatched_foods": unmatched,
        "nutrient_totals": result.get("nutrients", {}),
        "baseline_nutrient_totals": dict(zip(nutrient_names, baseline_nutrients.tolist())),
        "constraint_bounds": {name: {"lower": float(lb[i]), "upper": float(ub[i])} for i, name in enumerate(nutrient_names)},
        "optimizer_diagnostics": {k: v for k, v in result.items() if k not in ("servings", "nutrients")},
        "ml_preference_model": ml_details,
        "limitations": [
            "Research prototype, not medical advice or a clinically validated individual diet.",
            "Food groups are assigned using a conservative keyword map; verify mappings and portions.",
            "Source coefficients and bounds describe aggregate daily food-group profiles, not individual meals.",
            "An experimental Ridge model predicts next-day observed food-group servings and blends that profile with current intake before optimization; it does not predict healthiness.",
            "A mathematical optimum may substantially change the original diet and may not reflect preferences, affordability, culture, or clinical restrictions."
        ],
    }
