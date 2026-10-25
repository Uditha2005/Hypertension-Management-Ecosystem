"""Build editable medicine drafts from OCR text.

LLM output is checked against the supplied text.
A local fallback is explicitly marked when LLM extraction fails.
Automatic corrections made by prescription_draft are always recorded in
the row's review notes. Treatment doses are never guessed.
"""

import json
import logging
import os
import re
import urllib.error
import urllib.request

from prescription_draft import build_draft


API_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-oss-20b"

logger = logging.getLogger("uvicorn.error")

FIELDS = (
    "sourceText",
    "medicineName",
    "strength",
    "doseText",
    "scheduleText",
    "durationText",
)

PROPERTIES = {
    field: {"type": "string"}
    for field in FIELDS
}
PROPERTIES["warnings"] = {
    "type": "array",
    "items": {"type": "string"},
}

SCHEMA = {
    "type": "object",
    "properties": {
        "rows": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": PROPERTIES,
                "required": list(PROPERTIES),
                "additionalProperties": False,
            },
        },
    },
    "required": ["rows"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """
Extract medicine instructions from untrusted OCR text.

Return one row per medicine instruction.
Exclude headings, patient details, signatures and unrelated text.

Rules:
- Copy the COMPLETE sourceText from the input.
- Include all conditions and changing-dose instructions in sourceText.
- Copy medicineName, strength, doseText, scheduleText and durationText
  from that sourceText without correcting spelling or numbers.
- Use empty strings for absent or unclear fields.
- Copy an explicit phrase such as "1 tab" into doseText even when no
  frequency is written. Missing frequency does not erase an explicit dose.
- Never invent a missing decimal point.
- Never replace an OCR medicine name using medical knowledge.
- Never infer dose from strength or the medicine name.
- Never interpret supply totals as a dose.
- For shorthand such as "1x3" or "2 x 3", copy the whole shorthand
  into doseText. Leave scheduleText empty unless a separate explicit
  schedule phrase is present. Do not interpret the shorthand yourself.
- Preserve fractions, conditions, variable doses and abbreviations.
- Explain uncertainties in warnings.
- Return an empty rows array if there are no medicine instructions.
"""

DAILY_SCHEDULES = {
    "once daily": 1,
    "once a day": 1,
    "once per day": 1,
    "daily": 1,
    "od": 1,
    "qd": 1,
    "every morning": 1,
    "every evening": 1,
    "every night": 1,
    "at night": 1,
    "twice daily": 2,
    "twice a day": 2,
    "twice per day": 2,
    "bd": 2,
    "bid": 2,
    "three times daily": 3,
    "three times a day": 3,
    "three times per day": 3,
    "tds": 3,
    "tid": 3,
    "four times daily": 4,
    "four times a day": 4,
    "four times per day": 4,
    "qid": 4,
}

VARIABLE_INSTRUCTION = re.compile(
    r"\b(?:prn|if|when|needed|required|alternate|weekly|then|"
    r"taper|increase|decrease|except|depending|or)\b"
    r"|\bevery\s+other\b"
    r"|\bas\s+directed\b",
    re.I,
)

DOSE = re.compile(
    r"([1-9]\d?)\s*(?:tabs?|tablets?|caps?|capsules?)\.?",
    re.I,
)

# Restrict automatic shorthand interpretation to a terminal expression.
# This prevents a partial match in 1x3x7, 1/2x3 or additional instructions.
SHORTHAND_END = re.compile(
    r"(?<![\w./×x+\-])"
    r"(?P<dose>[1-9]\d?)\s*[x×]\s*(?P<frequency>[1-4])"
    r"\s*[.;]?\s*$",
    re.I,
)

# Used only to separate a trailing uncertain shorthand from the name.
UNCLEAR_SHORTHAND_END = re.compile(
    r"\s+(?P<instruction>[0-9Il/?.]+\s*[x×]\s*[0-9Il/?.]+)"
    r"\s*$",
    re.I,
)

TABLET_PREFIX = re.compile(
    r"^\s*(?:\d+[.)]\s*)?(?:tab(?:let)?s?|cap(?:sule)?s?)"
    r"(?:[.:\s]+)",
    re.I,
)

SIMPLE_MEDICINE_LINE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|ug|g|ml|iu)\b",
    re.I,
)

