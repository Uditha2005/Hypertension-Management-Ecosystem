import base64
import binascii
from io import BytesIO

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field

from detect import detect_pills, load_model


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
            detail="Choose a valid JPG, PNG or WebP photo under 5 MB "
                   "and no larger than 20 megapixels.",
        ) from error


@app.get("/")
def home():
    return {
        "message": "Medicine recognition API running",
        "component": 4,
        "mode": "live",
        "scope": "MEDISEG Hong Kong products",
        "prescriptionReady": False,
    }


@app.get("/api/medicine/bootstrap")
def bootstrap():
    model = get_model()

    products = [
        {
            "id": label,
            "name": label,
            "strength": "",
            "brand": "",
            "formulation": "",
        }
        for label in model.names.values()
        if label != "pills"
    ]

    return {
        "mode": "live",
        "products": products,
        "patients": [],
        "modelReady": True,
        "prescriptionReady": False,
        "scope": "MEDISEG Hong Kong products",
    }


@app.post("/api/medicine/detect")
def detect_photo(payload: PhotoRequest):
    get_model()
    image = decode_photo(payload.imageData)

    try:
        detections, prediction = detect_pills(image)

        # Ultralytics plot() returns a BGR image.
        annotated_bgr = prediction.plot()
        annotated_rgb = annotated_bgr[:, :, ::-1]
        annotated_image = Image.fromarray(annotated_rgb)

        buffer = BytesIO()
        annotated_image.save(buffer, format="JPEG", quality=85)

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
        "notes": "Model predictions require review. "
                 "No prescription comparison has been performed.",
    }


@app.get("/api/medicine/patients/{patient_id}/prescription")
def get_prescription(patient_id: str):
    raise HTTPException(
        status_code=503,
        detail="Patient and prescription records are not connected yet.",
    )


@app.get("/api/medicine/history")
def history():
    # No prescription verification records are created by this API yet.
    return []


@app.post("/api/medicine/verify")
def verify_medicine():
    raise HTTPException(
        status_code=503,
        detail="Prescription verification is not connected yet. "
               "Use /api/medicine/detect for model predictions.",
    )