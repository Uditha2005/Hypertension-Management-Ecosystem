
"""Model 1 prediction service for the elderly-care hypertension project.

This is a research prototype, not a clinically validated risk calculator.
The model estimates its study-defined hypertension outcome by follow-up.
It must not be used to diagnose hypertension or make treatment decisions.
"""

from pathlib import Path
from functools import lru_cache
from typing import Any

import joblib
import numpy as np
import pandas as pd
import shap


# ============================================================
# Paths and model configuration
# ============================================================

COMPONENT_DIR = Path(__file__).resolve().parents[1]

MODEL_PATH = (
    COMPONENT_DIR / "models" / "model1_random_forest.joblib"
)

FEATURES = [
    "age",
    "sex_female",
    "sbp_baseline",
    "dbp_baseline",
    "pulse_baseline",
    "bmi",
    "diabetes_history",
]

FEATURE_LABELS = {
    "age": "Age",
    "sex_female": "Sex",
    "sbp_baseline": "Systolic blood pressure",
    "dbp_baseline": "Diastolic blood pressure",
    "pulse_baseline": "Pulse rate",
    "bmi": "Body mass index (BMI)",
    "diabetes_history": "Reported diabetes history",
}

# These are the observed ranges in the current candidate dataset.
# They describe the research data, not universal clinical limits.
OBSERVED_RANGES = {
    "age": (60.0, 74.0),
    "sbp_baseline": (85.0, 158.0),
    "dbp_baseline": (44.0, 94.0),
    "pulse_baseline": (48.0, 150.0),
    "bmi": (14.23, 49.25),
}

# Baseline cohort eligibility excluded SBP >=160 or DBP >=95.
# These are historical research inclusion thresholds, not modern
# clinical diagnostic thresholds.


# ============================================================
# Model loading
# ============================================================

@lru_cache(maxsize=1)
def _load_model():
    """Load the selected trained model once per Python process."""

    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Trained model not found: {MODEL_PATH}. "
            "Copy the selected model artifact into the component models folder."
        )

    model = joblib.load(MODEL_PATH)

    trained_features = list(
        getattr(model, "feature_names_in_", [])
    )

    if trained_features and trained_features != FEATURES:
        raise RuntimeError(
            "The feature order or names in the saved model do not match "
            f"the service configuration. Model: {trained_features}; "
            f"service: {FEATURES}"
        )

    if not hasattr(model, "predict_proba"):
        raise TypeError(
            "The loaded model does not support predict_proba()."
        )

    if 1 not in list(model.classes_):
        raise RuntimeError(
            "The model does not contain the expected positive class 1."
        )

    return model


@lru_cache(maxsize=1)
def _load_explainer():
    """Build SHAP explanations without requiring a saved patient dataset."""

    model = _load_model()

    return shap.TreeExplainer(
        model,
        feature_perturbation="tree_path_dependent",
    )


# ============================================================
# Input validation
# ============================================================

def _number(data: dict, field: str) -> float:
    """Read a finite numeric input and validate its presence."""

    if field not in data or data[field] is None:
        raise ValueError(f"Missing required input: {field}")

    try:
        value = float(data[field])
    except (ValueError, TypeError):
        raise ValueError(
            f"{field} must be a valid number."
        ) from None

    if not np.isfinite(value):
        raise ValueError(f"{field} must be finite.")

    return value


def _binary(value: Any, field: str) -> int:
    """Convert common yes/no representations to 0 or 1."""

    if isinstance(value, (bool, np.bool_)):
        return int(value)

    if isinstance(value, (int, float, np.integer, np.floating)):
        if value in (0, 1):
            return int(value)

    normalized = str(value).strip().lower()

    if normalized in {"yes", "y", "true", "1"}:
        return 1

    if normalized in {"no", "n", "false", "0"}:
        return 0

    raise ValueError(
        f"{field} must be Yes/No or 1/0."
    )


def _sex_female(value: Any) -> int:
    """Map caregiver-facing sex input to the trained feature coding."""

    normalized = str(value).strip().lower()

    if normalized in {"male", "m"}:
        return 0

    if normalized in {"female", "f"}:
        return 1

    raise ValueError(
        "sex must be 'male' or 'female' for this model."
    )