VALID_SCOPES = {"manual", "single-dose", "full-day"}


def normalize_space(value):
    return " ".join(value.split())


def check_input(text):
    if (
        not isinstance(text, str)
        or not text.strip()
        or len(text) > 12000
    ):
        raise ValueError(
            "Enter prescription text of at most 12,000 characters."
        )

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    if len(lines) > 50:
        raise ValueError("Use at most 50 non-empty lines.")

    return lines


def shorthand_confirmed():
    """Explicit opt-in to one shorthand convention."""
    return os.environ.get(
        "RX_SHORTHAND_CONVENTION", ""
    ).strip() == "tablets-per-dose_x_doses-per-day"


def validate_extraction(data, text):
    if not isinstance(data, dict) or set(data) != {"rows"}:
        raise ValueError("Invalid LLM response structure.")

    items = data["rows"]

    if not isinstance(items, list) or len(items) > 50:
        raise ValueError("Invalid number of medicine rows.")

    input_text = normalize_space(text)
    seen = set()
    rows = []

    for item in items:
        if not isinstance(item, dict) or set(item) != set(PROPERTIES):
            raise ValueError("Invalid extracted medicine row.")

        if any(not isinstance(item[field], str) for field in FIELDS):
            raise ValueError("Invalid extracted text field.")

        row = {
            field: item[field].strip()
            for field in FIELDS
        }

        source = normalize_space(row["sourceText"])

        if not source or source not in input_text or source in seen:
            raise ValueError(
                "Missing, duplicated or unverifiable source instruction."
            )

        seen.add(source)

        if not row["medicineName"] or len(row["medicineName"]) > 200:
            raise ValueError("Invalid extracted medicine name.")

        if len(row["strength"]) > 80:
            raise ValueError("Extracted strength is too long.")

        for field in FIELDS:
            if field == "sourceText":
                continue

            value = normalize_space(row[field])

            if value and value not in source:
                raise ValueError(
                    f"Extracted {field} was not copied from its source."
                )

        if any(
            len(row[field]) > 500
            for field in ("doseText", "scheduleText", "durationText")
        ):
            raise ValueError("Extracted instruction is too long.")

        warnings = item["warnings"]

        if (
            not isinstance(warnings, list)
            or len(warnings) > 20
            or any(
                not isinstance(warning, str) or len(warning) > 500
                for warning in warnings
            )
        ):
            raise ValueError("Invalid extraction warnings.")

        rows.append({
            **row,
            "warnings": warnings,
        })

    return rows


# Only explicit whole-tablet instructions qualify. Never repair I/l into 1.
EXPLICIT_DOSE = re.compile(
    r"(?<![\w./+\-])([1-9]\d?)\s*(?:tablets?|tabs?|capsules?|caps?)\.?(?![\w/])",
    re.I,
)
SUPPLY = re.compile(r"\b(?:dispense|supply|quantity|qty|total|pack)\b|\bno\.", re.I)
FRACTION_OR_RANGE = re.compile(
    r"\b\d+\s*(?:/|[-–])\s*\d+\s*(?:tabs?|tablets?|caps?|capsules?)\b"
    r"|\b\d+\.\d+\s*(?:tabs?|tablets?|caps?|capsules?)\b", re.I
)


def explicit_dose(row):
    """Return a source-backed whole-tablet phrase, never a default count."""
    source = normalize_space(row.get("sourceText", ""))
    if VARIABLE_INSTRUCTION.search(source) or FRACTION_OR_RANGE.search(source):
        return None
    # A source containing supply instructions needs manual review: don't
    # accidentally interpret a supplied number of tablets as a per-dose count.
    if SUPPLY.search(source):
        return None
    matches = list(EXPLICIT_DOSE.finditer(source))
    if len(matches) != 1:
        return None
    match = matches[0]
    dose = normalize_space(row.get("doseText", ""))
    if dose and dose.casefold().rstrip(".") != match.group().casefold().rstrip("."):
        return None
    return match


