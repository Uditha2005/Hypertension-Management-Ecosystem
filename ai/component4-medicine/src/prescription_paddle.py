"""Local OCR transcription with reviewable medicine candidate filtering."""
import argparse
import json
import math
import re
import time
from functools import lru_cache
from pathlib import Path
from statistics import median
from threading import Lock

import numpy as np
from paddleocr import PaddleOCR
from PIL import Image, ImageOps, ImageFilter

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
    """Preserve ambiguous symbols instead of manufacturing a numeric dose."""
    notes = []
    for match in SHORTHAND.finditer(text):
        if not match.group(1).isdigit() or not match.group(2).isdigit():
            notes.append(
                f"Ambiguous OCR shorthand '{match.group()}': not converted to digits. Review the image."
            )
    return text, notes


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


# Geometry associates recognized dose fragments; it cannot recover an
# unrecognized digit by itself. No medicine dictionary or dose default is used.
DOSE_FRAGMENT = re.compile(
    r"(?:[0-9Il/|]+(?:\s*[x×]\s*[0-9Il/|]+)?"
    r"(?:\s*(?:tabs?|tablets?|caps?|capsules?))?"
    r"|tabs?|tablets?|caps?|capsules?|od|qd|bd|bid|tds|tid|qid|prn)\.?", re.I
)
EXPLICIT_TABLET_DOSE = re.compile(
    r"(?<![\w./+\-])([1-9]\d?)\s*(?:tabs?|tablets?|caps?|capsules?)\.?(?![\w/])", re.I
)
NUMERIC_SHORTHAND = re.compile(r"(?<![\w./+\-])([1-9]\d?)\s*[x×]\s*([1-4])(?![\w/×x])", re.I)
OCR_BUDGET_SECONDS = 60
MAX_ROW_RETRIES = 5
RETRY_MIN_SCORE = 0.75


def dose_signature(text):
    matches = list(EXPLICIT_TABLET_DOSE.finditer(text))
    if len(matches) == 1:
        return ("tablets", int(matches[0].group(1)))
    shorthand = list(NUMERIC_SHORTHAND.finditer(text))
    if len(shorthand) == 1:
        return ("shorthand", int(shorthand[0].group(1)), int(shorthand[0].group(2)))
    return None


def link_dose_columns(lines):
    """Attach only uniquely aligned right-hand instruction fragments.

    Separate medicine rows and ambiguous/tied alignments remain separate.
    All attached line IDs, boxes and text are retained in the result.
    """
    anchors = [line for line in lines if is_medicine_candidate(line["text"])]
    attached = {id(anchor): [] for anchor in anchors}
    used = set()
    for line in lines:
        if line in anchors or not DOSE_FRAGMENT.fullmatch(line["text"].strip()):
            continue
        x1, y1, x2, y2 = line["bbox"]
        h = max(1, y2 - y1)
        cy = (y1 + y2) / 2
        candidates = []
        for anchor in anchors:
            ax1, ay1, ax2, ay2 = anchor["bbox"]
            ah = max(1, ay2 - ay1)
            acy = (ay1 + ay2) / 2
            overlap = max(0, min(y2, ay2) - max(y1, ay1))
            if (x1 >= ax2 - 0.1 * ah
                    and 0.25 <= h / ah <= 3
                    and overlap >= 0.35 * min(h, ah)
                    and abs(cy - acy) <= 0.6 * max(h, ah)):
                candidates.append((abs(cy - acy), anchor))
        candidates.sort(key=lambda pair: pair[0])
        if not candidates:
            continue
        if len(candidates) > 1 and candidates[1][0] - candidates[0][0] <= 0.25 * h:
            continue
        anchor = candidates[0][1]
        attached[id(anchor)].append(line)
        used.add(id(line))
    output = []
    for line in lines:
        if id(line) in used:
            continue
        pieces = [line] + attached.get(id(line), [])
        if len(pieces) == 1:
            output.append(dict(line))
            continue
        pieces.sort(key=lambda part: part["bbox"][0])
        output.append({
            **line,
            "text": " ".join(part["text"].strip() for part in pieces),
            "confidence": min(part["confidence"] for part in pieces),
            "bbox": [min(p["bbox"][0] for p in pieces), min(p["bbox"][1] for p in pieces),
                     max(p["bbox"][2] for p in pieces), max(p["bbox"][3] for p in pieces)],
            "sourceLineIds": [i for p in pieces for i in p["sourceLineIds"]],
            "assembledFromFragments": True,
            "assemblyChanges": [change for p in pieces for change in p.get("assemblyChanges", [])] + [{
                "reason": "Uniquely aligned instruction column attached to medicine row",
                "parts": [{"text": p["text"], "bbox": p["bbox"], "sourceLineIds": p["sourceLineIds"]} for p in pieces],
                "requiresManualReview": True,
            }],
        })
    output.sort(key=lambda line: (line["bbox"][1], line["bbox"][0]))
    return [{**line, "lineId": index + 1} for index, line in enumerate(output)]


