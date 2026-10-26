"""Load one month of bill lines and the reference files."""
import csv
from pathlib import Path


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


class Reference:
    def __init__(self, ref_dir):
        ref_dir = Path(ref_dir)
        self.claims = {r["claim_number"]: r for r in read_csv(ref_dir / "claims.csv")}
        self.fees = {(r["procedure_code"], r["modifier"]): r for r in read_csv(ref_dir / "fee-schedule.csv")}
        self.providers = read_csv(ref_dir / "providers.csv")
        self.authorizations = read_csv(ref_dir / "authorizations.csv")
        self.rentals = read_csv(ref_dir / "rental-history.csv")
        self.provider_by_tin = {}
        for p in self.providers:
            self.provider_by_tin.setdefault(p["billing_tin"], p)
        self.tin_by_npi = {p["rendering_npi"]: p["billing_tin"] for p in self.providers}


def find_month_dir(data_dir, month=None):
    """The month folder is the one that holds bills.csv (e.g. data/2026-09)."""
    data_dir = Path(data_dir)
    if month:
        return data_dir / month
    months = sorted(p.parent for p in data_dir.glob("*/bills.csv"))
    if len(months) != 1:
        raise SystemExit(f"expected one month folder with bills.csv under {data_dir}, found {months}; pass --month")
    return months[0]


def load_electronic(month_dir):
    lines = []
    for r in read_csv(Path(month_dir) / "bills.csv"):
        r = dict(r)
        r["source"] = "electronic"
        r["source_ref"] = f"bills.csv line_id {r['line_id']}"
        lines.append(r)
    return lines


def load_notes(month_dir):
    return read_csv(Path(month_dir) / "treatment-notes.csv")
