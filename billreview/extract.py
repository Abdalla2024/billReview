"""Turn scanned paper bills into line records the rules can review.

Every extracted value is cross-checked against the form itself (line charges must add
up to box 28) and the reference files (claim, tax ID, NPI, diagnosis code). The result
is written to paper-extraction.csv with page and row so a reviewer can compare each
value with the page image; a corrected copy of that file can be fed back in with
--paper-extraction instead of re-reading the scans.
"""
import csv
from decimal import Decimal
from pathlib import Path

import cv2

FIELDS = ["line_id", "bill_id", "page", "row", "received_date", "claim_number", "claimant_name",
          "claimant_dob", "billing_tin", "rendering_npi", "date_of_service", "procedure_code", "modifier",
          "units", "billed_charge", "diagnosis_code", "form_total_charge", "ocr_checks", "ocr_raw", "page_box"]


def extract(pdf_path, ref, electronic, evidence_dir):
    from . import ocr  # imported here so a reviewed extraction CSV can be used without OCR installed

    evidence_dir = Path(evidence_dir)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for page_no, f, lines, raw, img in ocr.read_pdf(pdf_path):
        small = cv2.resize(img, (img.shape[1] // 2, img.shape[0] // 2), interpolation=cv2.INTER_AREA)
        cv2.imwrite(str(evidence_dir / f"page-{page_no:02d}.png"), small)
        page_checks = []
        for key in ("bill_id", "received_date", "claim_number", "claimant_dob", "billing_tin", "diagnosis_code",
                    "total_charge"):
            if not f.get(key):
                page_checks.append(f"could not read {key}")
        for ln in lines:
            p = ln["parsed"] or {}
            row = {
                "line_id": f"{f['bill_id']}-{ln['row']:02d}" if f["bill_id"] else f"PAGE{page_no:02d}-{ln['row']:02d}",
                "bill_id": f["bill_id"], "page": page_no, "row": ln["row"],
                "received_date": f["received_date"], "claim_number": f["claim_number"],
                "claimant_name": f["claimant_name"], "claimant_dob": f["claimant_dob"],
                "billing_tin": f["billing_tin"], "rendering_npi": p.get("rendering_npi", ""),
                "date_of_service": p.get("date_of_service", ""), "procedure_code": p.get("procedure_code", ""),
                "modifier": p.get("modifier", ""), "units": p.get("units", ""),
                "billed_charge": p.get("billed_charge", ""), "diagnosis_code": f["diagnosis_code"],
                "form_total_charge": f["total_charge"],
                "ocr_checks": list(page_checks) + ([] if ln["parsed"] else ["could not read service line"]),
                "ocr_raw": ln["raw"],
                "box": [v // 2 for v in ln["crop_box"]],
            }
            rows.append(row)
    validate(rows, ref, electronic)
    return rows


def validate(rows, ref, electronic):
    """Cross-check extracted values; adds problems to each row's ocr_checks."""
    dx_seen = {l["diagnosis_code"] for l in electronic}
    electronic_ids = {l["line_id"] for l in electronic}
    by_bill = {}
    for r in rows:
        by_bill.setdefault((r["page"], r["bill_id"]), []).append(r)
    for (page, bill), group in by_bill.items():
        try:
            total = sum(Decimal(r["billed_charge"]) for r in group)
            if group[0]["form_total_charge"] and total != Decimal(group[0]["form_total_charge"]):
                for r in group:
                    r["ocr_checks"].append(f"line charges add to {total}, form box 28 says "
                                           f"{group[0]['form_total_charge']}")
        except Exception:
            pass
        rownums = sorted(r["row"] for r in group)
        if rownums != list(range(1, len(rownums) + 1)):
            for r in group:
                r["ocr_checks"].append(f"service rows read: {rownums} (gap: a row may have been missed)")
    for r in rows:
        checks = r["ocr_checks"] if isinstance(r["ocr_checks"], list) else []
        if r["claim_number"] and r["claim_number"] not in ref.claims:
            checks.append(f"claim {r['claim_number']} not in claims.csv")
        if r["billing_tin"] and r["billing_tin"] not in ref.provider_by_tin:
            checks.append(f"tax ID {r['billing_tin']} not in providers.csv")
        if r["rendering_npi"] and ref.tin_by_npi.get(r["rendering_npi"]) != r["billing_tin"]:
            checks.append(f"NPI {r['rendering_npi']} is not listed under tax ID {r['billing_tin']} in providers.csv")
        if r["diagnosis_code"] and r["diagnosis_code"] not in dx_seen:
            checks.append(f"diagnosis {r['diagnosis_code']} does not appear in bills.csv (body part unknown)")
        if (r["procedure_code"], r["modifier"]) not in ref.fees and r["procedure_code"]:
            checks.append(f"{r['procedure_code']} {r['modifier']} not in fee schedule".replace("  ", " "))
        if r["line_id"] in electronic_ids:
            checks.append("line_id also appears in bills.csv")
        r["ocr_checks"] = checks


def write_extraction(rows, path):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({**r, "ocr_checks": "; ".join(r["ocr_checks"]) or "ok",
                        "page_box": " ".join(map(str, r["box"])) if r.get("box") else ""})


def read_extraction(path, ref, electronic):
    """Load a (possibly hand-corrected) paper-extraction.csv instead of re-reading the scans."""
    with open(path, newline="") as f:
        rows = [dict(r) for r in csv.DictReader(f)]
    for r in rows:
        r["page"], r["row"] = int(r["page"]), int(r["row"])
        r["ocr_checks"] = []
        r["box"] = [int(v) for v in r.get("page_box", "").split()] or None
    validate(rows, ref, electronic)
    return rows


def to_bill_lines(rows, ref, electronic):
    """Shape extracted rows like bills.csv lines (body part from bills.csv by diagnosis code)."""
    body_by_dx = {}
    for l in electronic:
        body_by_dx.setdefault(l["diagnosis_code"], (l["body_part"], l["line_id"]))
    lines = []
    for r in rows:
        bp, bp_src = body_by_dx.get(r["diagnosis_code"], ("", ""))
        prov = ref.provider_by_tin.get(r["billing_tin"], {})
        lines.append({
            **{k: r[k] for k in FIELDS if k in r},
            "page": r["page"], "row": r["row"], "box": r.get("box"),
            "source": "paper",
            "source_ref": f"paper-bills.pdf page {r['page']} (bill {r['bill_id']} line {r['row']:02d})",
            "billing_provider": prov.get("billing_provider", ""),
            "form_type": "CMS-1500 (paper)",
            "body_part": bp,
            "body_part_ev": f" (from bills.csv {bp_src} with the same dx)" if bp_src else "",
        })
    return lines