def result_blocks(results, scale=1.0, offset=(0, 0)):
    """Validate OCR output and map crop coordinates back to the page."""
    blocks = []
    for result in results:
        texts, scores, boxes = result["rec_texts"], result["rec_scores"], result["rec_boxes"]
        if not (len(texts) == len(scores) == len(boxes)):
            raise RuntimeError("OCR returned inconsistent text results.")
        for text, score, box in zip(texts, scores, boxes):
            score = float(score)
            values = np.asarray(box, dtype=float).reshape(-1).tolist()
            if not math.isfinite(score) or not 0 <= score <= 1:
                raise RuntimeError("OCR returned an invalid confidence score.")
            if len(values) != 4 or not all(math.isfinite(v) for v in values):
                raise RuntimeError("OCR returned an invalid bounding box.")
            mapped = [values[0] / scale + offset[0], values[1] / scale + offset[1],
                      values[2] / scale + offset[0], values[3] / scale + offset[1]]
            if mapped[2] <= mapped[0] or mapped[3] <= mapped[1]:
                raise RuntimeError("OCR returned an empty bounding box.")
            blocks.append({"lineId": len(blocks) + 1, "text": str(text),
                           "confidence": score, "bbox": [round(v, 2) for v in mapped],
                           "requiresManualReview": True})
    return blocks


def predict_page(ocr, image):
    # Keep weak recognized fragments in the audit output; do not inflate scores.
    bgr = np.asarray(image)[:, :, ::-1].copy()
    return list(ocr.predict(
        input=bgr, text_det_thresh=0.2, text_det_box_thresh=0.35,
        text_det_limit_side_len=1600, text_det_limit_type="max",
        text_rec_score_thresh=0.0,
    ))


def choose_retry(original, candidates):
    """Accept one source-backed dose transcript; reject conflicting numbers."""
    candidates = [c for c in candidates if is_medicine_candidate(c["text"])
                  and dose_signature(c["text"]) is not None and c["confidence"] >= RETRY_MIN_SCORE]
    if not candidates or len({dose_signature(c["text"]) for c in candidates}) != 1:
        return None
    original_height = max(1, original["bbox"][3] - original["bbox"][1])
    original_center = (original["bbox"][1] + original["bbox"][3]) / 2
    candidates = [c for c in candidates
                  if abs((c["bbox"][1] + c["bbox"][3]) / 2 - original_center) <= original_height]
    if len(candidates) != 1:
        return None
    return candidates[0]


