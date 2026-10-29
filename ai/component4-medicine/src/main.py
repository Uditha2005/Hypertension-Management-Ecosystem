"""Medicine API using the locally fine-tuned detection model."""

import base64
import binascii
import json
import logging
import os
import re
import subprocess
import tempfile

from io import BytesIO
from pathlib import Path
from threading import Lock
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field, StrictBool, StrictInt

from detect import (
    detect_pills,
    load_model,
    class_names,
    MODEL_PATH,
    MODEL_SCOPE,
    MODEL_ID,
)
from prescription_draft import build_draft
from prescription_llm import build_llm_draft
from prescription_vision import read_prescription_image, vision_model
from comparison_service import (
    save_prescription,
    get_prescription as get_reviewed_prescription,
    build_comparison,
    build_total_count_comparison,
    save_comparison,
    list_history,
)


COMPONENT_DIR = Path(__file__).resolve().parent.parent

# Separate local-model records from earlier Hong Kong comparisons.
# The earlier database remains on disk.
COMPARISON_DATABASE = (
    COMPONENT_DIR / "data" / "component4_local_comparison.sqlite3"
)

OCR_PYTHON = COMPONENT_DIR / ".venv-ocr" / "Scripts" / "python.exe"
OCR_WORKER = COMPONENT_DIR / "src" / "paddle_worker.py"
OCR_TIMEOUT_SECONDS = 90
OCR_LOCK = Lock()

logger = logging.getLogger("uvicorn.error")

# Only extract an unambiguous decimal/integer strength from a class label.
# Do not interpret labels such as "3-125mg" as a verified decimal strength.
LABEL_STRENGTH = re.compile(
    r"(?<![\w.\-])(\d+(?:\.\d+)?)\s*(mcg|ug|mg|g|ml|iu)(?!\w)",
    re.I,
)

app = FastAPI(title="Component 4 - Local Medicine Recognition")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class PhotoRequest(BaseModel):
    imageData: str = Field(min_length=1, max_length=7_000_000)


class ReviewedMedicine(BaseModel):
    medicineName: str = Field(min_length=1, max_length=200)
    strength: str = Field(default="", max_length=80)
    productId: str = Field(default="", max_length=200)
    quantity: StrictInt = Field(ge=1, le=100)


class ReviewedPrescriptionRequest(BaseModel):
    reference: str = Field(default="", max_length=200)
    doseLabel: str = Field(min_length=1, max_length=200)
    reviewed: StrictBool
    items: list[ReviewedMedicine] = Field(
        min_length=1,
        max_length=50,
    )


class ReviewedVerifyRequest(PhotoRequest):
    prescriptionId: str = Field(min_length=1, max_length=100)


class PrescriptionDraftRequest(BaseModel):
    text: str = Field(max_length=12000)
    useLLM: StrictBool = False
    trayScope: Literal[
        "manual",
        "single-dose",
        "full-day",
    ] = "manual"


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
            "error": (
                "Invalid request. Check the photo, prescription "
                "fields and whole-number tray quantities."
            )
        },
    )


def get_model():
    try:
        return load_model()
    except Exception as error:
        logger.exception("Local recognition model could not be loaded")
        raise HTTPException(
            status_code=503,
            detail=(
                "Local medicine model could not be loaded. "
                "Check models/local_medicines_best.pt "
                "and the API terminal."
            ),
        ) from error


def read_products(model):
    """
    Build the supported catalog from the loaded local model.

    Product IDs equal detection labels, keeping the existing
    comparison service compatible. Labels are dataset annotations,
    not independently verified pharmaceutical metadata.
    """
    names = class_names(model)

    if not names or len(names) != len(set(names)):
        raise HTTPException(
            status_code=503,
            detail="Local model contains missing or duplicate class names.",
        )

    products = {}

    for class_id, label in enumerate(names):
        # Underscores can separate words in dataset folder names.
        strength_text = label.replace("_", " ")
        matches = list(LABEL_STRENGTH.finditer(strength_text))

        strength = ""
        if len(matches) == 1:
            match = matches[0]
            unit = match.group(2).lower()
            if unit == "ug":
                unit = "mcg"
            strength = f"{match.group(1)} {unit}"

        products[label] = {
            "id": label,
            "name": label,
            "classId": class_id,
            "strength": strength,
            "brand": "",
            "formulation": "",
            "ingredients": [],
            "certificateHolder": "",
            "referenceUrl": "",
            "source": "local-training-label",
            "modelId": MODEL_ID,
            "metadataVerified": False,
            "requiresManualReview": True,
        }

    return products


