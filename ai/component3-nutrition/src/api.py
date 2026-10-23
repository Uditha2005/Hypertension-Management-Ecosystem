"""Component 3 API: nutrient assessment plus separate daily DASH optimization research.
Meal assessment is reference-based; ML artifacts are for explicitly documented research targets."""
from __future__ import annotations
from datetime import date
import os
from typing import Any
from dotenv import load_dotenv
load_dotenv()
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, StrictFloat, StrictInt, StrictStr
try:
    from meal_plan_service import MealPlanValidationError, PlannedFoodSelection, resolve_meal_plan
    from usda_fooddata import (FoodSearchResult, USDAConfigurationError, USDAEmptySearchError,
        USDAFoodDataClient, USDAFoodDataError, USDARequestError)
    from meal_assessment import assess_meal
except ModuleNotFoundError:
    from .meal_plan_service import MealPlanValidationError, PlannedFoodSelection, resolve_meal_plan
    from .usda_fooddata import (FoodSearchResult, USDAConfigurationError, USDAEmptySearchError,
        USDAFoodDataClient, USDAFoodDataError, USDARequestError)
    from .meal_assessment import assess_meal

app = FastAPI(title="Component 3 — DASH-Informed Meal Assessment and Diet Optimization", version="4.0.0",
 description="Transparent nutrient-reference assessment, daily DASH optimization and separately evaluated ML research. Not a diagnostic service.")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000","http://127.0.0.1:3000"], allow_credentials=False,
 allow_methods=["GET","POST","OPTIONS"], allow_headers=["Content-Type","Authorization"])

class FoodSearchItem(BaseModel):
    fdc_id:int; description:str; data_type:str; serving_size:float|None=None; serving_size_unit:str|None=None
class FoodSearchResponse(BaseModel):
    query:str; count:int; foods:list[FoodSearchItem]
class PlannedFoodInput(BaseModel):
    day:StrictStr; fdc_id:StrictInt|StrictStr; quantity:StrictFloat|StrictInt=Field(gt=0); unit:StrictStr; meal:StrictStr|None=None
class PersonalProfile(BaseModel):
    age_years:float=Field(gt=18,lt=120)
    bmi:float|None=Field(default=None,gt=10,lt=100)
    sex_code:int|None=Field(default=None,ge=1,le=2, description="Optional NHANES-compatible sex code: 1 or 2; used only for the research ML estimate.")
    dietary_requirements:list[str]=Field(default_factory=list, description="User-reported dietary requirements; do not enter medication or diagnosis details.")
class MealPlanAnalysisRequest(BaseModel):
    entries:list[PlannedFoodInput]=Field(min_length=1)
    selected_days:list[str]=Field(min_length=1)
    personal_profile:PersonalProfile
    full_day_intake:bool=False
class NutrientSummaryResponse(BaseModel):
    sodium_mg:float|None; potassium_mg:float|None; energy_kcal:float|None; sat_fat_g:float|None; na_k_ratio:float|None
class MealPlanAnalysisResponse(BaseModel):
    selected_days:list[str]; daily_nutrients:dict[str,NutrientSummaryResponse]
    complete_plan_total:NutrientSummaryResponse; assessment_method:str
    meal_assessments:dict[str,dict[str,Any]]
    daily_ml_alignment_estimates:dict[str,dict[str,Any]]
    limitation:str
LIMITATION=("Nutrient totals cover only foods entered and may be affected by missing nutrient values. "
 "Meal concerns are assessed with transparent reference rules. The optional ML estimate is only appropriate when the entries represent the complete day's intake and all required nutrients are available. "
 "Its target is a rule-derived daily proxy, not expert-labelled meal suitability or clinical truth. This prototype is not a diagnosis or a personalised medical prescription.")
def get_usda_client()->USDAFoodDataClient: return USDAFoodDataClient(api_key=os.getenv("USDA_FDC_API_KEY"))
def canonical_date(value:str)->str:
    try: parsed=date.fromisoformat(value)
    except (TypeError,ValueError) as exc: raise HTTPException(status_code=422,detail="Dates must use YYYY-MM-DD format") from exc
    if parsed.isoformat()!=value: raise HTTPException(status_code=422,detail="Dates must use YYYY-MM-DD format")
    return value
