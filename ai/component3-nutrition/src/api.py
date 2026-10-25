"""Component 3 API: nutrient assessment plus separate daily DASH optimization research.
Meal assessment is reference-based; ML artifacts are for explicitly documented research targets."""
from __future__ import annotations
from datetime import date
import os
import logging
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
    from recommendation_service import build_suggestions, screen_medication_precautions
    from food_alternatives import find_food_alternatives
except ModuleNotFoundError:
    from .meal_plan_service import MealPlanValidationError, PlannedFoodSelection, resolve_meal_plan
    from .usda_fooddata import (FoodSearchResult, USDAConfigurationError, USDAEmptySearchError,
        USDAFoodDataClient, USDAFoodDataError, USDARequestError)
    from .meal_assessment import assess_meal
    from .recommendation_service import build_suggestions, screen_medication_precautions
    from .food_alternatives import find_food_alternatives
try:
    from meal_record_store import save_meal_record, list_meal_records, save_feedback, list_feedback
except ModuleNotFoundError:
    from .meal_record_store import save_meal_record, list_meal_records, save_feedback, list_feedback


logger = logging.getLogger("component3_nutrition")
try:
    from foodseg103_inference import FoodSeg103Inference
except ModuleNotFoundError:
    from .foodseg103_inference import FoodSeg103Inference
_foodseg103 = FoodSeg103Inference()

app = FastAPI(title="Component 3 — DASH-Informed Meal Assessment and Diet Optimization", version="4.0.0",
 description="Transparent nutrient-reference assessment, daily DASH optimization and separately evaluated ML research. Not a diagnostic service.")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000","http://127.0.0.1:3000"], allow_credentials=False,
 allow_methods=["GET","POST","PUT","OPTIONS"], allow_headers=["Content-Type","Authorization"])

class FoodSearchItem(BaseModel):
    fdc_id:int; description:str; data_type:str; serving_size:float|None=None; serving_size_unit:str|None=None
class FoodSearchResponse(BaseModel):
    query:str; count:int; foods:list[FoodSearchItem]
class FoodDetailsResponse(BaseModel):
    fdc_id:int; description:str; data_type:str
    reference_quantity:float; reference_unit:str
    serving_size:float|None=None; serving_size_unit:str|None=None
    supported_units:list[str]
class PlannedFoodInput(BaseModel):
    day:StrictStr; fdc_id:StrictInt|StrictStr; quantity:StrictFloat|StrictInt=Field(gt=0,le=100000); unit:StrictStr; meal:StrictStr|None=None; description:StrictStr|None=None
class PersonalProfile(BaseModel):
    age_years:float=Field(gt=18,lt=120)
    bmi:float|None=Field(default=None,gt=10,lt=100)
    sex_code:int|None=Field(default=None,ge=1,le=2, description="Optional NHANES-compatible sex code: 1 or 2; used only for the research ML estimate.")
    dietary_requirements:list[str]=Field(default_factory=list, description="User-reported dietary requirements; do not enter medication or diagnosis details.")
    dietary_preferences:list[str]=Field(default_factory=list)
    dietary_restrictions:list[str]=Field(default_factory=list)
    allergies:list[str]=Field(default_factory=list)
    preferred_foods:list[str]=Field(default_factory=list)
    nutrition_goal:str|None=None
    confirmed_medications:list[str]=Field(default_factory=list, description="Optional manually confirmed active ingredients for prototype interaction screening; unverified OCR text must not be entered.")
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
class _UnconfiguredUSDAClient:
    def search_foods(self, query:str, *, page_size:int=25):
        raise USDAConfigurationError("USDA_FDC_API_KEY is missing or blank")
    def get_food(self, fdc_id:int|str):
        raise USDAConfigurationError("USDA_FDC_API_KEY is missing or blank")

def get_usda_client()->USDAFoodDataClient:
    try:
        return USDAFoodDataClient(api_key=os.getenv("USDA_FDC_API_KEY"))
    except USDAConfigurationError:
        # Defer the 503 until after request-shape/date validation in the route.
        return _UnconfiguredUSDAClient()  # type: ignore[return-value]
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
    if not api_key and not _foodseg103.available:
        raise HTTPException(status_code=503, detail="Photo recognition is not configured. Train/deploy the local FoodSeg103 model or add GEMINI_API_KEY to the API environment, or use manual food search below.")
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

    # Prefer the locally trained FoodSeg103 model when its checkpoint is installed.
    # This keeps photo recognition available without an external vision API key.
    if _foodseg103.available:
        try:
            result = _foodseg103.predict_data_url(image_data_url)
            return ImageFoodIdentificationResponse(
                foods=[IdentifiedFood(**food) for food in result["foods"]],
                message=result["message"],
                limitation=result["limitation"],
            )
        except Exception as exc:
            logger.exception("Local FoodSeg103 inference failed")
            if not os.getenv("GEMINI_API_KEY"):
                raise HTTPException(status_code=503, detail=(
                    "The local FoodSeg103 checkpoint exists but inference failed. Check the model checkpoint and PyTorch installation. "
                    f"Failure type: {type(exc).__name__}."
                )) from exc
            logger.warning("Falling back to configured Gemini vision service after local inference failure.")

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