def _input_row(data: dict) -> tuple[pd.DataFrame, dict]:
    """Validate caregiver inputs and construct trained features."""

    age = _number(data, "age")
    systolic = _number(data, "systolic_bp")
    diastolic = _number(data, "diastolic_bp")
    pulse = _number(data, "pulse_rate")
    height_cm = _number(data, "height_cm")
    weight_kg = _number(data, "weight_kg")

    sex_female = _sex_female(data.get("sex"))

    diabetes_history = _binary(
        data.get("diabetes_history"),
        "diabetes_history",
    )

    if not 60 <= age <= 74:
        raise ValueError(
            "This research model was developed using participants aged "
            "60–74. It cannot provide a supported estimate outside that "
            "age range."
        )

    if not 70 <= systolic <= 300:
        raise ValueError(
            "Systolic blood pressure must be entered in mmHg "
            "within the supported input-validation range."
        )

    if not 30 <= diastolic <= 180:
        raise ValueError(
            "Diastolic blood pressure must be entered in mmHg "
            "within the supported input-validation range."
        )

    if systolic >= 160 or diastolic >= 95:
        return None, {
            "status": "outside_training_eligibility",
            "message": (
                "These readings fall outside the baseline blood-pressure "
                "eligibility criteria used to construct this research "
                "cohort. No future-onset model score was generated. "
                "Follow the care home's clinical assessment protocol."
            ),
        }

    if not 30 <= pulse <= 200:
        raise ValueError(
            "Pulse rate must be entered in beats per minute."
        )

    if not 100 <= height_cm <= 220:
        raise ValueError(
            "Height must be entered in centimetres within the "
            "supported input-validation range."
        )

    if not 25 <= weight_kg <= 300:
        raise ValueError(
            "Weight must be entered in kilograms within the "
            "supported input-validation range."
        )

    height_m = height_cm / 100
    bmi = weight_kg / (height_m ** 2)

    features = {
        "age": age,
        "sex_female": sex_female,
        "sbp_baseline": systolic,
        "dbp_baseline": diastolic,
        "pulse_baseline": pulse,
        "bmi": bmi,
        "diabetes_history": diabetes_history,
    }

    row = pd.DataFrame(
        [[features[name] for name in FEATURES]],
        columns=FEATURES,
    )

    return row, features


# ============================================================
# SHAP explanation
# ============================================================

def _explain_prediction(
    row: pd.DataFrame,
    probability: float,
) -> dict:
    """Explain class 1, handling common SHAP return formats."""

    model = _load_model()
    explainer = _load_explainer()

    positive_index = list(model.classes_).index(1)

    shap_output = explainer.shap_values(row)

    if isinstance(shap_output, list):
        # Older SHAP versions return one array per class.
        contributions = np.asarray(
            shap_output[positive_index]
        )[0]

    else:
        shap_array = np.asarray(shap_output)

        if shap_array.ndim == 3:
            # Newer versions can return:
            # samples x features x classes.
            contributions = shap_array[
                0, :, positive_index
            ]

        elif shap_array.ndim == 2:
            contributions = shap_array[0]

        else:
            raise RuntimeError(
                f"Unexpected SHAP output shape: {shap_array.shape}"
            )

    expected = np.asarray(explainer.expected_value)

    if expected.ndim == 0:
        base_value = float(expected)
    elif expected.size > positive_index:
        base_value = float(
            expected.reshape(-1)[positive_index]
        )
    else:
        raise RuntimeError(
            f"Unexpected SHAP expected value: {expected}"
        )

    reconstruction = base_value + float(
        np.sum(contributions)
    )

    reconstruction_error = abs(
        reconstruction - probability
    )

    # Contributions are expressed in probability units only when
    # their sum reconstructs the positive-class probability.
    reconstruction_ok = reconstruction_error < 1e-5

    details = []

    for feature, contribution in zip(
        FEATURES,
        contributions,
    ):
        contribution = float(contribution)

        if contribution > 0:
            direction = "increases_model_output"
        elif contribution < 0:
            direction = "decreases_model_output"
        else:
            direction = "no_material_directional_contribution"

        item = {
            "feature": feature,
            "label": FEATURE_LABELS[feature],
            "value": float(row.iloc[0][feature]),
            "contribution": contribution,
            "direction": direction,
        }

        if reconstruction_ok:
            item["contribution_percentage_points"] = (
                contribution * 100
            )

        details.append(item)

    details.sort(
        key=lambda item: abs(item["contribution"]),
        reverse=True,
    )

    return {
        "output_scale": (
            "positive_class_probability"
            if reconstruction_ok
            else "model_output_units"
        ),
        "base_value": base_value,
        "reconstruction_error": float(reconstruction_error),
        "reconstruction_verified": bool(reconstruction_ok),
        "features": details,
    }


