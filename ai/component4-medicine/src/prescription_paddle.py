import argparse
import json
from functools import lru_cache
from pathlib import Path
from threading import Lock

import numpy as np
from paddleocr import PaddleOCR
from PIL import Image, ImageOps


COMPONENT_DIR = Path(__file__).resolve().parent.parent
OCR_LOCK = Lock()


@lru_cache(maxsize=1)
def load_ocr():
    """Load once and reuse the downloaded models."""
    return PaddleOCR(
        lang="en",
        ocr_version="PP-OCRv5",
        device="cpu",
        # Avoid the oneDNN error encountered on this computer.
        enable_mkldnn=False,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
    )


def read_prescription(image):
    """Extract text only; do not confirm medicines or infer dosages."""
    if image.width * image.height > 20_000_000:
        raise ValueError("Choose an image no larger than 20 megapixels.")

    prepared = ImageOps.exif_transpose(image).convert("RGB")

    try:
        # OpenCV/PaddleOCR image arrays use BGR channel order.
        image_bgr = np.asarray(prepared)[:, :, ::-1].copy()

        with OCR_LOCK:
            ocr = load_ocr()
            results = ocr.predict(input=image_bgr)

        blocks = []

        for result in results:
            texts = result["rec_texts"]
            scores = result["rec_scores"]
            boxes = result["rec_boxes"]

            if not (len(texts) == len(scores) == len(boxes)):
                raise RuntimeError("OCR returned inconsistent text results.")

            for text, score, box in zip(texts, scores, boxes):
                blocks.append({
                    "lineId": len(blocks) + 1,
                    "text": str(text),
                    "confidence": float(score),
                    "bbox": [int(value) for value in box],
                    "requiresManualReview": True,
                })

        return {
            "engine": "PaddleOCR",
            "model": "PP-OCRv5",
            "language": "en",
            "imageSize": {
                "width": prepared.width,
                "height": prepared.height,
            },
            "detectedRegionCount": len(blocks),
            "text": "\n".join(
                block["text"] for block in blocks
                if block["text"].strip()
            ),
            "blocks": blocks,
            "requiresManualReview": True,
            "confirmed": False,
            "comparisonPerformed": False,
            "notes": (
                "Unverified OCR transcription. Review the original image "
                "before using medicine names, strengths or instructions. "
                "Confidence scores do not guarantee correctness. "
                "No medicine fields have been inferred or confirmed."
            ),
        }
    finally:
        prepared.close()


def main():
    parser = argparse.ArgumentParser(
        description="Read prescription text using local PaddleOCR."
    )
    parser.add_argument("image", type=Path)
    args = parser.parse_args()

    if not args.image.is_file():
        parser.error(f"Image not found: {args.image}")

    try:
        with Image.open(args.image) as image:
            payload = read_prescription(image)

        output_dir = COMPONENT_DIR / "outputs" / "ocr" / "paddle"
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / f"{args.image.stem}_paddle.json"
        output_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    except Exception as error:
        print(f"\nOCR failed: {type(error).__name__}: {error}")
        print("No new result was saved. Older output files may still exist.")
        raise SystemExit(1)

    print("\nEXTRACTED TEXT")
    print(payload["text"] or "No text was recognised.")
    print(f"\nSaved result: {output_path}")
    print("Review required. Prescription is not confirmed.")


if __name__ == "__main__":
    main()