def decode_photo(image_data):
    allowed = {
        "data:image/jpeg;base64": "JPEG",
        "data:image/png;base64": "PNG",
        "data:image/webp;base64": "WEBP",
    }

    try:
        header, encoded = image_data.split(",", 1)

        if header not in allowed:
            raise ValueError("Unsupported image type")

        raw = base64.b64decode(encoded, validate=True)

        if not raw or len(raw) > 5 * 1024 * 1024:
            raise ValueError("Photo must be smaller than 5 MB")

        with Image.open(BytesIO(raw)) as source:
            if source.format != allowed[header]:
                raise ValueError("Image format does not match its type")

            if source.width * source.height > 20_000_000:
                raise ValueError("Photo exceeds 20 megapixels")

            source.load()
            return source.copy()

    except (
        ValueError,
        binascii.Error,
        OSError,
        UnidentifiedImageError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as error:
        raise HTTPException(
            status_code=400,
            detail=(
                "Choose a valid JPG, PNG or WebP photo under 5 MB "
                "and no larger than 20 megapixels."
            ),
        ) from error


def ocr_files_ready():
    return OCR_PYTHON.is_file() and OCR_WORKER.is_file()


def llm_configured():
    return bool(os.environ.get("GROQ_API_KEY", "").strip())


def image_reader():
    mode = os.environ.get("RX_IMAGE_READER", "").strip().lower()
    if mode and mode not in {"groq-vision", "paddle"}:
        raise HTTPException(status_code=503, detail="RX_IMAGE_READER must be groq-vision or paddle.")
    return mode or ("groq-vision" if llm_configured() else "paddle")


def image_reader_configured():
    return llm_configured() if image_reader() == "groq-vision" else ocr_files_ready()


@app.get("/")
def home():
    return {
        "message": "Local medicine recognition API running",
        "component": 4,
        "mode": "live",
        "scope": MODEL_SCOPE,
        "modelId": MODEL_ID,
        "modelFile": MODEL_PATH.name,
        "modelFilePresent": MODEL_PATH.is_file(),
        "prescriptionReady": False,
        "ocrConfigured": image_reader_configured(),
        "imageReader": image_reader(),
        "visionModel": vision_model() if image_reader() == "groq-vision" else None,
        "prescriptionImageDestination": "groq" if image_reader() == "groq-vision" else "local",
        "llmConfigured": llm_configured(),
        "reviewedComparisonReady": True,
        "totalCountComparisonReady": True,
    }


@app.get("/api/medicine/bootstrap")
def bootstrap():
    products = read_products(get_model())

    return {
        "mode": "live",
        "products": list(products.values()),
        "patients": [],
        "modelReady": True,
        "metadataReady": True,
        "metadataVerified": False,
        "metadataSource": "local-training-labels",
        "prescriptionReady": False,
        "ocrConfigured": image_reader_configured(),
        "imageReader": image_reader(),
        "visionModel": vision_model() if image_reader() == "groq-vision" else None,
        "prescriptionImageDestination": "groq" if image_reader() == "groq-vision" else "local",
        "llmConfigured": llm_configured(),
        "reviewedComparisonReady": True,
        "totalCountComparisonReady": True,
        "scope": MODEL_SCOPE,
        "modelId": MODEL_ID,
        "modelFile": MODEL_PATH.name,
        "classCount": len(products),
    }


@app.post("/api/medicine/detect")
def detect_photo(payload: PhotoRequest):
    products = read_products(get_model())
    image = decode_photo(payload.imageData)

    try:
        detections, prediction = detect_pills(image)

        for index, detection in enumerate(detections, start=1):
            product = products.get(detection["label"])

            detection["detectionId"] = index
            detection["productId"] = product["id"] if product else None
            detection["productName"] = (
                product["name"] if product else "Unidentified medicine"
            )
            detection["strength"] = product["strength"] if product else ""
            detection["ingredients"] = (
                product["ingredients"] if product else []
            )
            detection["unmapped"] = product is None
            detection["metadataVerified"] = False

        annotated_rgb = prediction.plot()[:, :, ::-1]

        with Image.fromarray(annotated_rgb) as annotated_image:
            with BytesIO() as buffer:
                annotated_image.save(
                    buffer,
                    format="JPEG",
                    quality=85,
                )
                encoded = base64.b64encode(
                    buffer.getvalue()
                ).decode("ascii")

    except Exception as error:
        logger.exception("Local model prediction failed")
        raise HTTPException(
            status_code=500,
            detail="Local model prediction failed. Check the API terminal.",
        ) from error
    finally:
        image.close()

    return {
        "mode": "live",
        "scope": MODEL_SCOPE,
        "modelId": MODEL_ID,
        "modelFile": MODEL_PATH.name,
        "count": len(detections),
        "detections": detections,
        "annotatedImage": f"data:image/jpeg;base64,{encoded}",
        "requiresManualReview": True,
        "notes": (
            "Names describe predicted local training classes, "
            "not confirmed medicine identities. "
            "No prescription comparison has been performed."
        ),
    }


@app.post("/api/medicine/prescription/ocr")
def prescription_ocr(payload: PhotoRequest):
    if image_reader() == "groq-vision":
        if not llm_configured():
            raise HTTPException(status_code=503, detail="Groq vision requires GROQ_API_KEY in the API process.")
        image = decode_photo(payload.imageData)
        acquired = False
        try:
            acquired = OCR_LOCK.acquire(blocking=False)
            if not acquired:
                raise HTTPException(status_code=503, detail="Prescription image reading is busy. Wait for the current request.")
            logger.info("Prescription image reader: Groq vision, model %s", vision_model())
            return read_prescription_image(image)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None
        except RuntimeError as error:
            # Do not hide a failed vision request behind the old local OCR.
            raise HTTPException(status_code=503, detail=str(error)) from None
        finally:
            image.close()
            if acquired:
                OCR_LOCK.release()

    if not ocr_files_ready():
        raise HTTPException(
            status_code=503,
            detail=(
                "OCR setup is missing. Check .venv-ocr "
                "and src/paddle_worker.py."
            ),
        )

    image = decode_photo(payload.imageData)
    lock_acquired = False

    try:
        lock_acquired = OCR_LOCK.acquire(blocking=False)

        if not lock_acquired:
            raise HTTPException(
                status_code=503,
                detail="OCR is busy. Try again after the current request.",
            )

        with tempfile.TemporaryDirectory(
            prefix="prescription_ocr_"
        ) as folder:
            folder_path = Path(folder)
            image_path = folder_path / "photo.png"
            output_path = folder_path / "result.json"

            image.save(
                image_path,
                format="PNG",
                exif=image.getexif(),
            )

            logger.info(
                "Prescription OCR: starting worker (timeout: %ss)",
                OCR_TIMEOUT_SECONDS,
            )

            process = subprocess.run(
                [
                    str(OCR_PYTHON),
                    "-u",
                    str(OCR_WORKER),
                    str(image_path),
                    str(output_path),
                ],
                cwd=str(COMPONENT_DIR),
                timeout=OCR_TIMEOUT_SECONDS,
                check=False,
            )

            if process.returncode != 0:
                logger.error(
                    "OCR worker exited with code %s",
                    process.returncode,
                )
                raise HTTPException(
                    status_code=503,
                    detail="Prescription OCR failed. Check the API terminal.",
                )

            if not output_path.is_file():
                raise HTTPException(
                    status_code=503,
                    detail="OCR did not produce a result.",
                )

            result = json.loads(
                output_path.read_text(encoding="utf-8")
            )

            if (
                not isinstance(result, dict)
                or not isinstance(result.get("text"), str)
                or not isinstance(result.get("blocks"), list)
            ):
                raise ValueError("Invalid OCR result")

            result["requiresManualReview"] = True
            result["confirmed"] = False
            result["comparisonPerformed"] = False

            return result

    except subprocess.TimeoutExpired as error:
        logger.warning("Prescription OCR timed out; worker stopped")
        raise HTTPException(
            status_code=504,
            detail=(
                "OCR exceeded 90 seconds and the worker was stopped. "
                "Check the API terminal for the last OCR stage."
            ),
        ) from error

    except (OSError, ValueError) as error:
        logger.exception("Could not process prescription photo")
        raise HTTPException(
            status_code=500,
            detail="Could not process the prescription photo.",
        ) from error

    finally:
        image.close()

        if lock_acquired:
            OCR_LOCK.release()
            logger.info("Prescription OCR: busy lock released")


@app.post("/api/medicine/prescription/draft")
def draft_prescription(payload: PrescriptionDraftRequest):
    products = read_products(get_model())

    try:
        if payload.useLLM:
            return build_llm_draft(
                payload.text,
                products,
                payload.trayScope,
            )

        return build_draft(payload.text, products)

    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error

    except RuntimeError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error


@app.post("/api/medicine/prescription/review")
def review_prescription(payload: ReviewedPrescriptionRequest):
    products = read_products(get_model())

    try:
        return save_prescription(
            COMPARISON_DATABASE,
            payload.model_dump(),
            products,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error


def find_reviewed_prescription(prescription_id):
    prescription = get_reviewed_prescription(
        COMPARISON_DATABASE,
        prescription_id,
    )

    if prescription is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Reviewed prescription not found for the local model. "
                "Review and save the tray list again."
            ),
        )

    return prescription


