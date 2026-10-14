"""Build reviewable fields from OCR text without inferring treatment doses."""
import re
from difflib import SequenceMatcher

PREFIX = re.compile(
    r"^\s*(?:[-–—•]\s*)?(?:tab(?:let)?s?|t[adq]b|cap(?:sule)?s?|"
    r"syr(?:up)?|inj(?:ection)?|in(?=\s*[-:])|[TPD])"
    r"(?:\s*[.:\-–—]\s*|\s+)", re.I
)
STRENGTH = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*(mcg|µg|mg|g|ml|iu|%)(?!\w)", re.I)
# Auto-fill quantity only when the text explicitly identifies THIS tray.
TRAY_QUANTITY = re.compile(r"\b(?:tray\s+(?:qty|quantity)\s*[:=]\s*(\d+)|"
                           r"(\d+)\s+(?:tablets?|pills?|capsules?)\s+for\s+(?:this\s+)?tray)\b", re.I)
SCHEDULE = re.compile(r"(?:\s*[-–—,;]\s*|\s+)(?:od|qd|bd|bid|tds|tid|qid|stat|prn)\s*$", re.I)
# Remove a clearly separated dose instruction from the NAME only. Preserve
# the original in sourceText; never convert it into a tray quantity.
DOSE_INSTRUCTION = re.compile(
    r"\s*[-–—;,]\s*(?:\d+(?:\.\d+)?|[Il])\s*"
    r"(?:tabs?|tablets?|caps?|capsules?|puffs?|drops?|ml)\b.*$", re.I
)
FORMS = re.compile(r"\b(?:film|coated|tablets?|tabs?|capsules?|caps?)\b", re.I)


def identity(text):
    return re.sub(r"[^a-z0-9µ%]", "", FORMS.sub(" ", text.casefold()))


def strength_key(text):
    return re.sub(r"\s+", "", text.casefold()).replace("µg", "mcg")


def build_draft(text, products):
    if not isinstance(text, str) or len(text) > 12000:
        raise ValueError("Prescription draft text must be at most 12,000 characters.")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) > 50:
        raise ValueError("Use at most 50 medicine rows.")
    rows = []
    for line in lines:
        body = PREFIX.sub("", line, count=1).strip()
        quantity_match = TRAY_QUANTITY.search(body)
        quantity = None
        if quantity_match:
            candidate = int(quantity_match.group(1) or quantity_match.group(2))
            if 1 <= candidate <= 100:
                quantity = candidate
            body = TRAY_QUANTITY.sub("", body).strip(" -,:;")
        body = DOSE_INSTRUCTION.sub("", body).strip(" -,:;")
        body = SCHEDULE.sub("", body).strip(" -,:;")
        strengths = list(STRENGTH.finditer(body))
        # Multiple strengths can describe combination products. Keep them for review.
        strength = ""
        name = body
        if len(strengths) == 1:
            match = strengths[0]
            strength = match.group(1) + " " + match.group(2).lower()
            name = (body[:match.start()] + body[match.end():]).strip(" -,:;")
        if not name:
            name = body or line
        query_key = identity(name + " " + strength)
        exact = [pid for pid, product in products.items()
                 if identity(product["name"] + " " + product.get("strength", "")) == query_key]
        product_id = exact[0] if len(exact) == 1 else ""
        suggestions = []
        if not product_id:
            scored = []
            for pid, product in products.items():
                product_text = product["name"] + " " + product.get("strength", "")
                product_strengths = STRENGTH.findall(product_text)
                if strength and product_strengths and strength_key(strength) not in {
                    strength_key(number + unit) for number, unit in product_strengths
                }:
                    continue
                product_name = STRENGTH.sub("", product_text)
                score = SequenceMatcher(None, identity(name), identity(product_name)).ratio()
                if score >= 0.65:
                    scored.append((score, pid, product["name"]))
            suggestions = [{"productId": pid, "name": name}
                           for _, pid, name in sorted(scored, reverse=True)[:3]]
        review_notes = []
        if not strength:
            review_notes.append("Strength not clearly extracted; check the original.")
        if quantity is None:
            review_notes.append("Enter pills for this tray; schedule/supply totals were not used.")
        if not product_id:
            review_notes.append("Exact trained product needs review or is unsupported.")
        rows.append({
            "sourceText": line,
            "medicineName": name,
            "strength": strength,
            "quantity": quantity,
            "productId": product_id,
            "matchType": "exact-text" if product_id else "unresolved",
            "suggestions": suggestions,
            "reviewNotes": review_notes,
            "requiresManualReview": True,
        })
    return {"rows": rows, "reviewed": False, "requiresManualReview": True}
