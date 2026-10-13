import base64
import binascii
import csv
import json
import logging
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field

from detect import detect_pills, load_model


COMPONENT_DIR = Path(__file__).resolve().parent.parent
METADATA_PATH = COMPONENT_DIR / "data" / "medicine_metadata.csv"

OCR_PYTHON = COMPONENT_DIR / ".venv-ocr" / "Scripts" / "python.exe"
OCR_WORKER = COMPONENT_DIR / "src" / "paddle_worker.py"
OCR_LOCK = Lock()

logger = logging.getLogger(__name__)

app = FastAPI(title="Component 4 - Medicine Recognition")

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
        content={"error": "Invalid request. Check the uploaded photo."},
    )


def get_model():
    try:
        return load_model()
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail="Recognition model could not be loaded.",
        ) from error


def read_products(model):
    """Match model class codes with the dataset's reference metadata."""
    try:
        with METADATA_PATH.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as stream:
            reader = csv.DictReader(stream)

            required = {"id", "name", "ingredients/0"}
            if not required.issubset(set(reader.fieldnames or [])):
                raise ValueError("Missing metadata columns")

            products = {}

            for row in reader:
                product_id = (row.get("id") or "").strip()
                product_name = (row.get("name") or "").strip()

                if not product_id or not product_name:
                    raise ValueError("Missing product ID or name")

                if product_id in products:
                    raise ValueError("Duplicate product ID")

                ingredients = [
                    value.strip()
                    for value in [
                        row.get("ingredients/0") or "",
                        row.get("ingredients/1") or "",
                    ]
                    if value.strip()
                ]

                products[product_id] = {
                    "id": product_id,
                    "name": product_name,
                    "strength": "",
                    "brand": "",
                    "formulation": "",
                    "ingredients": ingredients,
                    "certificateHolder": (
                        row.get("certificate_holder") or ""
                    ).strip(),
                    "referenceUrl": (row.get("url") or "").strip(),
                }

        model_names = model.names
        names = (
            model_names.values()
            if isinstance(model_names, dict)
            else model_names
        )

        labels = [label for label in names if label != "pills"]
        missing = [label for label in labels if label not in products]

        if missing:
            raise ValueError(
                "Metadata missing for model classes: " + ", ".join(missing)
            )

        return {label: products[label] for label in labels}

    except (OSError, ValueError, csv.Error) as error:
        raise HTTPException(
            status_code=503,
            detail=(
                "Medicine metadata could not be loaded. "
                "Check data/medicine_metadata.csv and its class codes."
            ),
        ) from error


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
    """File availability only; this does not test model inference."""
    return OCR_PYTHON.is_file() and OCR_WORKER.is_file()


@app.get("/")
def home():
    return {
        "message": "Medicine recognition API running",
        "component": 4,
        "mode": "live",
        "scope": "MEDISEG Hong Kong products",
        "prescriptionReady": False,
        "ocrConfigured": ocr_files_ready(),
    }


@app.get("/api/medicine/bootstrap")
def bootstrap():
    model = get_model()
    products = read_products(model)

    return {
        "mode": "live",
        "products": list(products.values()),
        "patients": [],
        "modelReady": True,
        "metadataReady": True,
        "prescriptionReady": False,
        "ocrConfigured": ocr_files_ready(),
        "scope": "MEDISEG Hong Kong products",
    }


@app.post("/api/medicine/detect")
def detect_photo(payload: PhotoRequest):
    model = get_model()
    products = read_products(model)
    image = decode_photo(payload.imageData)

    try:
        detections, prediction = detect_pills(image)

        for detection in detections:
            product = products.get(detection["label"])

            detection["productId"] = (
                product["id"] if product else None
            )
            detection["productName"] = (
                product["name"] if product else "Unidentified medicine"
            )
            detection["ingredients"] = (
                product["ingredients"] if product else []
            )
            detection["unmapped"] = product is None

        # plot() returns BGR; Pillow expects RGB.
        annotated_bgr = prediction.plot()
        annotated_rgb = annotated_bgr[:, :, ::-1]

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
        raise HTTPException(
            status_code=500,
            detail="Model prediction failed.",
        ) from error

    finally:
        image.close()

    return {
        "mode": "live",
        "scope": "MEDISEG Hong Kong products",
        "count": len(detections),
        "detections": detections,
        "annotatedImage": f"data:image/jpeg;base64,{encoded}",
        "requiresManualReview": True,
        "notes": (
            "Names and strengths come from reference metadata "
            "for the predicted class. Predictions require review. "
            "No prescription comparison has been performed."
        ),
    }


@app.post("/api/medicine/prescription/ocr")
def prescription_ocr(payload: PhotoRequest):
    """Run local PaddleOCR using the Python 3.13 environment."""
    if not ocr_files_ready():
        raise HTTPException(
            status_code=503,
            detail=(
                "OCR setup is missing. Check .venv-ocr and "
                "src/paddle_worker.py."
            ),
        )

    image = decode_photo(payload.imageData)
    lock_acquired = False

    try:
        # Avoid loading several OCR processes at the same time.
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

            # Keep camera orientation metadata for the OCR worker.
            image.save(
                image_path,
                format="PNG",
                exif=image.getexif(),
            )

            process = subprocess.run(
                [
                    str(OCR_PYTHON),
                    str(OCR_WORKER),
                    str(image_path),
                    str(output_path),
                ],
                cwd=str(COMPONENT_DIR),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=180,
                check=False,
            )

            if process.returncode != 0:
                logger.error(
                    "OCR worker exited with code %s",
                    process.returncode,
                )
                raise HTTPException(
                    status_code=503,
                    detail=(
                        "Prescription OCR failed. Test "
                        "prescription_paddle.py directly to check the setup."
                    ),
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
        raise HTTPException(
            status_code=504,
            detail="OCR took too long. Try a smaller, clearer photo.",
        ) from error

    except (OSError, ValueError) as error:
        raise HTTPException(
            status_code=500,
            detail="Could not process the prescription photo.",
        ) from error

    finally:
        image.close()

        if lock_acquired:
            OCR_LOCK.release()


@app.get("/api/medicine/patients/{patient_id}/prescription")
def get_prescription(patient_id: str):
    raise HTTPException(
        status_code=503,
        detail="Patient and prescription records are not connected yet.",
    )


@app.get("/api/medicine/history")
def history():
    return []


@app.post("/api/medicine/verify")
def verify_medicine():
    raise HTTPException(
        status_code=503,
        detail=(
            "Prescription verification is not connected yet. "
            "Use /api/medicine/detect for model predictions."
        ),
    )