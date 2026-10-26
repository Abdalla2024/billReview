"""Check flagged-lines.csv against the source files: every cited record must exist and
every cited value must match it. An evidence cite to a record that does not exist, or a
figure that does not match it, is treated as a fabrication.
"""
import csv
import re
from decimal import Decimal
from pathlib import Path

from .data import Reference, load_electronic, load_notes, read_csv

COLUMNS = ["line_id", "reason", "dollars_at_issue", "evidence", "action"]


def verify(out_dir, data_dir, month_dir):
    out_dir = Path(out_dir)
    ref = Reference(Path(data_dir) / "reference")
    bills = {l["line_id"]: l for l in load_electronic(month_dir)}
    paper = {r["line_id"]: r for r in read_csv(out_dir / "paper-extraction.csv")}
    notes = {n["note_id"]: n for n in load_notes(month_dir)}
    auths = {a["auth_id"]: a for a in ref.authorizations}
    problems = []

    with open(out_dir / "flagged-lines.csv", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != COLUMNS:
            problems.append(f"columns are {reader.fieldnames}, expected {COLUMNS}")
        rows = list(reader)
    seen = set()
    for r in rows:
        lid, ev = r["line_id"], r["evidence"]
        bad = lambda msg: problems.append(f"{lid}: {msg}")
        if lid in seen:
            bad("flagged twice")
        seen.add(lid)
        if lid not in bills and lid not in paper:
            bad("line_id is not in bills.csv or the paper extraction")
        if r["action"] not in ("deny", "reduce", "request_records"):
            bad(f"action {r['action']!r}")
        if not re.fullmatch(r"\d+\.\d\d", r["dollars_at_issue"]) or Decimal(r["dollars_at_issue"]) <= 0:
            bad(f"dollars_at_issue {r['dollars_at_issue']!r}")
        line = bills.get(lid) or paper.get(lid) or {}
        if line and Decimal(r["dollars_at_issue"]) > Decimal(line["billed_charge"]):
            bad("dollars at issue exceed the billed charge")

        for m in re.finditer(r"bills\.csv line_id (HB\d+-\d\d)", ev):
            if m.group(1) not in bills:
                bad(f"cites bills.csv line {m.group(1)} which does not exist")
        for m in re.finditer(r"paper-bills\.pdf page (\d+) \(bill (HB\d+) line (\d\d)\)", ev):
            p = paper.get(f"{m.group(2)}-{m.group(3)}")
            if not p or int(p["page"]) != int(m.group(1)):
                bad(f"cites paper page {m.group(1)} bill {m.group(2)} line {m.group(3)} which was not read there")
        for m in re.finditer(r"\b(HB\d{7}-\d\d) \(", ev):
            if m.group(1) not in bills and m.group(1) not in paper:
                bad(f"cites line {m.group(1)} which does not exist")
        for m in re.finditer(r"note (TN-\d+) (?:says )?\"([^\"]+)\"", ev):
            n = notes.get(m.group(1))
            if not n or m.group(2) not in n["note"]:
                bad(f"cites note {m.group(1)} text {m.group(2)!r} which is not in that note")
        for m in re.finditer(r"(AU-\d+) (\d+) visits (\d{4}-\d\d-\d\d) to (\d{4}-\d\d-\d\d)", ev):
            a = auths.get(m.group(1))
            if not a or (a["approved_visits"], a["start_date"], a["end_date"]) != m.group(2, 3, 4):
                bad(f"authorization cite {m.group(0)!r} does not match authorizations.csv")
        for m in re.finditer(r"fee-schedule\.csv (\w+)(?: (\w\w))? ([\d.]+) per", ev):
            fee = ref.fees.get((m.group(1), m.group(2) or ""))
            if not fee or fee["fee_schedule_amount"] != m.group(3):
                bad(f"fee cite {m.group(0)!r} does not match fee-schedule.csv")
        for m in re.finditer(r"claims\.csv (WC\d\d-\d{5})(?::| )", ev):
            c = ref.claims.get(m.group(1))
            if not c:
                bad(f"cites claim {m.group(1)} which is not in claims.csv")
                continue
            tail = ev[m.end():m.end() + 160]
            for field, rx in (("claimant_dob", r"^ ?[^;|]*?DOB (\d{4}-\d\d-\d\d)"),
                              ("date_of_injury", r"^ ?date_of_injury (\d{4}-\d\d-\d\d)"),
                              ("accepted_body_parts", r"^ ?accepted_body_parts \"([^\"]*)\"")):
                mm = re.search(rx, tail)
                if mm and mm.group(1) != c[field]:
                    bad(f"claims.csv {m.group(1)} {field} cited as {mm.group(1)}, file says {c[field]}")
        for m in re.finditer(r"providers\.csv (.+?) TIN (\d\d-\d{7}): (\w+)(?: since (\d{4}-\d\d-\d\d))?", ev):
            p = ref.provider_by_tin.get(m.group(2))
            if not p or p["network_status"] != m.group(3) or (m.group(4) or "") != p["network_since"]:
                bad(f"provider cite {m.group(0)!r} does not match providers.csv")
        for m in re.finditer(r"rental-history\.csv (WC\d\d-\d{5}) .*? E0730 RR (\d+) paid months", ev):
            if not any(x["claim_number"] == m.group(1) and x["rental_months_paid"] == m.group(2) for x in ref.rentals):
                bad(f"rental cite {m.group(0)!r} does not match rental-history.csv")
        if line:
            m = re.search(r"billed (\d+\.\d\d)", ev)
            if m and m.group(1) != line["billed_charge"]:
                bad(f"billed amount cited as {m.group(1)}, line says {line['billed_charge']}")
    return rows, problems
