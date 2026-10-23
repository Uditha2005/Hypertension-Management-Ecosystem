from typing import Union

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from prediction_service import assess_patient


app = FastAPI(
    title="Component 1 - Physiological Wellness AI",
    description=(
        "Research prototype for physiological hypertension "
        "risk prediction, SHAP explanations and recommendations."
    ),
    version="0.1.0",
)


class PatientInput(BaseModel):
    age: float
    sex: str
    systolic_bp: float
    diastolic_bp: float
    pulse_rate: float
    height_cm: float
    weight_kg: float
    diabetes_history: Union[bool, int, str]
    has_existing_hypertension: Union[bool, int, str]


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "component1-physiological",
    }


@app.post("/predict")
def predict(patient: PatientInput):
    try:
        return assess_patient(patient.dict())
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