def store_result(result, recognition):
    # Persist model provenance with each comparison.
    result = {
        **result,
        "modelId": MODEL_ID,
        "modelFile": MODEL_PATH.name,
        "modelScope": MODEL_SCOPE,
    }

    save_comparison(COMPARISON_DATABASE, result)

    return {
        **result,
        "recognition": recognition,
    }


@app.post("/api/medicine/verify-reviewed")
def verify_reviewed(payload: ReviewedVerifyRequest):
    prescription = find_reviewed_prescription(payload.prescriptionId)
    products = read_products(get_model())

    try:
        build_comparison(prescription, [], products)
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error

    recognition = detect_photo(
        PhotoRequest(imageData=payload.imageData)
    )

    try:
        result = build_comparison(
            prescription,
            recognition["detections"],
            products,
        )
    except ValueError as error:
        logger.exception("Invalid recognition data during comparison")
        raise HTTPException(
            status_code=500,
            detail="Invalid model comparison result.",
        ) from error

    return store_result(result, recognition)


@app.post("/api/medicine/verify-total-count")
def verify_total_count(payload: ReviewedVerifyRequest):
    prescription = find_reviewed_prescription(payload.prescriptionId)

    try:
        build_total_count_comparison(prescription, [])
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error

    recognition = detect_photo(
        PhotoRequest(imageData=payload.imageData)
    )

    try:
        result = build_total_count_comparison(
            prescription,
            recognition["detections"],
        )
    except ValueError as error:
        logger.exception("Invalid data during total-count comparison")
        raise HTTPException(
            status_code=500,
            detail="Invalid total-count comparison result.",
        ) from error

    return store_result(result, recognition)


@app.get("/api/medicine/history")
def history():
    return list_history(COMPARISON_DATABASE)


@app.get("/api/medicine/patients/{patient_id}/prescription")
def get_prescription(patient_id: str):
    raise HTTPException(
        status_code=503,
        detail="Patient and prescription records are not connected yet.",
    )


@app.post("/api/medicine/verify")
def verify_medicine():
    raise HTTPException(
        status_code=503,
        detail=(
            "Use /api/medicine/verify-reviewed for supported products "
            "or /api/medicine/verify-total-count for total counts only."
        ),
    )