"""Local OCR transcription with reviewable medicine candidate filtering."""
import argparse
import json
import math
import re
from functools import lru_cache
from pathlib import Path
from statistics import median
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

# Handwritten "1" is often read as / | I l. Applied only to the two digit
# positions of an "A x B" shorthand, never elsewhere in the text.
SHORTHAND_TOKEN = r"(?:[1-9]|[/|Il])"
SHORTHAND = re.compile(
    rf"(?<![\w./|])({SHORTHAND_TOKEN})\s*[x×]\s*({SHORTHAND_TOKEN})(?![\w/|])",
    re.I,
)


def repair_shorthand(text):
    """Return (text, corrections) after fixing '1x/' style digit misreads."""
    corrections = []

    def replace(match):
        first, second = match.group(1), match.group(2)
        fixed_first = first if first.isdigit() else "1"
        fixed_second = second if second.isdigit() else "1"
        original = match.group().strip()
        fixed = f"{fixed_first}x{fixed_second}"
        if original.replace(" ", "") != fixed:
            corrections.append(
                f"OCR shorthand '{original}' read as '{fixed}'. "
                "Verify against the image."
            )
        return fixed

    return SHORTHAND.sub(replace, text), corrections


def is_medicine_candidate(text):
    """Select possible medicine lines, never validate their drug identity."""
    text = text.strip()
    if not text or NON_MEDICINE.match(text):
        return False
    if MEDICINE_PREFIX.match(text):
        return True
    match = STRENGTH.search(text)
    if match is None:
        return False
    before = re.sub(r"^\s*(?:[-–—•]|\d+[.)])\s*", "", text[:match.start()]).strip()
    return bool(re.search(r"[A-Za-z]{2,}", before)) and len(before) <= 120


def join_fragments(parts):
    """Join fragments and audit exact duplicated text at overlapping edges.

    No dictionary corrections or guessed medicine names are applied.
    Edge deduplication is heuristic and remains subject to manual review.
    """
    text = parts[0]["text"].strip()
    changes = []
    for previous, part in zip(parts, parts[1:]):
        right = part["text"].strip()
        left = previous["text"].strip()
        overlap = previous["bbox"][2] - part["bbox"][0]
        removed = ""
        if overlap > 0:
            left_char = (previous["bbox"][2] - previous["bbox"][0]) / max(1, len(left))
            right_char = (part["bbox"][2] - part["bbox"][0]) / max(1, len(right))
            for size in range(min(len(left), len(right), 12), 0, -1):
                suffix, prefix = left[-size:], right[:size]
                if suffix != prefix or not prefix.strip() or any(c.isdigit() for c in prefix):
                    continue
                if size < len(right) and right[size].isalpha():
                    continue
                estimate = size * (left_char + right_char) / 2
                if not 0.45 * estimate <= overlap <= 1.8 * estimate:
                    continue
                removed = prefix
                right = right[size:].lstrip()
                break
        if removed:
            changes.append({
                "sourceLineIds": [previous["lineId"], part["lineId"]],
                "removedDuplicatePrefix": removed,
                "reason": "Exact suffix/prefix at overlapping OCR box edges",
                "requiresManualReview": True,
            })
        if right:
            text += " " + right
    return text, changes


