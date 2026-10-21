"""Build editable prescription drafts with flagged, conservative auto-correction.

Automatic corrections (always recorded in reviewNotes/autoCorrections):
- OCR letter/digit confusion directly before a unit (e.g. 'so mg' -> '50 mg')
- Close drug-name spelling matched to ONE unambiguous catalog drug
- Decimal-point slip (25 mg vs 2.5 mg) only when the catalog has exactly
  one variant with the same digits
Ambiguous cases are never selected; they remain suggestions.
"""

import re
import unicodedata
from difflib import SequenceMatcher


PREFIX = re.compile(
    r"^\s*"
    r"(?:(?:[-–—•]|\d+[.)])\s*)?"
    r"(?:tab(?:let)?s?|t[adq]b|cap(?:sule)?s?|"
    r"syr(?:up)?|inj(?:ection)?|[TPD])"
    r"(?:\s*[.:\-–—]\s*|\s+)",
    re.I,
)

BULLET = re.compile(r"^\s*(?:[-–—•]|\d+[.)])\s*")

STRENGTH = re.compile(
    r"(?<![\w./])"
    r"\d+(?:\.\d+)?\s*"
    r"(?:mcg|ug|mg|g|ml|iu|%)"
    r"(?!\w)",
    re.I,
)

# Standalone token made only of digit-like letters, directly before a unit.
CONFUSED_STRENGTH = re.compile(
    r"(?<![\w./])([0-9OoSsIl|]{1,4})(\s*)(mcg|ug|mg|g|ml|iu)(?!\w)",
    re.I,
)
CONFUSION_MAP = {
    "O": "0", "o": "0", "S": "5", "s": "5",
    "I": "1", "l": "1", "|": "1",
}

TRAY_QUANTITY = re.compile(
    r"\b(?:"
    r"tray\s+(?:qty|quantity)\s*[:=]\s*(\d+)"
    r"|"
    r"(\d+)\s+(?:tablets?|pills?|capsules?)"
    r"\s+for\s+(?:this\s+)?tray"
    r")\b",
    re.I,
)

SCHEDULE = re.compile(
    r"(?:\s*[-–—,;]\s*|\s+)"
    r"(?:od|qd|bd|bid|tds|tid|qid|stat|prn)"
    r"\.?\s*$",
    re.I,
)

DOSE_INSTRUCTION = re.compile(
    r"\s*[-–—;,]\s*"
    r"(?:\d+(?:\.\d+)?|[Il])\s*"
    r"(?:tabs?|tablets?|caps?|capsules?|puffs?|drops?|ml)"
    r"\b.*$",
    re.I,
)

FORMS = re.compile(
    r"\b(?:film|coated|tablets?|tabs?|capsules?|caps?)\b",
    re.I,
)

COMPLEX = re.compile(
    r"\d\s*[/+]\s*\d"
    r"|"
    r"(?:mg|mcg|ug|g|iu)\s*/",
    re.I,
)

NAME_MATCH_MIN = 0.80      # minimum spelling similarity for auto-match
NAME_MATCH_MARGIN = 0.06   # best drug must beat any other drug by this much
SUGGESTION_MIN = 0.65


def clean(text):
    value = unicodedata.normalize("NFKC", str(text or ""))
    value = value.replace("μ", "u").replace("µ", "u")
    return re.sub(r"\s+", " ", value).strip()


def identity(text):
    value = FORMS.sub(" ", clean(text).casefold())
    return re.sub(r"[^a-z0-9%]", "", value)


def strength_key(text):
    value = re.sub(r"\s+", "", clean(text).casefold())
    return value.replace("ug", "mcg")


def digit_key(text):
    """Digits without decimal point, plus unit: '2.5mg' and '25mg' match."""
    parts = re.fullmatch(
        r"(\d+(?:\.\d+)?)([a-z%]+)",
        strength_key(text),
    )

    if not parts:
        return None

    number, unit = parts.groups()
    return number.replace(".", "").lstrip("0"), unit


def strength_value(match):
    value = re.sub(r"\s+", "", match.group()).lower()

    parts = re.fullmatch(
        r"(\d+(?:\.\d+)?)(mcg|ug|mg|g|ml|iu|%)",
        value,
    )

    number, unit = parts.groups()

    if unit == "ug":
        unit = "mcg"

    return f"{number} {unit}"


def repair_strength_token(body):
    """Fix letter/digit confusion before a unit, e.g. 'so mg' -> '50 mg'."""
    fixes = []

    def replace(match):
        token = match.group(1)

        if token.isdigit():
            return match.group()

        fixed = "".join(CONFUSION_MAP.get(c, c) for c in token)

        if not fixed.isdigit() or fixed.startswith("0"):
            return match.group()

        fixes.append(
            f"OCR strength '{token} {match.group(3)}' read as "
            f"'{fixed} {match.group(3)}'. Verify against the image."
        )
        return f"{fixed} {match.group(3)}"

    return CONFUSED_STRENGTH.sub(replace, body), fixes


def extract_name_strength(text):
    body = clean(text)
    matches = list(STRENGTH.finditer(body))

    if len(matches) == 1 and not COMPLEX.search(body):
        match = matches[0]

        name = clean(
            body[:match.start() ] + " " + body[match.end():]
        ).strip(" -,:;")

        if name:
            return name, strength_value(match)

    return body, ""