def calculate_tray_quantity(row, tray_scope):
    if tray_scope not in VALID_SCOPES:
        raise ValueError("Invalid tray scope.")
    if tray_scope == "manual":
        return None, "Custom tray: enter the intended quantity manually."
    source = normalize_space(row.get("sourceText", ""))
    if VARIABLE_INSTRUCTION.search(source) or FRACTION_OR_RANGE.search(source) or SUPPLY.search(source):
        return None, "Conditional, fractional, variable or supply instruction: review quantity."
    shorthand = SHORTHAND_END.search(source)
    if shorthand:
        preceding = source[:shorthand.start()]
        if (re.search(r"[x×]\s*\d", preceding, re.I)
            or re.search(r"\b(?:od|qd|bd|bid|tds|tid|qid|daily|night|morning)\b", preceding, re.I)
            or EXPLICIT_DOSE.search(preceding)):
            return None, "Multiple instruction expressions found. Review quantity."
        if not TABLET_PREFIX.search(source) or not shorthand_confirmed():
            return None, "Shorthand requires an explicit tablet form and a configured interpretation convention."
        tablets_per_dose = int(shorthand.group("dose"))
        doses_per_day = int(shorthand.group("frequency"))
        basis = "Calculated using the configured tablets-per-dose x doses-per-day convention. "
    else:
        match = explicit_dose(row)
        if match is None:
            return None, "No unambiguous whole-tablet dose was read. Check the OCR text against the image."
        tablets_per_dose = int(match.group(1))
        schedule = normalize_space(row.get("scheduleText", "")).casefold().rstrip(".")
        doses_per_day = DAILY_SCHEDULES.get(schedule)
        # A single scheduled administration needs the per-dose quantity,
        # not a daily frequency. Full-day calculations still need frequency.
        if tray_scope == "full-day" and doses_per_day is None:
            return None, "Full-day tray requires an explicit daily frequency; it was not read."
        basis = "Read explicit dose '" + match.group().strip() + "'. "
    quantity = tablets_per_dose if tray_scope == "single-dose" else tablets_per_dose * doses_per_day
    if not 1 <= quantity <= 100:
        return None, "Calculated count is outside the supported range."
    if tray_scope == "single-dose":
        return quantity, basis + f"{quantity} tablet(s) for ONE dose. Frequency was not assumed; confirm the intended dose time."
    return quantity, basis + f"{tablets_per_dose} x {doses_per_day} = {quantity} for one full day. Review before saving."


# Explicit compatibility aliases for the existing misspelled dataset labels.
# These affect catalog lookup only, never the source text or image predictions.
CATALOG_ALIASES = {
    "nifedipine": "nitedipine nicardia e",
    "irbesartan": "irbesartan irovel",
    "metoprolol": "metaprolol betaloc",
    "metoprolol betaloc": "metaprolol betaloc",
}
CATALOG_STRENGTH = re.compile(r"(?<![\w./])([0-9]+(?:\.[0-9]+)?)\s*(mcg|ug|mg|g|ml|iu|%)(?![a-z])", re.I)


def name_key(value):
    value = str(value).casefold().replace("_", " ")
    value = CATALOG_STRENGTH.sub(" ", value)
    value = re.sub(r"\b(?:tabs?|tablets?|caps?|capsules?|film|coated)\b", " ", value)
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def strength_key(value):
    value = str(value).casefold().replace("µ", "u").replace("μ", "u")
    match = CATALOG_STRENGTH.fullmatch(value.strip())
    if not match:
        return ""
    from decimal import Decimal
    unit = "mcg" if match.group(2).lower() == "ug" else match.group(2).lower()
    return str(Decimal(match.group(1)).normalize()) + unit


