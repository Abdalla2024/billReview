"""Review one month of bills: python -m billreview --data data [--month 2026-09] [--out out/2026-09]"""
import argparse
import json
from pathlib import Path

from . import data, extract, report
from .verify import verify
from .rules import Review, fmt

INTERNAL = {"source", "source_ref", "box", "body_part_ev", "ocr_raw", "ocr_checks"}
REQUIRED = ["claim_number", "claimant_dob", "billing_tin", "rendering_npi", "date_of_service", "procedure_code",
            "units", "billed_charge", "received_date"]


def run(data_dir, month=None, out_dir=None, paper_extraction=None):
    month_dir = data.find_month_dir(data_dir, month)
    month = month_dir.name
    out_dir = Path(out_dir or Path("out") / month)
    out_dir.mkdir(parents=True, exist_ok=True)
    ref = data.Reference(Path(data_dir) / "reference")
    electronic = data.load_electronic(month_dir)
    notes = data.load_notes(month_dir)

    pdf = month_dir / "paper-bills.pdf"
    if paper_extraction:
        rows = extract.read_extraction(paper_extraction, ref, electronic)
        pages = len({r["page"] for r in rows})
    elif pdf.exists():
        rows = extract.extract(pdf, ref, electronic, out_dir / "evidence")
        pages = len(list((out_dir / "evidence").glob("page-*.png")))
    else:
        rows, pages = [], 0
    extract.write_extraction(rows, out_dir / "paper-extraction.csv")
    paper = extract.to_bill_lines(rows, ref, electronic)

    # a line missing a field the rules need cannot be reviewed; it is reported, never guessed
    reviewable, unreadable = [], []
    for l in electronic + paper:
        missing = [k for k in REQUIRED if not str(l.get(k, "")).strip()]
        (unreadable if missing else reviewable).append((l, missing))
    review = Review([l for l, _ in reviewable], notes, ref)
    verdicts = review.run()
    for l, missing in unreadable:
        review.question([l["line_id"]], f"Could not read {', '.join(missing)} from {l['source_ref']}; the line "
                        "was not reviewed. Read the scan, correct paper-extraction.csv and re-run with "
                        "--paper-extraction.")
        verdicts.append({"line": l, "flagged": False, "calc": None, "status": "not reviewed (unreadable)"})

    accounting = {"electronic": len(electronic), "paper": len(paper), "pages": pages,
                  "total": len(electronic) + len(paper), "unreadable": len(unreadable)}
    assert len(verdicts) == accounting["total"]
    report.write_flagged(verdicts, out_dir / "flagged-lines.csv")
    report.write_all_lines(verdicts, out_dir / "all-lines.csv")
    _, problems = verify(out_dir, data_dir, month_dir)
    accounting["evidence_problems"] = problems
    total = report.write_summary(verdicts, review.questions, rows, accounting, out_dir / "review-summary.md", month)
    write_review_data(verdicts, review.questions, rows, accounting, out_dir, month, total)
    return verdicts, review.questions, accounting, total, out_dir


def write_review_data(verdicts, questions, rows, accounting, out_dir, month, total):
    """Data for the supervisor's review page (review.html reads review-data.json)."""
    items = []
    for v in verdicts:
        if not v["flagged"]:
            continue
        l = v["line"]
        items.append({
            "line_id": l["line_id"], "action": v["action"], "dollars_at_issue": fmt(v["dollars"]),
            "reason": v["reason"], "evidence": v["evidence"], "rules": [str(r) for r in v["rules"]],
            "also": [f"{f['action']} (rule {f['rule']}): {f['reason']}" for f in v["also"]],
            "source": l["source"], "source_ref": l["source_ref"], "claim_number": l["claim_number"],
            "claimant_name": l.get("claimant_name", ""), "billing_provider": l.get("billing_provider", ""),
            "date_of_service": l["date_of_service"], "received_date": l["received_date"],
            "procedure_code": l["procedure_code"], "modifier": l["modifier"], "units": l["units"],
            "billed_charge": l["billed_charge"], "page": l.get("page"), "box": l.get("box"),
            "record": {k: v for k, v in l.items() if k not in INTERNAL and not isinstance(v, (list, dict))},
            "note": (v["calc"] or {}).get("note_ev") and {
                "note_id": v["calc"]["note_ev"]["note"]["note_id"], "text": v["calc"]["note_ev"]["note"]["note"]},
        })
    payload = {"month": month, "total": fmt(total), "accounting": accounting, "items": items,
               "questions": questions,
               "extraction": [{k: r[k] for k in ("line_id", "page", "row", "ocr_checks", "ocr_raw") if k in r}
                              for r in rows]}
    (out_dir / "review-data.json").write_text(json.dumps(payload, indent=1))


def main():
    ap = argparse.ArgumentParser(description="Pre-payment bill review (recommendations only).")
    ap.add_argument("--data", default="data", help="data folder holding reference/ and the month folder")
    ap.add_argument("--month", help="month folder name, e.g. 2026-09 (default: the only one present)")
    ap.add_argument("--out", help="output folder (default out/<month>)")
    ap.add_argument("--paper-extraction", help="use a reviewed paper-extraction.csv instead of OCR")
    a = ap.parse_args()
    verdicts, questions, acc, total, out_dir = run(a.data, a.month, a.out, a.paper_extraction)
    flagged = [v for v in verdicts if v["flagged"]]
    print(f"Reviewed {acc['total']} lines ({acc['electronic']} electronic, {acc['paper']} paper on "
          f"{acc['pages']} pages); flagged {len(flagged)}; {len(questions)} questions for the summary.")
    print(f"Total dollars at issue: ${fmt(total)} (suspected overpayments pending human review)")
    problems = acc["evidence_problems"]
    print(f"Evidence self-check: {'all cites match the source files' if not problems else str(len(problems)) + ' problems'}")
    for p in problems:
        print("  ", p)
    print(f"Wrote {out_dir}/flagged-lines.csv, review-summary.md, all-lines.csv, paper-extraction.csv")
    print(f"Supervisor review: python -m billreview.review_server {out_dir}")


if __name__ == "__main__":
    main()