def product_fields(product):
    label = clean(product.get("name", ""))

    name, embedded_strength = extract_name_strength(label)
    metadata_strength = clean(product.get("strength", ""))

    if metadata_strength:
        match = STRENGTH.fullmatch(metadata_strength)

        if not match:
            return name, "", False

        metadata_strength = strength_value(match)

    if (
        embedded_strength
        and metadata_strength
        and strength_key(embedded_strength)
        != strength_key(metadata_strength)
    ):
        return name, "", False

    if (
        COMPLEX.search(label)
        or len(list(STRENGTH.finditer(label))) > 1
    ):
        return name, "", False

    return name, embedded_strength or metadata_strength, True


def pick_product(name, strength, catalog):
    """Return (entry, match_type, note) or (None, '', '').

    entry = (product_id, label, product_name, product_strength, valid)
    """
    usable = [e for e in catalog if e[4] and e[3]]
    wanted = identity(name)

    # 1. Exact name + strength.
    exact = [
        e for e in usable
        if strength
        and identity(e[2]) == wanted
        and strength_key(e[3]) == strength_key(strength)
    ]

    if len(exact) == 1:
        return exact[0], "exact-text", ""

    if exact or len(wanted) < 4:
        return None, "", ""

    # 2. Unambiguous fuzzy drug name.
    scored = [
        (SequenceMatcher(None, wanted, identity(e[2])).ratio(), e)
        for e in usable
    ]

    if not scored:
        return None, "", ""

    best_score, best_entry = max(scored, key=lambda item: item[0])

    if best_score < NAME_MATCH_MIN:
        return None, "", ""

    best_identity = identity(best_entry[2])
    group = [e for score, e in scored if identity(e[2]) == best_identity]

    other_scores = [
        score for score, e in scored
        if identity(e[2]) != best_identity
    ]

    if other_scores and best_score - max(other_scores) < NAME_MATCH_MARGIN:
        return None, "", ""

    spelled = (
        "" if wanted == best_identity
        else f"Drug name '{name}' auto-matched to '{best_entry[2]}'. "
    )

    if strength:
        same = [
            e for e in group
            if strength_key(e[3]) == strength_key(strength)
        ]

        if len(same) == 1:
            return same[0], "auto-name", spelled + "Verify against the image."

        if not same:
            wanted_digits = digit_key(strength)
            slips = [
                e for e in group
                if wanted_digits and digit_key(e[3]) == wanted_digits
            ]

            if len(slips) == 1:
                return slips[0], "auto-strength-corrected", (
                    spelled
                    + f"Strength '{strength}' is not in the dataset for "
                    f"this drug; corrected to '{slips[0][3]}' (decimal "
                    "point). VERIFY the strength on the image."
                )

        return None, "", ""

    if len(group) == 1:
        return group[0], "auto-name", (
            spelled
            + f"Strength was unclear; set to '{group[0][3]}' (only "
            "dataset variant). Verify against the image."
        )

    return None, "", ""


def build_draft(text, products):
    if not isinstance(text, str) or len(text) > 12000:
        raise ValueError(
            "Prescription draft text must be at most 12,000 characters."
        )

    lines = [line.strip() for line in text.splitlines() if line.strip()]

    if len(lines) > 50:
        raise ValueError("Use at most 50 medicine rows.")

    catalog = []

    for product_id, product in products.items():
        if not isinstance(product, dict) or not product.get("name"):
            continue

        name, strength, valid = product_fields(product)
        catalog.append(
            (str(product_id), str(product["name"]), name, strength, valid)
        )

    rows = []

    for line in lines:
        body = BULLET.sub("", clean(line), count=1)
        body = PREFIX.sub("", body, count=1).strip()

        quantities = list(TRAY_QUANTITY.finditer(body))
        quantity = None

        if len(quantities) == 1:
            candidate = int(quantities[0].group(1) or quantities[0].group(2))

            if 1 <= candidate <= 100:
                quantity = candidate

        body = TRAY_QUANTITY.sub(" ", body).strip(" -,:;")
        body = DOSE_INSTRUCTION.sub("", body).strip(" -,:;")
        body = SCHEDULE.sub("", body).strip(" -,:;")

        body, corrections = repair_strength_token(body)
        name, strength = extract_name_strength(body)
        name = name or line

        entry, match_type, match_note = pick_product(name, strength, catalog)
        product_id = entry[0] if entry else ""

        if entry and match_type != "exact-text":
            name, strength = entry[2], entry[3]
            corrections.append(match_note)

        suggestions = []

        if not product_id:
            scored = []
            wanted = identity(name)

            for pid, label, pname, pstrength, valid in catalog:
                if not valid:
                    continue

                if (
                    strength and pstrength
                    and strength_key(strength) != strength_key(pstrength)
                    and digit_key(strength) != digit_key(pstrength)
                ):
                    continue

                score = SequenceMatcher(
                    None, wanted, identity(pname)
                ).ratio()

                if score >= SUGGESTION_MIN:
                    scored.append((score, pid, label))

            suggestions = [
                {"productId": pid, "name": label}
                for _, pid, label in sorted(scored, reverse=True)[:3]
            ]

        review_notes = list(corrections)

        if not strength:
            review_notes.append(
                "Strength unclear or compound; review the original."
            )

        if not product_id:
            review_notes.append(
                "No unique dataset match. Check the spelling and strength "
                "or choose a suggested product."
            )

        rows.append(
            {
                "sourceText": line,
                "medicineName": name,
                "strength": strength,
                "quantity": quantity,
                "productId": product_id,
                "matchType": match_type if product_id else "unresolved",
                "suggestions": suggestions,
                "autoCorrections": corrections,
                "reviewNotes": review_notes,
                "requiresManualReview": True,
            }
        )

    return {
        "rows": rows,
        "reviewed": False,
        "requiresManualReview": True,
    }