def match_catalog(item, products):
    """Unique exact/declared-alias match; never fuzzy-pick another drug."""
    wanted = name_key(item["medicineName"])
    wanted = CATALOG_ALIASES.get(wanted, wanted)
    raw_strength = item.get("strength", "").strip()
    wanted_strength = strength_key(raw_strength)
    if raw_strength and not wanted_strength:
        return "", "unresolved", []
    candidates = []
    for pid, product in products.items():
        label = product.get("name", "")
        key = name_key(label)
        if CATALOG_ALIASES.get(key, key) != wanted:
            continue
        embedded = CATALOG_STRENGTH.findall(label.replace("_", " "))
        metadata = product.get("strength", "").strip()
        catalog_strength = strength_key(metadata)
        if not catalog_strength and len(embedded) == 1:
            catalog_strength = strength_key(" ".join(embedded[0]))
        # Never accept a conflicting/combination strength automatically.
        if metadata and len(embedded) == 1 and strength_key(" ".join(embedded[0])) != catalog_strength:
            continue
        if len(embedded) > 1 or (wanted_strength and catalog_strength != wanted_strength):
            continue
        candidates.append((str(pid), label))
    suggestions = [{"productId": pid, "name": label} for pid, label in candidates[:3]]
    if len(candidates) != 1:
        return "", "unresolved", suggestions
    return candidates[0][0], "exact-text" if wanted_strength else "unique-name-review-strength", []


def extract_prescription(text):
    check_input(text)

    key = os.environ.get("GROQ_API_KEY", "").strip()

    if not key:
        raise RuntimeError("GROQ_API_KEY is missing in the API process.")

    model = (
        os.environ.get("GROQ_MODEL", DEFAULT_MODEL).strip()
        or DEFAULT_MODEL
    )

    payload = {
        "model": model,
        "temperature": 0,
        "max_completion_tokens": 4096,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {"ocrText": text},
                    ensure_ascii=False,
                ),
            },
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "prescription_extraction",
                "strict": True,
                "schema": SCHEMA,
            },
        },
    }

    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
            "User-Agent": "MedicineProject/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            body = response.read(2_000_001)

        if len(body) > 2_000_000:
            raise ValueError("LLM response is too large.")

        result = json.loads(body)
        choice = result["choices"][0]

        if choice.get("finish_reason") != "stop":
            raise ValueError("LLM extraction was incomplete.")

        content = choice["message"].get("content")

        if not isinstance(content, str) or not content.strip():
            raise ValueError("LLM returned no extraction.")

        rows = validate_extraction(json.loads(content), text)

        if not rows:
            raise ValueError("LLM returned no medicine rows.")

        return {
            "provider": "groq",
            "model": model,
            "rows": rows,
            "reviewed": False,
            "requiresManualReview": True,
        }

    except urllib.error.HTTPError as error:
        messages = {
            401: "Groq API key is invalid.",
            403: "Groq access denied.",
            404: "Configured Groq model is unavailable.",
            429: "Groq usage limit reached.",
        }
        raise RuntimeError(
            messages.get(
                error.code,
                f"Groq request failed: HTTP {error.code}.",
            )
        ) from None

    except (urllib.error.URLError, TimeoutError):
        raise RuntimeError("Groq connection failed or timed out.") from None

    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        raise ValueError("Groq returned an invalid response.") from None


def fallback_extraction(text):
    """Preserve likely medicine lines without pretending LLM succeeded."""
    rows = []

    for line in check_input(text):
        if not (
            TABLET_PREFIX.search(line)
            or SIMPLE_MEDICINE_LINE.search(line)
        ):
            continue

        identity_text = line
        dose_text = ""

        shorthand = SHORTHAND_END.search(line)
        unclear = UNCLEAR_SHORTHAND_END.search(line)

        if shorthand:
            dose_text = shorthand.group().strip()
            identity_text = line[:shorthand.start()].strip(" -;,")
        elif unclear:
            dose_text = unclear.group("instruction")
            identity_text = line[:unclear.start()].strip(" -;,")

        if not dose_text:
            match = explicit_dose({"sourceText": line, "doseText": ""})
            if match:
                dose_text = match.group().strip()
                identity_text = line[:match.start()].strip(" -—–;,")
        parsed = build_draft(identity_text, {})["rows"]

        if len(parsed) != 1:
            continue

        warnings = [
            "Local fallback extraction: check every field "
            "against the source image."
        ]
        warnings.extend(parsed[0].get("autoCorrections", []))

        rows.append({
            "sourceText": line,
            "medicineName": parsed[0]["medicineName"],
            "strength": parsed[0]["strength"],
            "doseText": dose_text,
            "scheduleText": "",
            "durationText": "",
            "warnings": warnings,
        })

    return rows


