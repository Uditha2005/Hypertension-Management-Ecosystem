"""Prescription-aware medicine tray verification (FR6-FR9).

Takes the detections produced by the vision model and compares them with the
active prescription. No ML is needed here, so it can be built and tested
before the detection model is ready.
"""
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# Result statuses (FR9)
CORRECT = "Correct"
MISSING = "Missing"
EXTRA = "Extra"
POTENTIAL_SWAP = "Potential Swap"
MANUAL = "Manual Verification Required"

# Tune these using validation results
MIN_CONFIDENCE = 0.60   # below this, a detection is too uncertain (FR8)
MIN_MARGIN = 0.15       # top-1 minus top-2 confidence; smaller = ambiguous


@dataclass
class Detection:
    """One pill found in the tray image."""
    label: str                      # most likely medicine class
    confidence: float               # confidence of that class (0-1)
    second_label: Optional[str] = None
    second_confidence: float = 0.0  # confidence of the runner-up class

    def is_uncertain(self) -> bool:
        if self.confidence < MIN_CONFIDENCE:
            return True
        return (self.confidence - self.second_confidence) < MIN_MARGIN


@dataclass
class VerificationResult:
    status: str
    missing: Dict[str, int] = field(default_factory=dict)
    extra: Dict[str, int] = field(default_factory=dict)
    swaps: List[Tuple[str, str]] = field(default_factory=list)  # (prescribed, found)
    uncertain: List[Detection] = field(default_factory=list)


def verify_tray(detections: List[Detection],
                prescription: Dict[str, int]) -> VerificationResult:
    """Compare detected pills with the prescription {medicine: quantity}."""
    uncertain = [d for d in detections if d.is_uncertain()]
    confident = [d for d in detections if not d.is_uncertain()]

    found = Counter(d.label.lower() for d in confident)
    expected = Counter({k.lower(): v for k, v in prescription.items()})

    missing = {m: n for m, n in (expected - found).items()}
    extra = {m: n for m, n in (found - expected).items()}

    # A missing medicine plus an extra one is a potential swap
    swaps: List[Tuple[str, str]] = []
    miss_left, extra_left = dict(missing), dict(extra)
    for m in list(miss_left):
        for e in list(extra_left):
            while miss_left.get(m, 0) > 0 and extra_left.get(e, 0) > 0:
                swaps.append((m, e))
                miss_left[m] -= 1
                extra_left[e] -= 1
    missing = {m: n for m, n in miss_left.items() if n > 0}
    extra = {e: n for e, n in extra_left.items() if n > 0}

    # Overall status: uncertainty first, then discrepancies
    if uncertain:
        status = MANUAL
    elif swaps:
        status = POTENTIAL_SWAP
    elif missing:
        status = MISSING
    elif extra:
        status = EXTRA
    else:
        status = CORRECT

    return VerificationResult(status, missing, extra, swaps, uncertain)


if __name__ == "__main__":
    rx = {"amlodipine": 1, "losartan": 1}
    tray = [Detection("amlodipine", 0.95, "atenolol", 0.02),
            Detection("losartan", 0.90, "enalapril", 0.05)]
    print(verify_tray(tray, rx))