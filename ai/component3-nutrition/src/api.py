"""FastAPI endpoints for Component 3 meal-plan nutrition analysis.

The API wraps existing Component 3 services; it does not duplicate nutrient
aggregation or classifier feature engineering. Classifier output is research
only and is not a diagnosis or validated prediction of future blood pressure.
"""

from __future__ import annotations
from dotenv import load_dotenv

load_dotenv()

import logging
import os
from datetime import date
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, StrictFloat, StrictInt, StrictStr

try:
    from meal_plan_classifier_features import build_classifier_features
    from meal_plan_service import MealPlanValidationError, PlannedFoodSelection, resolve_meal_plan
    from predict_bp_category import BPCategoryPrediction, predict_bp_category
    from usda_fooddata import (
        FoodSearchResult,
        USDAConfigurationError,
        USDAEmptySearchError,
        USDAFoodDataClient,
        USDAFoodDataError,
        USDARequestError,
    )
except ModuleNotFoundError:
    from .meal_plan_classifier_features import build_classifier_features
    from .meal_plan_service import MealPlanValidationError, PlannedFoodSelection, resolve_meal_plan
    from .predict_bp_category import BPCategoryPrediction, predict_bp_category
    from .usda_fooddata import (
        FoodSearchResult,
        USDAConfigurationError,
        USDAEmptySearchError,
        USDAFoodDataClient,
        USDAFoodDataError,
        USDARequestError,
    )

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Component 3 — Hypertension Dietary Risk Assessment API",
    version="1.0.0",
    description=(
        "Research prototype for planned-meal nutrient summaries and experimental "
        "BP-associated classification. Not a medical diagnostic service."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


class FoodSearchItem(BaseModel):
    fdc_id: int
    description: str
    data_type: str
    serving_size: float | None = None
    serving_size_unit: str | None = None


class FoodSearchResponse(BaseModel):
    query: str
    count: int
    foods: list[FoodSearchItem]


class PlannedFoodInput(BaseModel):
    day: StrictStr = Field(..., description="Planned date in YYYY-MM-DD format")
    fdc_id: StrictInt | StrictStr = Field(..., description="Explicit USDA FoodData Central ID")
    quantity: StrictFloat | StrictInt = Field(..., ge=0, description="Quantity expressed in unit")
    unit: StrictStr = Field(..., description="Supported unit: g, kg, or serving")


class MealPlanAnalysisRequest(BaseModel):
    entries: list[PlannedFoodInput] = Field(..., min_length=1)
    selected_days: list[str] = Field(..., min_length=1)
    age: StrictFloat | StrictInt = Field(..., ge=18, le=80)
    sex_female: StrictInt = Field(..., ge=0, le=1)
    bmi: StrictFloat | StrictInt = Field(..., gt=0)


class NutrientSummaryResponse(BaseModel):
    sodium_mg: float | None
    potassium_mg: float | None
    energy_kcal: float | None
    sat_fat_g: float | None
    na_k_ratio: float | None


class PredictionResponse(BaseModel):
    predicted_class_id: int
    predicted_category: str
    probabilities: dict[str, float]
    experimental_result: str


class MealPlanAnalysisResponse(BaseModel):
    selected_days: list[str]
    daily_nutrients: dict[str, NutrientSummaryResponse]
    complete_plan_total: NutrientSummaryResponse
    classifier_features: dict[str, float]
    prediction: PredictionResponse
    limitation: str


LIMITATION_TEXT = (
    "Experimental research output only. This is not a diagnosis or a validated "
    "prediction of future blood pressure. The classifier was trained on observed "
    "NHANES dietary recalls; planned-meal inputs have not been clinically validated "
    "and are not established as equivalent to observed recalls."
)


def get_usda_client() -> USDAFoodDataClient:
    """Construct a client lazily so health checks and API imports need no key."""
    return USDAFoodDataClient(api_key=os.getenv("USDA_FDC_API_KEY"))


def _canonical_date(value: str, field_name: str) -> str:
    if not isinstance(value, str) or value != value.strip():
        raise HTTPException(status_code=422, detail=f"{field_name} must use YYYY-MM-DD format")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=f"{field_name} must be a real YYYY-MM-DD date") from error
    if parsed.isoformat() != value:
        raise HTTPException(status_code=422, detail=f"{field_name} must use canonical YYYY-MM-DD format")
    return value


def _summary_dict(summary: Any) -> dict[str, float | None]:
    return {
        "sodium_mg": summary.sodium_mg,
        "potassium_mg": summary.potassium_mg,
        "energy_kcal": summary.energy_kcal,
        "sat_fat_g": summary.sat_fat_g,
        "na_k_ratio": summary.na_k_ratio,
    }