def summary_dict(summary:Any)->dict[str,float|None]:
    return {key:getattr(summary,key) for key in ("sodium_mg","potassium_mg","energy_kcal","sat_fat_g","na_k_ratio",
        "protein_g","carbs_g","fiber_g","calcium_mg","magnesium_mg","vitamin_c_mg")}

def estimate_daily_alignment(summary:Any, age_years:float, sex_code:int|None)->dict[str,Any]:
    """Run the saved daily proxy classifier only on a complete daily food record."""
    model_path = _Path(__file__).resolve().parent.parent / "models" / "daily_reference_alignment_proxy.joblib"
    if not model_path.exists():
        return {"status":"unavailable","reason":"The trained proxy model file is missing."}
    values = {
        "DR1TPOTA": summary.potassium_mg,
        "DR1TFIBE": summary.fiber_g,
        "DR1TPROT": summary.protein_g,
        "DR1TCARB": summary.carbs_g,
        "DR1TCALC": summary.calcium_mg,
        "DR1TMAGN": summary.magnesium_mg,
        "DR1TVC": summary.vitamin_c_mg,
        "RIDAGEYR": age_years,
        "RIAGENDR": sex_code,
    }
    missing = [key for key, value in values.items() if value is None and key != "RIAGENDR"]
    if missing:
        return {"status":"unavailable","reason":"Required model input nutrient data are missing.",
                "missing_features":missing}
    try:
        import joblib, pandas as pd
        model = joblib.load(model_path)
        features = pd.DataFrame([values])
        predicted = str(model.predict(features)[0])
        probabilities = model.predict_proba(features)[0] if hasattr(model, "predict_proba") else None
        confidence = None
        if probabilities is not None:
            confidence = float(max(probabilities))
        return {
            "status":"estimated",
            "predicted_daily_alignment_proxy":predicted,
            "confidence":confidence,
            "model":"ExtraTrees (selected by participant-grouped cross-validation macro-F1)",
            "target_type":"rule-derived daily nutrient-reference alignment proxy",
            "explanation":"This ML estimate approximates a daily reference-alignment label learned from NHANES records. It is not a meal-suitability score, clinical prediction, or substitute for the nutrient-reference checks."
        }
    except Exception as exc:
        return {"status":"unavailable","reason":f"Model inference failed: {type(exc).__name__}"}
def food_item(food:FoodSearchResult)->FoodSearchItem:
    return FoodSearchItem(fdc_id=food.fdc_id,description=food.description,data_type=food.data_type,serving_size=food.serving_size,serving_size_unit=food.serving_size_unit)
class ImageFoodIdentificationRequest(BaseModel):
    image_data_url: StrictStr = Field(min_length=100, max_length=12_000_000)
    meal_context: str | None = Field(default=None, max_length=100)

class IdentifiedFood(BaseModel):
    food_name: str
    estimated_quantity_g: float = Field(gt=0, le=5000)
    confidence: str
    notes: str | None = None

class ImageFoodIdentificationResponse(BaseModel):
    foods: list[IdentifiedFood]
    message: str
    limitation: str