# ============================================================
# Evidence-informed recommendation layer
# ============================================================

def _recommendations(features: dict) -> list[dict]:
    """Create general precautionary advice independently of SHAP."""

    recommendations = [
        {
            "title": "Record blood-pressure measurements carefully",
            "reason": (
                "Repeated, correctly performed readings provide "
                "more useful information than a single reading."
            ),
            "action": (
                "Use a validated upper-arm monitor where available. "
                "Take two readings about 1–2 minutes apart, record "
                "the date and time, and share repeated high readings "
                "with the patient's healthcare professional."
            ),
            "source": (
                "CDC — Measuring Your Blood Pressure: "
                "https://www.cdc.gov/high-blood-pressure/measure/"
            ),
        },
        {
            "title": "Support a heart-healthy eating pattern",
            "reason": (
                "A balanced diet with less excess sodium is among "
                "the recommended lifestyle approaches for helping "
                "prevent or manage high blood pressure."
            ),
            "action": (
                "Offer balanced meals with vegetables, fruit and "
                "other appropriate nutrient-rich foods, and avoid "
                "unnecessarily salty foods. Adapt dietary changes "
                "to the patient's nutritional needs and clinical plan."
            ),
            "source": (
                "2025 AHA/ACC high blood-pressure guideline: "
                "https://www.jacc.org/doi/10.1016/j.jacc.2025.05.007"
            ),
        },
        {
            "title": "Support safe physical activity",
            "reason": (
                "Regular physical activity can help manage blood "
                "pressure and overall cardiovascular health."
            ),
            "action": (
                "Encourage activity suited to the resident's mobility, "
                "fall risk, preferences and clinician-approved care plan."
            ),
            "source": (
                "CDC — Preventing High Blood Pressure: "
                "https://www.cdc.gov/high-blood-pressure/prevention/"
            ),
        },
    ]

    systolic = features["sbp_baseline"]
    diastolic = features["dbp_baseline"]
    bmi = features["bmi"]

    # Current guideline thresholds are used here as a prompt for
    # repeat measurement and clinician review, not as an automated
    # diagnosis from a single reading.
    if systolic >= 130 or diastolic >= 80:
        recommendations.insert(
            0,
            {
                "title": "Arrange review of repeated elevated readings",
                "reason": (
                    "The entered reading is above the normal range "
                    "defined in current adult blood-pressure guidance. "
                    "A single reading does not establish a diagnosis."
                ),
                "action": (
                    "Repeat measurements using correct technique and "
                    "share the readings with a healthcare professional "
                    "for interpretation."
                ),
                "source": (
                    "2025 AHA/ACC high-blood-pressure guideline: "
                    "https://professional.heart.org/en/science-news/"
                    "2025-high-blood-pressure-guideline/top-things-to-know"
                ),
            },
        )

    if bmi >= 30:
        recommendations.append(
            {
                "title": "Discuss individualized nutrition and weight support",
                "reason": (
                    "Higher body weight can contribute to blood-pressure "
                    "risk, but weight recommendations for older adults "
                    "must also consider frailty and nutritional status."
                ),
                "action": (
                    "Consider a clinician- or dietitian-guided plan. "
                    "Do not prescribe weight loss automatically; "
                    "assess nutrition and the resident's overall health."
                ),
                "source": (
                    "2025 AHA/ACC high-blood-pressure guideline: "
                    "https://www.jacc.org/doi/10.1016/j.jacc.2025.05.007"
                ),
            }
        )

    if bmi < 18.5:
        recommendations.append(
            {
                "title": "Review nutritional status",
                "reason": (
                    "A low BMI may warrant attention to nutrition "
                    "rather than a weight-loss recommendation."
                ),
                "action": (
                    "Ask the care team to assess nutritional intake, "
                    "unintentional weight loss and appropriate support."
                ),
                "source": (
                    "Individual clinical assessment is required."
                ),
            }
        )

    if features["diabetes_history"] == 1:
        recommendations.append(
            {
                "title": "Continue diabetes-related follow-up",
                "reason": (
                    "A reported history of diabetes is relevant to "
                    "overall cardiometabolic health."
                ),
                "action": (
                    "Follow the patient's prescribed diabetes care plan "
                    "and discuss blood-glucose monitoring and cardiovascular "
                    "risk management with the healthcare team."
                ),
                "source": (
                    "2025 AHA/ACC high-blood-pressure guideline: "
                    "https://www.jacc.org/doi/10.1016/j.jacc.2025.05.007"
                ),
            }
        )

    return recommendations


