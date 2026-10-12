import base64
import binascii
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from verify import Detection, verify_tray


app = FastAPI(title="Component 4 - Medicine Verification")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# Fictional demo products, not prescribing recommendations.
PRODUCTS = [
    {
        "id": "DEMO-P001",
        "name": "Sample product A",
        "strength": "5 mg",
        "brand": "Demo brand A",
        "formulation": "Tablet",
    },
    {
        "id": "DEMO-P002",
        "name": "Sample product B",
        "strength": "50 mg",
        "brand": "Demo brand B",
        "formulation": "Tablet",
    },
    {
        "id": "DEMO-P003",
        "name": "Sample product C",
        "strength": "10 mg",
        "brand": "Demo brand C",
        "formulation": "Tablet",
    },
]

PATIENTS = [
    {"id": "DEMO-001", "name": "Demo patient 01"},
    {"id": "DEMO-002", "name": "Demo patient 02"},
]

PRESCRIPTIONS = {
    "DEMO-001": {
        "id": "RX-DEMO-001",
        "patientId": "DEMO-001",
        "doseLabel": "Sample morning tray",
        "status": "active",
        "items": [
            {"productId": "DEMO-P001", "quantity": 1},
            {"productId": "DEMO-P002", "quantity": 1},
        ],
    },
    "DEMO-002": {
        "id": "RX-DEMO-002",
        "patientId": "DEMO-002",
        "doseLabel": "Sample evening tray",
        "status": "active",
        "items": [
            {"productId": "DEMO-P001", "quantity": 2},
        ],
    },
}

# Stored only inside ai/component4-medicine/data.
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
HISTORY_FILE = DATA_DIR / "medicine-history.json"
HISTORY_LOCK = Lock()

STATUS_LABELS = {
    "Correct": "Tray matches prescription",
    "Missing": "Missing pills",
    "Extra": "Extra pills",
    "Potential Swap": "Potential swap",
    "Manual Verification Required": "Manual verification required",
}


class VerifyRequest(BaseModel):
    patientId: str = Field(min_length=1, max_length=100)
    prescriptionId: str = Field(min_length=1, max_length=100)
    scenario: Literal[
        "match",
        "missing",
        "extra",
        "swap",
        "uncertain",
        "empty",
    ]
    imageData: str = Field(min_length=1, max_length=7_000_000)


@app.exception_handler(HTTPException)
async def handle_http_error(request, error):
    return JSONResponse(
        status_code=error.status_code,
        content={"error": str(error.detail)},
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request, error):
    return JSONResponse(
        status_code=422,
        content={
            "error": "Invalid request. Check the patient, scenario and photo."
        },
    )


def read_history():
    if not HISTORY_FILE.exists():
        return []

    try:
        records = json.loads(
            HISTORY_FILE.read_text(encoding="utf-8")
        )

        if not isinstance(records, list):
            raise ValueError("History must be a list")

        return records

    except (OSError, ValueError) as error:
        raise HTTPException(
            status_code=500,
            detail="Could not read the saved history.",
        ) from error


def save_result(result):
    # Run this local demo with one API worker.
    with HISTORY_LOCK:
        records = [result, *read_history()][:200]

        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)

            temporary = HISTORY_FILE.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(records, indent=2),
                encoding="utf-8",
            )
            temporary.replace(HISTORY_FILE)

        except OSError as error:
            raise HTTPException(
                status_code=500,
                detail="Could not save verification history.",
            ) from error


def validate_photo(image_data):
    try:
        header, encoded = image_data.split(",", 1)

        allowed_headers = {
            "data:image/jpeg;base64",
            "data:image/png;base64",
            "data:image/webp;base64",
        }

        if header not in allowed_headers:
            raise ValueError("Unsupported image type")

        raw = base64.b64decode(encoded, validate=True)

    except (ValueError, binascii.Error) as error:
        raise HTTPException(
            status_code=400,
            detail="Choose a JPG, PNG or WebP photo.",
        ) from error

    if not raw or len(raw) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail="Choose a photo smaller than 5 MB.",
        )

    signatures = {
        "data:image/jpeg;base64": raw.startswith(b"\xff\xd8\xff"),
        "data:image/png;base64": raw.startswith(b"\x89PNG\r\n\x1a\n"),
        "data:image/webp;base64": (
            raw.startswith(b"RIFF") and raw[8:12] == b"WEBP"
        ),
    }

    if not signatures[header]:
        raise HTTPException(
            status_code=400,
            detail="The file does not have a valid image signature.",
        )

    # Demo only: image bytes are not analysed or saved.