def recommendation_engine_status() -> dict[str, Any]:
    """Report what is actually wired into the live nutrition flow."""
    component_root = _Path(__file__).resolve().parent.parent
    proxy_model = component_root / "models" / "daily_reference_alignment_proxy.joblib"
    dash_coefficients = component_root / "research" / "dash_servings" / "results" / "nutrient_coefficients.csv"
    dash_bounds = component_root / "research" / "dash_servings" / "results" / "dash_nutrient_bounds.csv"
    dash_metadata = component_root / "research" / "dash_servings" / "results" / "food_group_metadata.csv"
    dash_model = component_root / "research" / "dash_servings" / "models" / "dash_next_day_preference_ridge.joblib"
    dash_ready = all(p.exists() for p in (dash_coefficients, dash_bounds, dash_metadata))
    return {
        "live_suggestion_engine": "removed",
        "trained_model_connected_to_live_suggestions": False,
        "dash_ml_model_file_present": dash_model.exists(),
        "dash_ml_model_used_by_daily_optimizer": True,
        "daily_reference_alignment_proxy_model_file_present": proxy_model.exists(),
        "daily_reference_alignment_proxy_used_only_for_complete_day_estimate": True,
        "dash_optimizer_data_ready": dash_ready,
        "dash_optimizer_is_separate_endpoint_not_live_meal_suggestion_engine": True,
    }

@app.on_event("startup")
def log_recommendation_engine_status() -> None:
    status = recommendation_engine_status()
    logger.warning("========== COMPONENT 3 ENGINE DIAGNOSTICS ==========")
    logger.warning("LIVE MEAL-SUGGESTION CARDS: REMOVED")
    logger.warning("DASH OPTIMIZER: separate daily recommendation endpoint")
    logger.warning("DASH ML MODEL FILE PRESENT: %s", status["dash_ml_model_file_present"])
    logger.warning("DASH OPTIMIZER DATA READY: %s", status["dash_optimizer_data_ready"])
    logger.warning("ML model use is reported per /dash/optimize-current-day response; startup file presence alone does not prove inference succeeded.")
    logger.warning("====================================================")

@app.get("/health")
def health()->dict[str,Any]:
    local_food_model = _foodseg103.available
    return {"status":"ok","service":"component3-nutrition-api",
            "photo_food_identification_available":bool(local_food_model or os.getenv("GEMINI_API_KEY")),
            "photo_food_identification_method":("local_foodseg103" if local_food_model else "gemini" if os.getenv("GEMINI_API_KEY") else "unconfigured"),
            "foodseg103_checkpoint_available":local_food_model,
            "foodseg103_checkpoint_path":str(_foodseg103.checkpoint_path),
            "daily_dash_optimizer_available":recommendation_engine_status()["dash_optimizer_data_ready"],
            "recommendation_engine": recommendation_engine_status()}

class MealRecordCreate(BaseModel):
    analysis: dict[str, Any]
    meal_date: str = Field(min_length=10, max_length=10)
    meals: list[dict[str, Any]] = Field(default_factory=list, max_length=100)

class RecommendationFeedbackRequest(BaseModel):
    suggestion_title: StrictStr = Field(min_length=1, max_length=160)
    rating: StrictStr = Field(pattern="^(helpful|not_helpful|tried)$")
    comment: StrictStr = Field(default="", max_length=1000)