def assemble_lines(raw_blocks):
    """Join close horizontal fragments only; preserve every original block."""
    visible = [b for b in raw_blocks if b["text"].strip()]
    heights = [b["bbox"][3] - b["bbox"][1] for b in visible
               if b["bbox"][3] > b["bbox"][1]]
    typical_height = median(heights) if heights else 1
    groups = []
    for block in sorted(visible, key=lambda b: ((b["bbox"][1] + b["bbox"][3]) / 2,
                                               b["bbox"][0], b["lineId"])):
        x1, y1, x2, y2 = block["bbox"]
        height = max(1, y2 - y1)
        center = (y1 + y2) / 2
        candidates = []
        for index, group in enumerate(groups):
            compatible = True
            for part in group:
                px1, py1, px2, py2 = part["bbox"]
                pheight = max(1, py2 - py1)
                overlap = max(0, min(y2, py2) - max(y1, py1))
                if (height > 2.5 * typical_height or pheight > 2.5 * typical_height
                        or height / pheight < .5 or height / pheight > 2
                        or overlap < .65 * min(height, pheight)
                        or abs(center - (py1 + py2) / 2) > .35 * min(height, pheight)):
                    compatible = False
                    break
            if compatible:
                distance = abs(center - median((p["bbox"][1] + p["bbox"][3]) / 2 for p in group))
                candidates.append((distance, index))
        if candidates:
            groups[min(candidates)[1]].append(block)
        else:
            groups.append([block])
    horizontal_groups = []
    for group in groups:
        current = []
        for part in sorted(group, key=lambda b: (b["bbox"][0], b["lineId"])):
            if current:
                previous = current[-1]
                gap = part["bbox"][0] - previous["bbox"][2]
                limit = max(20, 2.5 * min(part["bbox"][3] - part["bbox"][1],
                                         previous["bbox"][3] - previous["bbox"][1]))
                allowed_overlap = min(
                    0.6 * min(part["bbox"][3] - part["bbox"][1],
                              previous["bbox"][3] - previous["bbox"][1]),
                    0.6 * min(part["bbox"][2] - part["bbox"][0],
                              previous["bbox"][2] - previous["bbox"][0]),
                )
                if gap < -allowed_overlap or gap > limit:
                    horizontal_groups.append(current)
                    current = []
            current.append(part)
        if current:
            horizontal_groups.append(current)
    assembled = []
    for parts in horizontal_groups:
        joined_text, changes = join_fragments(parts)
        assembled.append({
            "text": joined_text,
            "assemblyChanges": changes,
            "confidence": min(p["confidence"] for p in parts),
            "bbox": [min(p["bbox"][0] for p in parts),
                     min(p["bbox"][1] for p in parts),
                     max(p["bbox"][2] for p in parts),
                     max(p["bbox"][3] for p in parts)],
            "sourceLineIds": [p["lineId"] for p in parts],
            "assembledFromFragments": len(parts) > 1,
            "requiresManualReview": True,
        })
    assembled.sort(key=lambda b: (b["bbox"][1], b["bbox"][0]))
    return [{"lineId": index + 1, **block} for index, block in enumerate(assembled)]


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
    oriented = ImageOps.exif_transpose(image)
    try:
        prepared = oriented.convert("RGB")
    finally:
        oriented.close()
    try:
        # Small photos give poor handwriting recognition; enlarge modestly.
        long_side = max(prepared.size)
        if long_side < 1400:
            scale = 1600 / long_side
            enlarged = prepared.resize(
                (round(prepared.width * scale), round(prepared.height * scale)),
                Image.LANCZOS,
            )
            prepared.close()
            prepared = enlarged

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
                values = np.asarray(box, dtype=float).reshape(-1).tolist()
                if not math.isfinite(score) or not 0 <= score <= 1:
                    raise RuntimeError("OCR returned an invalid confidence score.")
                if len(values) != 4 or not all(math.isfinite(value) for value in values):
                    raise RuntimeError("OCR returned an invalid bounding box.")
                if values[2] <= values[0] or values[3] <= values[1]:
                    raise RuntimeError("OCR returned an empty or inverted bounding box.")
                raw_blocks.append({
                    "lineId": len(raw_blocks) + 1, "text": str(text),
                    "confidence": score, "bbox": [int(value) for value in values],
                    "requiresManualReview": True,
                })
        assembled = assemble_lines(raw_blocks)
        blocks = [block for block in assembled if is_medicine_candidate(block["text"])]

        # Flagged correction of misread handwritten "1" in shorthand.
        shorthand_notes = []
        for block in blocks:
            fixed, notes = repair_shorthand(block["text"])
            if notes:
                block["originalOcrText"] = block["text"]
                block["text"] = fixed
                block["shorthandCorrections"] = notes
                shorthand_notes.extend(notes)

        merged_count = sum(block["assembledFromFragments"] for block in assembled)
        print(f"[prescription OCR] {len(raw_blocks)} regions -> "
              f"{len(assembled)} reconstructed lines -> {len(blocks)} medicine candidates", flush=True)
        raw_text = "\n".join(b["text"] for b in raw_blocks if b["text"].strip())
        text = "\n".join(b["text"] for b in blocks)
        message = (
            "Possible medicine rows selected by a prescription prefix or a name "
            "followed by a strength, after joining close horizontal OCR fragments. "
            "Selection and line assembly are heuristic and can miss rows or "
            "include other text. Check the original prescription."
        )
        warnings = list(shorthand_notes)
        if any(b["assemblyChanges"] for b in assembled):
            warnings.append("Exact duplicated edge text was removed from overlapping fragments. Review assemblyChanges and rawBlocks against the image.")
        if merged_count:
            warnings.append(f"Joined fragments in {merged_count} lines. Check names, strengths and quantities against the image.")
        if any(b["confidence"] < .8 for b in blocks):
            warnings.append("Some medicine candidates contain low-confidence OCR text. Manual review is required.")
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
            "assembledText": "\n".join(b["text"] for b in assembled),
            "assembledBlocks": assembled, "assembledLineCount": len(assembled),
            "fragmentJoinedLineCount": merged_count,
            "filterMethod": "overlap_aware_lines_v5", "filterMessage": message,
            "warnings": warnings, "requiresManualReview": True,
            "confirmed": False, "comparisonPerformed": False,
            "notes": message + " Original OCR blocks are preserved in rawBlocks; overlap-edge deduplication is recorded in assemblyChanges and shorthand fixes in originalOcrText. Medicine identity, strengths and instructions are unverified. Confidence scores do not guarantee correctness.",
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
        output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
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