# ============================================================
# Public application-facing function
# ============================================================

def assess_patient(patient: dict) -> dict:
    """Return a research-model output, explanation and precautions.

    Expected input keys:
        age: 60–74
        sex: "male" or "female"
        systolic_bp: mmHg
        diastolic_bp: mmHg
        pulse_rate: beats per minute
        height_cm: centimetres
        weight_kg: kilograms
        diabetes_history: Yes/No or 1/0
        has_existing_hypertension: Yes/No or True/False

    The model is not clinically validated and does not provide a
    calibrated absolute risk over a defined future period.
    """

    if not isinstance(patient, dict):
        raise TypeError("patient must be a dictionary.")

    if "has_existing_hypertension" not in patient:
        raise ValueError(
            "Please specify has_existing_hypertension before "
            "requesting a first-onset estimate."
        )

    existing = _binary(
        patient["has_existing_hypertension"],
        "has_existing_hypertension",
    )

    if existing == 1:
        return {
            "status": "existing_hypertension_pathway",
            "model_score_percent": None,
            "message": (
                "This model was trained to estimate a study-defined "
                "first-onset outcome in people reporting no previous "
                "high blood pressure. It is not appropriate for estimating "
                "first-onset risk in someone already diagnosed."
            ),
            "recommendations": [
                {
                    "title": "Follow the clinician-approved care plan",
                    "action": (
                        "Continue the existing care plan and record "
                        "blood-pressure readings as directed."
                    ),
                },
                {
                    "title": "Do not alter medication independently",
                    "action": (
                        "Do not stop or change prescribed medication "
                        "without consulting the healthcare professional."
                    ),
                },
            ],
        }

    row, features = _input_row(patient)

    # _input_row may return a non-applicable status for readings
    # outside the research cohort's eligibility range.
    if row is None:
        return {
            **features,
            "model_score_percent": None,
            "recommendations": [
                {
                    "title": "Clinical assessment",
                    "action": (
                        "Follow the care home's clinical assessment "
                        "protocol; this model has not generated a score."
                    ),
                }
            ],
        }

    model = _load_model()
    probability = float(model.predict_proba(row)[0][
        list(model.classes_).index(1)
    ])

    warnings = []

    for feature, (low, high) in OBSERVED_RANGES.items():
        value = features[feature]

        if value < low or value > high:
            warnings.append(
                f"{FEATURE_LABELS[feature]} is outside the observed "
                f"range ({low:g}–{high:g}) in the current research cohort."
            )

    explanation = _explain_prediction(row, probability)

    return {
        "status": "research_prototype",
        "model_name": "Random Forest",
        "model_score_percent": round(probability * 100, 2),
        "score_interpretation": (
            "Uncalibrated model output for the study-defined "
            "hypertension outcome by follow-up. It is not a validated "
            "absolute risk estimate for a fixed time period."
        ),
        "input_features": features,
        "domain_warnings": warnings,
        "shap_explanation": explanation,
        "recommendations": _recommendations(features),
    }
