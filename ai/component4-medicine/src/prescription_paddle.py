"""Local OCR transcription with reviewable medicine candidate filtering."""
import argparse
import json
import math
import re
from functools import lru_cache
from pathlib import Path
from threading import Lock

import numpy as np
from paddleocr import PaddleOCR
from PIL import Image, ImageOps

COMPONENT_DIR = Path(__file__).resolve().parent.parent
OCR_LOCK = Lock()
MEDICINE_PREFIX = re.compile(
    r"^\s*(?:[-–—•]\s*)?(?:tab(?:let)?s?|t[adq]b|cap(?:sule)?s?|"
    r"syr(?:up)?|inj(?:ection)?|in(?=\s*[-:])|[TPD])"
    r"(?:\s*[.:\-–—]\s*|\s+)\S", re.I
)
STRENGTH = re.compile(
    r"(?<![\w.])\d+(?:\.\d+)?\s*(?:mcg|µg|mg|g|ml|iu|%)(?!\w)", re.I
)
NON_MEDICINE = re.compile(
    r"^\s*(?:name|age|sex|gender|address|date|dr\.?|doctor|signature|"
    r"refill|label|phone|mobile|mob|tel|weight|wt|height|temp(?:erature)?|"
    r"pulse|hr|spo2|b\.?\s*p\.?|blood\s+(?:pressure|sugar|glucose)|"
    r"glucose|fbs|rbs|hba1c|cholesterol|creatinine|sodium|potassium)\b", re.I
)


def is_medicine_candidate(text):
    """Select possible medicine lines, never validate their drug identity."""
    text = text.strip()
    if not text or NON_MEDICINE.match(text):
        return False
    if MEDICINE_PREFIX.match(text):
        return True
    # Some prescriptions start directly with the brand/name, e.g.
    # 'Betaloc 100mg - I tab BID'. Preserve the OCR spelling unchanged.
    match = STRENGTH.search(text)
    if match is None:
        return False
    before = re.sub(r"^\s*(?:[-–—•]|\d+[.)])\s*", "", text[:match.start()]).strip()
    return bool(re.search(r"[A-Za-z]{2,}", before)) and len(before) <= 120


@lru_cache(maxsize=1)
def load_ocr():
    return PaddleOCR(
        lang="en", ocr_version="PP-OCRv5", device="cpu",
        text_detection_model_name="PP-OCRv5_mobile_det",
        text_recognition_model_name="en_PP-OCRv5_mobile_rec",
        cpu_threads=4, enable_mkldnn=False,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False, use_textline_orientation=False,
    )


def read_prescription(image):
    if image.width * image.height > 20_000_000:
        raise ValueError("Choose an image no larger than 20 megapixels.")
    prepared = ImageOps.exif_transpose(image).convert("RGB")
    try:
        image_bgr = np.asarray(prepared)[:, :, ::-1].copy()
        with OCR_LOCK:
            print("[prescription OCR] Loading OCR models...", flush=True)
            ocr = load_ocr()
            print("[prescription OCR] Running prediction...", flush=True)
            results = list(ocr.predict(input=image_bgr))
        raw_blocks = []
        for result in results:
            texts, scores, boxes = result["rec_texts"], result["rec_scores"], result["rec_boxes"]
            if not (len(texts) == len(scores) == len(boxes)):
                raise RuntimeError("OCR returned inconsistent text results.")
            for text, score, box in zip(texts, scores, boxes):
                score = float(score)
                values = [float(value) for value in box]
                if not math.isfinite(score) or not 0 <= score <= 1:
                    raise RuntimeError("OCR returned an invalid confidence score.")
                if len(values) != 4 or not all(math.isfinite(value) for value in values):
                    raise RuntimeError("OCR returned an invalid bounding box.")
                raw_blocks.append({
                    "lineId": len(raw_blocks) + 1, "text": str(text),
                    "confidence": score, "bbox": [int(value) for value in values],
                    "requiresManualReview": True,
                })
        blocks = [block for block in raw_blocks if is_medicine_candidate(block["text"])]
        raw_text = "\n".join(b["text"] for b in raw_blocks if b["text"].strip())
        text = "\n".join(b["text"] for b in blocks)
        message = (
            "Possible medicine rows selected by a prescription prefix or a name "
            "followed by a strength. Selection is heuristic and can miss rows or "
            "include other text. Check the original prescription."
        )
        warnings = []
        if min(prepared.size) < 600:
            warnings.append("Small image: medicine handwriting may be hard to recognise.")
        if not raw_text:
            warnings.append("OCR did not recognise text. Try a close, sharp photo or enter text manually.")
        elif not blocks:
            warnings.append("OCR recognised text, but no medicine candidates matched. Review rawText or enter medicine rows manually.")
        return {
            "engine": "PaddleOCR", "model": "PP-OCRv5",
            "detectionModel": "PP-OCRv5_mobile_det",
            "recognitionModel": "en_PP-OCRv5_mobile_rec", "language": "en",
            "imageSize": {"width": prepared.width, "height": prepared.height},
            "text": text, "blocks": blocks, "medicineCandidateCount": len(blocks),
            "detectedRegionCount": len(raw_blocks), "rawText": raw_text,
            "rawBlocks": raw_blocks, "filterApplied": True,
            "filterMethod": "prefix_or_name_and_strength_v2", "filterMessage": message,
            "warnings": warnings, "requiresManualReview": True,
            "confirmed": False, "comparisonPerformed": False,
            "notes": message + " Original OCR spelling is preserved. Medicine identity, strengths and instructions are unverified. Confidence scores do not guarantee correctness.",
        }
    finally:
        prepared.close()


def main():
    parser = argparse.ArgumentParser(description="Read prescription text using local PaddleOCR.")
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
        output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as error:
        print(f"\nOCR failed: {type(error).__name__}: {error}")
        print("No new result was saved. Older output files may still exist.")
        raise SystemExit(1)
    print("\nMEDICINE CANDIDATE TEXT")
    print(payload["text"] or "No medicine candidate lines were selected.")
    print(f"\nSaved result: {output_path}")
    print("Review required. Prescription is not confirmed.")


if __name__ == "__main__":
    main()