def retry_missing_doses(image, blocks, ocr, started):
    """Retry only bounded medicine rows, using the same cached local models."""
    rows = sorted(blocks, key=lambda b: (b["bbox"][1] + b["bbox"][3]) / 2)
    retry_records = []
    updated = []
    attempted = 0
    for index, row in enumerate(rows):
        if dose_signature(row["text"]) is not None or attempted >= MAX_ROW_RETRIES or time.monotonic() - started >= OCR_BUDGET_SECONDS:
            updated.append(row)
            continue
        x1, y1, x2, y2 = row["bbox"]
        height = max(1, y2 - y1)
        center = (y1 + y2) / 2
        upper = max(0, y1 - 0.65 * height)
        lower = min(image.height, y2 + 0.65 * height)
        if index:
            prev = rows[index - 1]["bbox"]
            upper = max(upper, (center + (prev[1] + prev[3]) / 2) / 2)
        if index + 1 < len(rows):
            following = rows[index + 1]["bbox"]
            lower = min(lower, (center + (following[1] + following[3]) / 2) / 2)
        crop_box = (max(0, int(x1 - height)), int(upper), image.width, int(lower))
        if crop_box[3] <= crop_box[1] or crop_box[2] <= crop_box[0]:
            updated.append(row)
            continue
        attempted += 1
        record = {"rowLineId": row["lineId"], "originalText": row["text"],
                  "cropBox": list(crop_box), "accepted": False, "requiresManualReview": True}
        try:
            with image.crop(crop_box) as crop:
                scale = min(2.0, 2400 / max(crop.size))
                with crop.resize((max(1, round(crop.width * scale)), max(1, round(crop.height * scale))), Image.Resampling.LANCZOS) as enlarged:
                    with ImageOps.autocontrast(enlarged) as contrast:
                        with contrast.filter(ImageFilter.UnsharpMask(radius=1, percent=110, threshold=3)) as enhanced:
                            with OCR_LOCK:
                                print(f"[prescription OCR] Retrying medicine row {index + 1}...", flush=True)
                                retry_raw = result_blocks(predict_page(ocr, enhanced), scale, crop_box[:2])
            retry_lines = link_dose_columns(assemble_lines(retry_raw))
            record["rawBlocks"] = retry_raw
            record["assembledBlocks"] = retry_lines
            chosen = choose_retry(row, retry_lines)
            if chosen:
                replacement = {**chosen, "lineId": row["lineId"],
                               "sourceLineIds": row["sourceLineIds"],
                               "originalOcrText": row["text"], "transcriptionSource": "row-crop-retry",
                               "rowRetryIndex": len(retry_records),
                               "assemblyChanges": row.get("assemblyChanges", []) + [{
                                   "reason": "New OCR transcript from an enlarged, isolated medicine row; verify against image",
                                   "originalText": row["text"], "retryText": chosen["text"],
                                   "requiresManualReview": True}]}
                record["accepted"] = True
                record["selectedText"] = chosen["text"]
                updated.append(replacement)
            else:
                updated.append(row)
        except Exception as error:
            # Preserve the successful first pass if an optional retry fails.
            record["errorType"] = type(error).__name__
            updated.append(row)
        retry_records.append(record)
    return updated, retry_records


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
    started = time.monotonic()
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

        with OCR_LOCK:
            print("[prescription OCR] Loading OCR models...", flush=True)
            ocr = load_ocr()
            print("[prescription OCR] Running prediction...", flush=True)
            results = predict_page(ocr, prepared)
        raw_blocks = result_blocks(results)
        assembled = link_dose_columns(assemble_lines(raw_blocks))
        first_pass_blocks = [block for block in assembled if is_medicine_candidate(block["text"])]
        blocks, row_retries = retry_missing_doses(prepared, first_pass_blocks, ocr, started)

        # Flag ambiguous shorthand without substituting a numeric dose.
        shorthand_notes = []
        for block in blocks:
            fixed, notes = repair_shorthand(block["text"])
            if notes:
                block.setdefault("originalOcrText", block["text"])
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
        accepted_retries = sum(record["accepted"] for record in row_retries)
        if accepted_retries:
            warnings.append(f"Used enlarged row-crop OCR for {accepted_retries} row(s). Verify new text against originalOcrText and the image.")
        if any(dose_signature(block["text"]) is None for block in blocks):
            warnings.append("Some doses remain unread. No missing numeric dose was defaulted to one.")
        if time.monotonic() - started >= OCR_BUDGET_SECONDS:
            warnings.append("Optional crop retries stopped at the processing budget; remaining rows need review.")
        if any(change.get("removedDuplicatePrefix") for b in assembled for change in b["assemblyChanges"]):
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
            "firstPassBlocks": first_pass_blocks, "rowRetries": row_retries,
            "rowRetryCount": len(row_retries), "acceptedRowRetryCount": accepted_retries,
            "numericDoseRepairApplied": False,
            "assembledText": "\n".join(b["text"] for b in assembled),
            "assembledBlocks": assembled, "assembledLineCount": len(assembled),
            "fragmentJoinedLineCount": merged_count,
            "filterMethod": "aligned_dose_columns_and_row_retries_v6", "filterMessage": message,
            "warnings": warnings, "requiresManualReview": True,
            "confirmed": False, "comparisonPerformed": False,
            "notes": message + " Original OCR blocks are preserved in rawBlocks; overlap-edge deduplication is recorded in assemblyChanges and row retries in rowRetries. Ambiguous handwritten symbols were not converted to numbers. Medicine identity, strengths and instructions are unverified. Confidence scores do not guarantee correctness.",
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