def build_llm_draft(text, products, tray_scope="manual"):
    check_input(text)

    if tray_scope not in VALID_SCOPES:
        raise ValueError("Invalid tray scope.")

    fallback_reason = ""

    try:
        extracted = extract_prescription(text)
    except (ValueError, RuntimeError) as error:
        fallback_reason = str(error)
        logger.warning(
            "Prescription extraction using local fallback: %s",
            fallback_reason,
        )
        extracted = {
            "provider": "local-fallback",
            "model": None,
            "rows": fallback_extraction(text),
            "reviewed": False,
            "requiresManualReview": True,
        }

    if not extracted["rows"]:
        raise ValueError(
            "No medicine rows could be extracted. "
            "Check the OCR text and enter one medicine per line."
        )

    rows = []

    for item in extracted["rows"]:
        item = dict(item)
        if not item["doseText"]:
            explicit = explicit_dose(item)
            if explicit:
                item["doseText"] = explicit.group().strip()
        identity_text = normalize_space(
            item["medicineName"] + " " + item["strength"]
        )
        matched = build_draft(identity_text, products)["rows"]

        if len(matched) != 1:
            raise ValueError("Invalid extracted medicine identity.")

        catalog_row = matched[0]
        # Keep written identity fields separate from catalog metadata.
        product_id, match_type, suggestions = match_catalog(item, products)
        catalog_row.update(productId=product_id, matchType=match_type, suggestions=suggestions)
        quantity, explanation = calculate_tray_quantity(
            item,
            tray_scope,
        )

        notes = list(item["warnings"])

        if fallback_reason:
            notes.insert(
                0,
                "LLM unavailable or response rejected: "
                + fallback_reason
                + " Local parser used instead.",
            )

        # Legacy parser corrections are not applied to source identity fields
        # here, so do not display its discarded name/strength-fill messages.
        if match_type == "unique-name-review-strength":
            notes.append("A unique catalog NAME was preselected. Prescription strength was not read; confirm it against the original.")
        notes.append(explanation)

        if not item["strength"]:
            notes.append(
                "Strength was not clearly extracted. Check the source image."
            )

        if not catalog_row["productId"]:
            notes.append(
                "No unique dataset match. Check the spelling and strength "
                "or choose a suggested product."
            )

        rows.append({
            **catalog_row,
            **item,
            # Preserve source fields; a catalog match must never invent a written strength.
            "medicineName": item["medicineName"],
            "strength": item["strength"],
            "catalogStrength": products.get(product_id, {}).get("strength", ""),
            "strengthSource": "source-text" if item["strength"] else "not-read",
            "quantity": quantity,
            "quantitySource": (
                "reviewable-calculation"
                if quantity is not None
                else ""
            ),
            "quantityExplanation": explanation,
            "reviewNotes": notes,
            "requiresManualReview": True,
        })

    return {
        **extracted,
        "trayScope": tray_scope,
        "rows": rows,
        "fallbackUsed": bool(fallback_reason),
        "fallbackReason": fallback_reason,
        "reviewed": False,
        "requiresManualReview": True,
    }


if __name__ == "__main__":
    sample = (
        "Tab. ExampleMed 10 mg 1x3\n"
        "Tab. SampleMed 5 mg 2x3"
    )

    result = build_llm_draft(
        sample,
        products={},
        tray_scope="full-day",
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))