def _food_search_item(food: FoodSearchResult) -> FoodSearchItem:
    return FoodSearchItem(
        fdc_id=food.fdc_id,
        description=food.description,
        data_type=food.data_type,
        serving_size=food.serving_size,
        serving_size_unit=food.serving_size_unit,
    )


@app.exception_handler(USDAConfigurationError)
async def usda_configuration_exception_handler(request: Request, exc: USDAConfigurationError) -> JSONResponse:
    logger.warning("USDA configuration unavailable for %s %s", request.method, request.url.path)
    return JSONResponse(status_code=503, content={"detail": "USDA service is not configured"})


@app.exception_handler(USDARequestError)
async def usda_request_exception_handler(request: Request, exc: USDARequestError) -> JSONResponse:
    logger.warning("USDA request failed for %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(status_code=502, content={"detail": "USDA food data is temporarily unavailable"})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Log server errors without exposing stack traces or secrets to clients."""
    logger.exception("Unhandled API error for %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Health check does not depend on USDA or the model artifact."""
    return {"status": "ok", "service": "component3-nutrition-api"}


@app.get("/foods/search", response_model=FoodSearchResponse, tags=["foods"])
def search_foods(
    query: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(10, ge=1, le=50),
    client: USDAFoodDataClient = Depends(get_usda_client),
) -> FoodSearchResponse:
    """Search USDA candidates; the caller must explicitly select a food ID."""
    if not query.strip():
        raise HTTPException(status_code=422, detail="query must not be blank")
    try:
        foods = client.search_foods(query.strip(), page_size=limit)
    except USDAEmptySearchError as error:
        raise HTTPException(status_code=404, detail="No matching USDA foods were found") from error
    except USDAConfigurationError as error:
        raise HTTPException(status_code=503, detail="USDA service is not configured") from error
    except USDARequestError as error:
        logger.warning("USDA search request failed: %s", error)
        raise HTTPException(status_code=502, detail="USDA food search is temporarily unavailable") from error
    except USDAFoodDataError as error:
        logger.warning("USDA search response could not be processed: %s", error)
        raise HTTPException(status_code=502, detail="USDA returned an unusable search response") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return FoodSearchResponse(query=query.strip(), count=len(foods), foods=[_food_search_item(food) for food in foods])


@app.post("/meal-plans/analyze", response_model=MealPlanAnalysisResponse, tags=["meal plans"])
def analyze_meal_plan(
    request: MealPlanAnalysisRequest,
    client: USDAFoodDataClient = Depends(get_usda_client),
) -> MealPlanAnalysisResponse:
    """Summarize a planned meal schedule and return an experimental classifier result."""
    if request.sex_female not in (0, 1):
        raise HTTPException(status_code=422, detail="sex_female must be 0 or 1")

    selected_days = [_canonical_date(day, "selected_days entry") for day in request.selected_days]
    if len(set(selected_days)) != len(selected_days):
        raise HTTPException(status_code=422, detail="selected_days must not contain duplicates")
    entries = [
        PlannedFoodSelection(
            day=_canonical_date(entry.day, "entry day"),
            fdc_id=entry.fdc_id,
            quantity=entry.quantity,
            unit=entry.unit,
        )
        for entry in request.entries
    ]

    try:
        summary = resolve_meal_plan(entries, client)
    except MealPlanValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except USDAConfigurationError as error:
        raise HTTPException(status_code=503, detail="USDA service is not configured") from error
    except USDARequestError as error:
        logger.warning("USDA food resolution failed: %s", error)
        raise HTTPException(status_code=502, detail="USDA food data is temporarily unavailable") from error
    except USDAFoodDataError as error:
        logger.warning("USDA food record could not be processed: %s", error)
        raise HTTPException(status_code=502, detail="USDA returned an unusable food record") from error

    try:
        features = build_classifier_features(
            summary,
            age=request.age,
            sex_female=request.sex_female,
            bmi=request.bmi,
            selected_days=selected_days,
        )
    except (TypeError, ValueError, ZeroDivisionError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    try:
        prediction: BPCategoryPrediction = predict_bp_category(features)
    except FileNotFoundError as error:
        logger.error("Classifier model artifact is unavailable")
        raise HTTPException(status_code=503, detail="Classifier model is unavailable") from error
    except (TypeError, ValueError) as error:
        logger.exception("Classifier prediction failed validation")
        raise HTTPException(status_code=500, detail="Classifier could not produce a valid result") from error

    return MealPlanAnalysisResponse(
        selected_days=selected_days,
        daily_nutrients={day: _summary_dict(value) for day, value in summary.daily.items()},
        complete_plan_total=_summary_dict(summary.total),
        classifier_features=features,
        prediction=PredictionResponse(
            predicted_class_id=prediction.predicted_class_id,
            predicted_category=prediction.predicted_category,
            probabilities=prediction.probabilities,
            experimental_result=prediction.experimental_result,
        ),
        limitation=LIMITATION_TEXT,
    )
