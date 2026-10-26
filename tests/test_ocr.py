"""Re-read the practice scans and compare with values checked by eye against each page image
(tests/fixtures/paper-2026-09-verified.csv). Slow (~1 minute): needs Tesseract installed."""
import csv
import shutil
from pathlib import Path

import pytest

from billreview import data, extract

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "paper-2026-09-verified.csv"


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="tesseract not installed")
def test_ocr_matches_hand_verified_values(tmp_path):
    ref = data.Reference(ROOT / "data" / "reference")
    electronic = data.load_electronic(ROOT / "data" / "2026-09")
    rows = extract.extract(ROOT / "data" / "2026-09" / "paper-bills.pdf", ref, electronic, tmp_path)
    with open(FIXTURE, newline="") as f:
        expected = list(csv.DictReader(f))
    assert len(rows) == len(expected) == 25
    for got, want in zip(rows, expected):
        for k, v in want.items():
            assert str(got[k]) == v, (want["line_id"], k, got[k], v)
        assert got["ocr_checks"] == [], (got["line_id"], got["ocr_checks"])