@app.post("/foods/identify-image", response_model=ImageFoodIdentificationResponse)
def identify_foods_from_image(request: ImageFoodIdentificationRequest) -> ImageFoodIdentificationResponse:
    """Use a separate vision-capable service to suggest foods; user must confirm before nutrition lookup."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="Photo recognition is not configured. Add GEMINI_API_KEY to the API environment, or use manual food search below.")
    image_data_url = request.image_data_url.strip()
    if not image_data_url.startswith(("data:image/jpeg;base64,", "data:image/png;base64,", "data:image/webp;base64,")):
        raise HTTPException(status_code=422, detail="Upload a JPG, PNG, or WEBP image.")
    import base64, binascii, requests
    try:
        encoded = image_data_url.split(",", 1)[1]
        raw = base64.b64decode(encoded, validate=True)
    except (IndexError, binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail="The uploaded image could not be read.") from exc
    if len(raw) > 8 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Please upload an image smaller than 8 MB.")
    prompt = ("Identify visible foods in this dish photo. Return JSON only with a foods array. "
              "Each item must have food_name (plain recognizable food name), estimated_quantity_g (rough edible portion estimate in grams), "
              "confidence (high, medium, or low), and notes (uncertainty such as hidden ingredients). "
              "Do not claim to know hidden ingredients, oil, salt, sauces, or exact weight from the image. "
              "If uncertain, give a conservative estimate and say so in notes. Maximum 12 visible food items. "
              f"Meal context: {request.meal_context or 'not specified'}. "
              "Use an empty foods array if no food is visible.")
    try:
        mime_type = image_data_url[5:].split(";", 1)[0].lower()
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{os.getenv('GEMINI_VISION_MODEL', 'gemini-2.5-flash')}:generateContent",
            params={"key": api_key}, timeout=45,
            headers={"Content-Type": "application/json"},
            json={"contents": [{"role": "user", "parts": [
                      {"text": prompt},
                      {"inline_data": {"mime_type": mime_type, "data": encoded}}
                  ]}],
                  "generationConfig": {"temperature": 0, "responseMimeType": "application/json"}})
        response.raise_for_status()
        content = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        import json
        parsed = json.loads(content)
        raw_foods = parsed.get("foods", [])
        foods = []
        for item in raw_foods[:12]:
            name = str(item.get("food_name", "")).strip()[:120]
            try: grams = float(item.get("estimated_quantity_g", 100))
            except (TypeError, ValueError): grams = 100.0
            if name and grams > 0:
                foods.append(IdentifiedFood(food_name=name, estimated_quantity_g=min(grams,5000),
                    confidence=str(item.get("confidence", "low")).lower() if str(item.get("confidence", "low")).lower() in ("high","medium","low") else "low",
                    notes=str(item.get("notes", "Photo-based estimate; please confirm portion and ingredients."))[:300] or None))
        return ImageFoodIdentificationResponse(foods=foods,
            message="Review the suggested foods and portions. Choose the closest USDA record for each item before calculating nutrition.",
            limitation="Photo recognition and portion sizes are estimates. The image may not reveal hidden ingredients, oil, salt, sauces, or exact weight. Confirm and edit every item before nutrition is calculated.")
    except requests.HTTPError as exc:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=502, detail="The photo-recognition service returned an error. Check the API key and try again.") from exc
    except (requests.RequestException, KeyError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=502, detail="Could not identify foods from this image. Try another clear photo or use food search.") from exc

@app.get("/health")
def health()->dict[str,Any]:
    proxy_model = _Path(__file__).resolve().parent.parent / "models" / "daily_reference_alignment_proxy.joblib"
    dash_model = _Path(__file__).resolve().parent.parent / "research" / "dash_servings" / "results" / "training" / "selected_food_group_preference_model.joblib"
    return {"status":"ok","service":"component3-nutrition-api",
            "meal_assessment":"transparent_nutrient_reference_rules",
            "photo_food_identification_available":bool(os.getenv("GEMINI_API_KEY")),
            "main_flow_ml_estimate":"optional_daily_reference_alignment_proxy_when_full_day_confirmed",
            "ml_research":{"daily_reference_alignment_proxy_model_available":proxy_model.exists(),
                           "daily_food_group_preference_model_available":dash_model.exists()}}
@app.get("/foods/search",response_model=FoodSearchResponse)
def search_foods(query:str=Query(...,min_length=1,max_length=200),limit:int=Query(10,ge=1,le=50),client:USDAFoodDataClient=Depends(get_usda_client))->FoodSearchResponse:
    if not query.strip(): raise HTTPException(status_code=422,detail="query must not be blank")
    try: foods=client.search_foods(query.strip(),page_size=limit)
    except USDAEmptySearchError as exc: raise HTTPException(status_code=404,detail="No matching USDA foods were found") from exc
    except USDAConfigurationError as exc: raise HTTPException(status_code=503,detail="USDA service is not configured") from exc
    except USDARequestError as exc: raise HTTPException(status_code=502,detail="USDA food search is temporarily unavailable") from exc
    except USDAFoodDataError as exc: raise HTTPException(status_code=502,detail="USDA returned an unusable food record") from exc
    return FoodSearchResponse(query=query.strip(),count=len(foods),foods=[food_item(f) for f in foods])
@app.post("/meal-plans/analyze",response_model=MealPlanAnalysisResponse)
def analyze_meal_plan(request:MealPlanAnalysisRequest,client:USDAFoodDataClient=Depends(get_usda_client))->MealPlanAnalysisResponse:
    days=[canonical_date(d) for d in request.selected_days]
    if len(set(days))!=len(days): raise HTTPException(status_code=422,detail="selected_days must not contain duplicates")
    entries=[PlannedFoodSelection(day=canonical_date(e.day),fdc_id=e.fdc_id,quantity=e.quantity,unit=e.unit) for e in request.entries]
    missing=sorted({e.day for e in entries}-set(days))
    if missing: raise HTTPException(status_code=422,detail=f"Food entry date(s) not in selected_days: {', '.join(missing)}")
    try: summary=resolve_meal_plan(entries,client)
    except MealPlanValidationError as exc: raise HTTPException(status_code=422,detail=str(exc)) from exc
    except USDAConfigurationError as exc: raise HTTPException(status_code=503,detail="USDA service is not configured") from exc
    except USDARequestError as exc: raise HTTPException(status_code=502,detail="USDA food data is temporarily unavailable") from exc
    except USDAFoodDataError as exc: raise HTTPException(status_code=502,detail="USDA returned an unusable food record") from exc
    daily={d:summary.daily.get(d) for d in days}
    absent=[d for d,v in daily.items() if v is None]
    if absent: raise HTTPException(status_code=422,detail=f"Add at least one food for each selected day: {', '.join(absent)}")
    ml_estimates={}
    for d, daily_summary in daily.items():
        if request.full_day_intake:
            ml_estimates[d]=estimate_daily_alignment(daily_summary, request.personal_profile.age_years, request.personal_profile.sex_code)
        else:
            ml_estimates[d]={"status":"not_requested","reason":"Tick the complete-day option only if the foods entered cover the full day's intake."}
    # Group entries by actual meal for transparent nutrient-reference assessment.
    profile=request.personal_profile.model_dump()
    grouped:dict[tuple[str,str],list[PlannedFoodSelection]]={}
    for entry in request.entries:
        day=canonical_date(entry.day); meal=(entry.meal or "Unspecified meal").strip() or "Unspecified meal"
        grouped.setdefault((day,meal),[]).append(PlannedFoodSelection(day=day,fdc_id=entry.fdc_id,quantity=entry.quantity,unit=entry.unit))
    meal_assessments={}
    for (day,meal), meal_entries in grouped.items():
        key=f"{day} | {meal}"
        try:
            meal_summary=resolve_meal_plan(meal_entries,client)
            meal_nutrients=meal_summary.daily[day]
            row=summary_dict(meal_nutrients)
            row.update({"age_years":profile["age_years"],"bmi":profile["bmi"],
                        "dietary_requirements":", ".join(sorted(profile["dietary_requirements"])) or "unspecified"})
            meal_assessments[key]=assess_meal(row, profile["dietary_requirements"])
        except (ValueError, KeyError) as exc:
            raise HTTPException(status_code=422, detail=f"Unable to assess meal {key}: {exc}") from exc
    return MealPlanAnalysisResponse(selected_days=days,daily_nutrients={d:summary_dict(v) for d,v in daily.items()},
      complete_plan_total=summary_dict(summary.total),assessment_method="nutrient_calculation_plus_reference_rules_plus_optional_daily_ml_proxy",
      meal_assessments=meal_assessments, daily_ml_alignment_estimates=ml_estimates, limitation=LIMITATION)


# Research-only daily DASH food-group optimization endpoint. The underlying target is
# observed daily food-group servings, not a meal-suitability label or clinical outcome.
from pathlib import Path as _Path
from pydantic import BaseModel as _BaseModel, Field as _Field
class DashOptimizationRequest(_BaseModel):
    age_years: float = _Field(gt=18, lt=120)
    sex_code: int = _Field(ge=1, le=2, description="NHANES coding: 1 or 2")
    self_reported_hypertension: bool
class DashOptimizationResponse(_BaseModel):
    status: str
    target_definition: str
    servings_before: dict[str, float] | None = None
    servings_after: dict[str, float] | None = None
    nutrient_totals: dict[str, float] | None = None
    optimizer_diagnostics: dict[str, Any] | None = None
    limitation: str
DASH_ROOT = _Path(__file__).resolve().parent.parent / "research" / "dash_servings"
DASH_RESULTS = DASH_ROOT / "results"
DASH_MODEL = DASH_RESULTS / "training" / "selected_food_group_preference_model.joblib"
DASH_LIMITATION = ("Research prototype only. It predicts observed daily food-group servings from age, sex and "
                   "self-reported hypertension, then projects that profile against the supplied daily aggregate "
                   "nutrient constraints. It does not predict whether an individual meal is suitable and is not medical advice.")
@app.post("/dash/optimize-daily-pattern", response_model=DashOptimizationResponse)
def optimize_daily_pattern(request: DashOptimizationRequest) -> DashOptimizationResponse:
    if not DASH_MODEL.exists():
        raise HTTPException(status_code=503, detail="The daily food-pattern research model is not trained. Run the research training script first.")
    try:
        import joblib, pandas as pd
        try:
            from dash_optimizer import optimize_servings
        except ModuleNotFoundError:
            from .research.dash_servings.src.dash_optimizer import optimize_servings
        model = joblib.load(DASH_MODEL)
        features = pd.DataFrame([{"RIDAGEYR": request.age_years, "RIAGENDR": request.sex_code,
                                  "hypertension_reported": int(request.self_reported_hypertension)}])
        values = model.predict(features)[0]
        import numpy as np
        values = np.maximum(values, 0)
        coeff = DASH_RESULTS / "nutrient_coefficients.csv"
        bounds = DASH_RESULTS / "dash_nutrient_bounds.csv"
        meta = DASH_RESULTS / "food_group_metadata.csv"
        if not (coeff.exists() and bounds.exists() and meta.exists()):
            raise HTTPException(status_code=503, detail="DASH constraint parameter files are missing.")
        optimized = optimize_servings(values, coeff, bounds, meta)
        if not optimized.get("success"):
            return DashOptimizationResponse(status=optimized.get("status","optimization_warning"),
                target_definition="Average observed servings per food group across NHANES dietary Day 1 and Day 2",
                servings_before={str(k):float(v) for k,v in zip(pd.read_csv(coeff,index_col=0).columns,values)},
                servings_after={str(k):float(v) for k,v in optimized.get("servings",{}).items()}, nutrient_totals={str(k):float(v) for k,v in optimized.get("nutrients",{}).items()},
                optimizer_diagnostics=optimized, limitation=DASH_LIMITATION)
        return DashOptimizationResponse(status="ok",
            target_definition="Average observed servings per food group across NHANES dietary Day 1 and Day 2",
            servings_before={str(k):float(v) for k,v in zip(pd.read_csv(coeff,index_col=0).columns,values)},
            servings_after={str(k):float(v) for k,v in optimized["servings"].items()}, nutrient_totals={str(k):float(v) for k,v in optimized["nutrients"].items()},
            optimizer_diagnostics={k:v for k,v in optimized.items() if k not in ("servings","nutrients")},
            limitation=DASH_LIMITATION)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Daily-pattern optimization failed: {type(exc).__name__}: {exc}") from exc
