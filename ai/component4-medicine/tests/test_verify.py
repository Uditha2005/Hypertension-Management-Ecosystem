import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from verify import (Detection, verify_tray, CORRECT, MISSING, EXTRA,
                    POTENTIAL_SWAP, MANUAL)

RX = {"amlodipine": 1, "losartan": 1}


def d(label, conf=0.95):
    return Detection(label, conf, None, 0.02)


def test_correct():
    assert verify_tray([d("amlodipine"), d("losartan")], RX).status == CORRECT


def test_missing():
    r = verify_tray([d("amlodipine")], RX)
    assert r.status == MISSING and r.missing == {"losartan": 1}


def test_extra():
    r = verify_tray([d("amlodipine"), d("losartan"), d("atenolol")], RX)
    assert r.status == EXTRA and r.extra == {"atenolol": 1}


def test_extra_quantity():
    r = verify_tray([d("amlodipine"), d("amlodipine"), d("losartan")], RX)
    assert r.status == EXTRA and r.extra == {"amlodipine": 1}


def test_swap():
    r = verify_tray([d("amlodipine"), d("atenolol")], RX)
    assert r.status == POTENTIAL_SWAP and r.swaps == [("losartan", "atenolol")]


def test_low_confidence_needs_manual():
    r = verify_tray([d("amlodipine"), Detection("losartan", 0.40, "enalapril", 0.30)], RX)
    assert r.status == MANUAL


def test_ambiguous_similar_pills_need_manual():
    # high-ish confidence but runner-up is very close
    r = verify_tray([d("amlodipine"), Detection("losartan", 0.70, "enalapril", 0.65)], RX)
    assert r.status == MANUAL


def test_empty_tray():
    assert verify_tray([], RX).status == MISSING