def create_demo_detections(prescription, scenario):
    detections = [
        Detection(
            label=item["productId"],
            confidence=0.95,
        )
        for item in prescription["items"]
        for _ in range(item["quantity"])
    ]

    if scenario == "missing":
        detections.pop()

    elif scenario == "extra":
        detections.append(Detection("DEMO-P003", 0.95))

    elif scenario == "swap":
        detections.pop()
        detections.append(Detection("DEMO-P003", 0.95))

    elif scenario == "uncertain":
        detections[0] = Detection("UNKNOWN", 0.40)

    elif scenario == "empty":
        detections = []

    return detections


def detection_to_json(detection):
    return {
        "productId": (
            None
            if detection.label == "UNKNOWN"
            else detection.label
        ),
        "confidence": detection.confidence,
    }


@app.get("/")
def home():
    return {
        "message": "Python medicine verification backend running",
        "component": 4,
        "mode": "demo",
    }


@app.get("/api/medicine/bootstrap")
def bootstrap():
    return {
        "mode": "demo",
        "products": PRODUCTS,
        "patients": PATIENTS,
        "modelReady": False,
    }


@app.get("/api/medicine/patients/{patient_id}/prescription")
def get_prescription(patient_id: str):
    prescription = PRESCRIPTIONS.get(patient_id)

    if prescription is None:
        raise HTTPException(
            status_code=404,
            detail="Patient or active prescription not found.",
        )

    return prescription


@app.get("/api/medicine/history")
def get_history():
    with HISTORY_LOCK:
        return read_history()


@app.post("/api/medicine/verify")
def verify_medicine(payload: VerifyRequest):
    prescription = PRESCRIPTIONS.get(payload.patientId)

    if (
        prescription is None
        or prescription["id"] != payload.prescriptionId
    ):
        raise HTTPException(
            status_code=409,
            detail="Select a patient and reload their prescription.",
        )

    validate_photo(payload.imageData)

    # Synthetic detections for testing the UI and comparison flow.
    # Replace this with model inference after local fine-tuning.
    detections = create_demo_detections(
        prescription,
        payload.scenario,
    )

    expected = {
        item["productId"]: item["quantity"]
        for item in prescription["items"]
    }

    # Uses the existing Python logic in verify.py.
    comparison = verify_tray(detections, expected)

    confident = [
        detection
        for detection in detections
        if not detection.is_uncertain()
    ]

    found = Counter(
        detection.label for detection in confident
    )

    product_ids = list(
        dict.fromkeys([*expected, *found])
    )

    rows = [
        {
            "productId": product_id,
            "expected": expected.get(product_id, 0),
            "found": found.get(product_id, 0),
        }
        for product_id in product_ids
    ]

    # Keep all missing/extra counts visible, including potential swaps.
    missing = [
        {
            "productId": row["productId"],
            "quantity": row["expected"] - row["found"],
        }
        for row in rows
        if row["expected"] > row["found"]
    ]

    extra = [
        {
            "productId": row["productId"],
            "quantity": row["found"] - row["expected"],
        }
        for row in rows
        if row["found"] > row["expected"]
    ]

    uncertain = [
        detection_to_json(detection)
        for detection in comparison.uncertain
    ]

    patient = next(
        item
        for item in PATIENTS
        if item["id"] == payload.patientId
    )

    result = {
        "id": str(uuid4()),
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "mode": "demo",
        "scenario": payload.scenario,
        "patientId": payload.patientId,
        "patientName": patient["name"],
        "prescription": prescription,
        "detections": [
            detection_to_json(item)
            for item in detections
        ],
        "status": STATUS_LABELS[comparison.status],
        "rows": rows,
        "missing": missing,
        "extra": extra,
        "uncertain": uncertain,
        "notes": (
            "Counts exclude uncertain detections. Review the whole tray."
            if uncertain
            else (
                "This compares detected products and counts only; "
                "it does not confirm administration or swallowing."
            )
        ),
    }

    save_result(result)
    return result