@app.post("/meal-records")
def create_meal_record(request: MealRecordCreate, profile_id: str = Query("local-demo", min_length=1, max_length=80)) -> dict[str, Any]:
    """Persist an analysis for history; profile_id must be authenticated in production."""
    canonical_date(request.meal_date)
    try:
        record = save_meal_record(profile_id, request.model_dump())
        return {"record": record, "storage": "local_json"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Meal history storage unavailable ({type(exc).__name__}).") from exc

@app.get("/meal-records")
def read_meal_records(profile_id: str = Query("local-demo", min_length=1, max_length=80), limit: int = Query(30, ge=1, le=100)) -> dict[str, Any]:
    try:
        return {"records": list_meal_records(profile_id, limit), "storage": "local_json"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Meal history storage unavailable ({type(exc).__name__}).") from exc

@app.get("/nutrition-context")
def read_nutrition_context(profile_id: str = Query("local-demo", min_length=1, max_length=80), days: int = Query(7, ge=1, le=90)) -> dict[str, Any]:
    """Summarize recorded intake context; never infer unlogged foods or missing nutrients."""
    try:
        records = list_meal_records(profile_id, 100)
        feedback = list_feedback(profile_id, 2000)
        from datetime import date, timedelta
        cutoff = date.today() - timedelta(days=days - 1)
        recent = []
        daily: dict[str, dict[str, Any]] = {}
        # list_meal_records returns newest records first. Each saved analysis may
        # cover a whole multi-meal plan, so selecting the latest analysis per day
        # avoids double-counting the same plan when a user recalculates it.
        for record in records:
            record_date = str(record.get("meal_date", ""))[:10]
            try:
                parsed = date.fromisoformat(record_date)
            except ValueError:
                continue
            if parsed < cutoff or parsed > date.today():
                continue
            recent.append(record)
            analysis = record.get("analysis", {}) or {}
            nutrients = analysis.get("daily_nutrients", {}) or {}
            for day_key, summary in nutrients.items():
                key = str(day_key)[:10]
                try:
                    nutrient_date = date.fromisoformat(key)
                except ValueError:
                    continue
                if nutrient_date < cutoff or nutrient_date > date.today() or key in daily:
                    continue
                if not isinstance(summary, dict):
                    continue
                normalized = {"records": 1}
                for field in ("sodium_mg", "potassium_mg", "energy_kcal", "sat_fat_g", "fiber_g"):
                    value = summary.get(field)
                    try:
                        number = float(value)
                        normalized[field] = round(number, 2) if number >= 0 and number < float("inf") else None
                    except (TypeError, ValueError):
                        normalized[field] = None
                daily[key] = normalized
        counts = {key: sum(1 for item in feedback if item.get("rating") == key) for key in ("helpful", "not_helpful", "tried")}
        return {"days": days, "record_count": len(recent), "feedback_count": len(feedback), "feedback_counts": counts, "daily_recorded_nutrients": daily, "records": recent, "limitation": "Only saved records in this profile are included. The latest saved analysis per date is shown to avoid double-counting recalculations. Missing nutrient values remain unavailable; totals are not guaranteed complete daily intake and are not clinical assessments."}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Nutrition context unavailable ({type(exc).__name__}).") from exc

@app.get("/recommendation-feedback")
def read_recommendation_feedback(profile_id: str = Query("local-demo", min_length=1, max_length=80), limit: int = Query(100, ge=1, le=1000)) -> dict[str, Any]:
    try:
        items = list_feedback(profile_id, limit)
        return {"feedback": items, "count": len(items)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Feedback storage unavailable ({type(exc).__name__}).") from exc

@app.post("/meal-records/{record_id}/feedback")
def create_recommendation_feedback(request: RecommendationFeedbackRequest, record_id: str, profile_id: str = Query("local-demo", min_length=1, max_length=80)) -> dict[str, Any]:
    try:
        feedback = save_feedback(profile_id, record_id, request.suggestion_title, request.rating, request.comment)
        return {"feedback": feedback, "storage": "local_json"}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Feedback storage unavailable ({type(exc).__name__}).") from exc

class FoodAlternativesRequest(BaseModel):
    fdc_id: StrictInt | StrictStr
    quantity_unit: StrictStr = "g"
    limit: int = Field(default=5, ge=1, le=10)

@app.post("/foods/alternatives")
def food_alternatives(request: FoodAlternativesRequest, client: USDAFoodDataClient = Depends(get_usda_client)):
    unit = request.quantity_unit.casefold().strip()
    if unit not in {"g", "kg", "serving", "servings"}:
        raise HTTPException(status_code=422, detail="quantity_unit must be g, kg, or serving")
    try:
        return find_food_alternatives(client, int(request.fdc_id), unit, request.limit)
    except USDAConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except USDAEmptySearchError:
        raise HTTPException(status_code=404, detail="No compatible alternative records found")
    except USDAFoodDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

@app.get("/foods/search",response_model=FoodSearchResponse)
def search_foods(query:str=Query(...,min_length=1,max_length=200),limit:int=Query(10,ge=1,le=50),client:USDAFoodDataClient=Depends(get_usda_client))->FoodSearchResponse:
    if not query.strip(): raise HTTPException(status_code=422,detail="query must not be blank")
    try: foods=client.search_foods(query.strip(),page_size=limit)
    except USDAEmptySearchError as exc: raise HTTPException(status_code=404,detail="No matching USDA foods were found") from exc
    except USDAConfigurationError as exc: raise HTTPException(status_code=503,detail="USDA service is not configured") from exc
    except USDARequestError as exc: raise HTTPException(status_code=502,detail="USDA food search is temporarily unavailable") from exc
    except USDAFoodDataError as exc: raise HTTPException(status_code=502,detail="USDA returned an unusable food record") from exc
    return FoodSearchResponse(query=query.strip(),count=len(foods),foods=[food_item(f) for f in foods])
@app.get("/foods/{fdc_id}/details", response_model=FoodDetailsResponse)
def food_details(fdc_id:int, client:USDAFoodDataClient=Depends(get_usda_client))->FoodDetailsResponse:
    """Return the actual nutrient reference basis before the UI enables quantity units."""
    try:
        record=client.get_food(fdc_id)
    except USDAConfigurationError as exc:
        raise HTTPException(status_code=503,detail="USDA service is not configured") from exc
    except USDARequestError as exc:
        raise HTTPException(status_code=502,detail="USDA food data is temporarily unavailable") from exc
    except USDAFoodDataError as exc:
        raise HTTPException(status_code=422,detail="This USDA record has no usable nutrient reference basis. Choose another record.") from exc
    supported=["serving"] if record.reference_unit == "serving" else ["g","kg"]
    if record.reference_unit == "serving" and (record.serving_size_unit or "").casefold().strip()=="g" and record.serving_size:
        supported=["serving","g","kg"]
    return FoodDetailsResponse(fdc_id=record.fdc_id,description=record.description,data_type=record.data_type,
        reference_quantity=record.reference_quantity,reference_unit=record.reference_unit,
        serving_size=record.serving_size,serving_size_unit=record.serving_size_unit,supported_units=supported)

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
            assessment=assess_meal(row, profile["dietary_requirements"])
            food_names=[(e.description or "") for e in request.entries if canonical_date(e.day)==day and (e.meal or "Unspecified meal").strip()==meal]
            assessment["suggestions"]=build_suggestions(food_names, row, meal_name=meal, personal_profile=profile)
            logger.info("[LIVE SUGGESTIONS] day=%s meal=%s engine=RULE_BASED count=%d",
                        day, meal, len(assessment["suggestions"]))
            assessment["medication_precautions"]=screen_medication_precautions(profile.get("confirmed_medications", []), food_names)
            meal_assessments[key]=assessment
        except (ValueError, KeyError) as exc:
            raise HTTPException(status_code=422, detail=f"Unable to assess meal {key}: {exc}") from exc
    return MealPlanAnalysisResponse(selected_days=days,daily_nutrients={d:summary_dict(v) for d,v in daily.items()},
      complete_plan_total=summary_dict(summary.total),assessment_method="nutrient_calculation_plus_reference_rules_plus_optional_daily_ml_proxy",
      meal_assessments=meal_assessments, daily_ml_alignment_estimates=ml_estimates, limitation=LIMITATION)


# Current-plan DASH optimizer: this operates on one complete day of user-entered foods.
from pathlib import Path as _Path

class DashFoodEntry(BaseModel):
    food_name: str = Field(min_length=1, max_length=240)
    quantity_grams: float = Field(gt=0, le=20000)

class DashCurrentDayOptimizationRequest(BaseModel):
    items: list[DashFoodEntry] = Field(min_length=1, max_length=200)

@app.post("/dash/optimize-current-day")
def optimize_current_day(request: DashCurrentDayOptimizationRequest) -> dict[str, Any]:
    """Project entered daily foods to mapped food-group servings and optimize the daily pattern."""
    import time
    started = time.perf_counter()
    try:
        try:
            from dash_recommendation import optimize_daily_food_entries
        except ModuleNotFoundError:
            from .dash_recommendation import optimize_daily_food_entries
        logger.info("[DASH OPTIMIZER] request received; items=%d; attempting daily food-group optimization",
                    len(request.items))
        result = optimize_daily_food_entries([item.model_dump() for item in request.items])
        ml_info = result.get("ml_preference_model") or {}
        logger.info(
            "[DASH OPTIMIZER] completed status=%s matched_foods=%d unmatched_foods=%d changes=%d "
            "ml_model_used=%s ml_model=%s duration_seconds=%.2f",
            result.get("status", "unknown"), len(result.get("matched_foods", [])),
            len(result.get("unmatched_foods", [])), len(result.get("changes", [])),
            ml_info.get("used", False), ml_info.get("model"),
            time.perf_counter() - started,
        )
        if not result.get("matched_foods"):
            raise HTTPException(status_code=422, detail={
                "message": "None of the entered foods could be mapped to the DASH food-group catalogue.",
                "unmatched_foods": result.get("unmatched_foods", [])
            })
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("[DASH OPTIMIZER] FAILED: %s: %s", type(exc).__name__, exc)
        raise HTTPException(status_code=500, detail=f"Current-day DASH optimization failed: {type(exc).__name__}: {exc}") from exc
