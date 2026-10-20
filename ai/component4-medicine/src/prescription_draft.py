"""Build editable prescription drafts without inferring treatment doses."""

import re
import unicodedata
from difflib import SequenceMatcher


# Remove an explicit prescription prefix.
PREFIX = re.compile(
    r"^\s*"
    r"(?:(?:[-–—•]|\d+[.)])\s*)?"
    r"(?:tab(?:let)?s?|t[adq]b|cap(?:sule)?s?|"
    r"syr(?:up)?|inj(?:ection)?|[TPD])"
    r"(?:\s*[.:\-–—]\s*|\s+)",
    re.I,
)

BULLET = re.compile(
    r"^\s*(?:[-–—•]|\d+[.)])\s*"
)

# Only numbers with explicit units qualify as strengths.
STRENGTH = re.compile(
    r"(?<![\w./])"
    r"\d+(?:\.\d+)?\s*"
    r"(?:mcg|ug|mg|g|ml|iu|%)"
    r"(?!\w)",
    re.I,
)

# Quantity must explicitly refer to this tray.
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

# Remove clearly separated instructions from the name only.
# Never convert these instructions into a tray quantity.
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

# Do not partially extract combination strengths or concentrations.
COMPLEX = re.compile(
    r"\d\s*[/+]\s*\d"
    r"|"
    r"(?:mg|mcg|ug|g|iu)\s*/",
    re.I,
)


def clean(text):
    """Normalize whitespace and microgram symbols, not drug spelling."""
    value = unicodedata.normalize(
        "NFKC",
        str(text or ""),
    )

    value = value.replace("μ", "u").replace("µ", "u")

    return re.sub(r"\s+", " ", value).strip()


def identity(text):
    """Create a comparison key while retaining release/brand qualifiers."""
    value = FORMS.sub(
        " ",
        clean(text).casefold(),
    )

    return re.sub(r"[^a-z0-9%]", "", value)


def strength_key(text):
    value = re.sub(
        r"\s+",
        "",
        clean(text).casefold(),
    )

    return value.replace("ug", "mcg")


def strength_value(match):
    """Format an explicitly matched strength."""
    value = re.sub(
        r"\s+",
        "",
        match.group(),
    ).lower()

    parts = re.fullmatch(
        r"(\d+(?:\.\d+)?)(mcg|ug|mg|g|ml|iu|%)",
        value,
    )

    number, unit = parts.groups()

    if unit == "ug":
        unit = "mcg"

    return f"{number} {unit}"


def extract_name_strength(text):
    """Extract one clear strength; preserve ambiguous text for review."""
    body = clean(text)
    matches = list(STRENGTH.finditer(body))

    if len(matches) == 1 and not COMPLEX.search(body):
        match = matches[0]

        name = clean(
            body[:match.start()]
            + " "
            + body[match.end():]
        ).strip(" -,:;")

        if name:
            return name, strength_value(match)

    return body, ""


def product_fields(product):
    """Avoid counting a strength twice when it is also in the name."""
    label = clean(product.get("name", ""))

    name, embedded_strength = extract_name_strength(label)
    metadata_strength = clean(product.get("strength", ""))

    if metadata_strength:
        match = STRENGTH.fullmatch(metadata_strength)

        if not match:
            return name, "", False

        metadata_strength = strength_value(match)

    # Conflicting catalog values must not produce an automatic match.
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

    return (
        name,
        embedded_strength or metadata_strength,
        True,
    )


def build_draft(text, products):
    if not isinstance(text, str) or len(text) > 12000:
        raise ValueError(
            "Prescription draft text must be at most 12,000 characters."
        )

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    if len(lines) > 50:
        raise ValueError("Use at most 50 medicine rows.")

    catalog = []

    for product_id, product in products.items():
        if not isinstance(product, dict) or not product.get("name"):
            continue

        name, strength, valid = product_fields(product)

        catalog.append(
            (
                str(product_id),
                str(product["name"]),
                name,
                strength,
                valid,
            )
        )

    rows = []

    for line in lines:
        body = BULLET.sub(
            "",
            clean(line),
            count=1,
        )

        body = PREFIX.sub(
            "",
            body,
            count=1,
        ).strip()

        # Multiple quantity statements remain unresolved.
        quantities = list(TRAY_QUANTITY.finditer(body))
        quantity = None

        if len(quantities) == 1:
            candidate = int(
                quantities[0].group(1)
                or quantities[0].group(2)
            )

            if 1 <= candidate <= 100:
                quantity = candidate

        body = TRAY_QUANTITY.sub(
            " ",
            body,
        ).strip(" -,:;")

        body = DOSE_INSTRUCTION.sub(
            "",
            body,
        ).strip(" -,:;")

        body = SCHEDULE.sub(
            "",
            body,
        ).strip(" -,:;")

        name, strength = extract_name_strength(body)
        name = name or line

        exact_matches = []
        scored_suggestions = []

        for (
            product_id,
            product_label,
            product_name,
            product_strength,
            valid,
        ) in catalog:
            if not valid:
                continue

            # Do not suggest a known different strength.
            if (
                strength
                and product_strength
                and strength_key(strength)
                != strength_key(product_strength)
            ):
                continue

            same_name = (
                identity(name)
                == identity(product_name)
            )

            same_strength = bool(
                strength
                and product_strength
                and strength_key(strength)
                == strength_key(product_strength)
            )

            if same_name and same_strength:
                exact_matches.append(product_id)

            score = SequenceMatcher(
                None,
                identity(name),
                identity(product_name),
            ).ratio()

            if score >= 0.65:
                scored_suggestions.append(
                    (
                        score,
                        product_id,
                        product_label,
                    )
                )

        # Only a unique name + strength match is preselected.
        # Similar spelling is a suggestion, never an automatic selection.
        product_id = (
            exact_matches[0]
            if len(exact_matches) == 1
            else ""
        )

        suggestions = []

        if not product_id:
            suggestions = [
                {
                    "productId": candidate_id,
                    "name": candidate_label,
                }
                for _, candidate_id, candidate_label
                in sorted(
                    scored_suggestions,
                    reverse=True,
                )[:3]
            ]

        review_notes = []

        if not strength:
            review_notes.append(
                "Strength unclear or compound; review the original. "
                "No strength was guessed."
            )

        if quantity is None:
            review_notes.append(
                "Enter pills for this tray; schedules and supply "
                "totals were not converted."
            )

        if not product_id:
            review_notes.append(
                "Exact product not uniquely matched. "
                "Review suggestions or leave unsupported."
            )

        rows.append(
            {
                "sourceText": line,
                "medicineName": name,
                "strength": strength,
                "quantity": quantity,
                "productId": product_id,
                "matchType": (
                    "exact-text"
                    if product_id
                    else "unresolved"
                ),
                "suggestions": suggestions,
                "reviewNotes": review_notes,
                "requiresManualReview": True,
            }
        )

    return {
        "rows": rows,
        "reviewed": False,
        "requiresManualReview": True,
    }