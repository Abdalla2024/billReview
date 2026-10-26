"""Check flagged-lines.csv against the source files: every cited record must exist, every cited
value must match it, and every figure in the evidence must recompute. An evidence cite to a record
that does not exist, or a figure that does not match it, is treated as a fabrication.

This re-reads the files itself and does not reuse the rules engine's calculations.
"""
import csv
import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from .data import Reference, load_electronic, load_notes, read_csv

COLUMNS = ["line_id", "reason", "dollars_at_issue", "evidence", "action"]
TIMED = {"PX270", "PX280", "PX320"}
DATE = r"\d{4}-\d\d-\d\d"


def _cents(x):
    return Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def verify(out_dir, data_dir, month_dir):
    out_dir = Path(out_dir)
    ref = Reference(Path(data_dir) / "reference")
    bills = {l["line_id"]: l for l in load_electronic(month_dir)}
    paper = {r["line_id"]: r for r in read_csv(out_dir / "paper-extraction.csv")}
    all_lines = {**bills, **paper}
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
        lid, ev, action = r["line_id"], r["evidence"], r["action"]

        def bad(msg):
            problems.append(f"{lid}: {msg}")

        if lid in seen:
            bad("flagged twice")
        seen.add(lid)
        line = all_lines.get(lid)
        if line is None:
            bad("line_id is not in bills.csv or the paper extraction")
            continue
        if action not in ("deny", "reduce", "request_records"):
            bad(f"action {action!r}")
        if not re.fullmatch(r"\d+\.\d\d", r["dollars_at_issue"]):
            bad(f"dollars_at_issue {r['dollars_at_issue']!r}")
            continue
        dollars, billed = Decimal(r["dollars_at_issue"]), Decimal(line["billed_charge"])
        if dollars > billed:
            bad("dollars at issue exceed the billed charge")

        # -- the line itself, as cited
        for m in re.finditer(r"bills\.csv line_id (HB\d+-\d\d)", ev):
            if m.group(1) not in bills:
                bad(f"cites bills.csv line {m.group(1)} which does not exist")
        for m in re.finditer(r"paper-bills\.pdf page (\d+) \(bill (HB\d+) line (\d\d)\)", ev):
            p = paper.get(f"{m.group(2)}-{m.group(3)}")
            if not p or int(p["page"]) != int(m.group(1)):
                bad(f"cites paper page {m.group(1)} bill {m.group(2)} line {m.group(3)} which was not read there")
        m = re.search(r"billed (\d+\.\d\d)", ev)
        if m and Decimal(m.group(1)) != billed:
            bad(f"billed amount cited as {m.group(1)}, line says {line['billed_charge']}")
        m = re.search(r": (\w+)(?: (\w\w))? x(\d+) billed", ev)
        if m and (m.group(1), m.group(2) or "", m.group(3)) != (line["procedure_code"], line["modifier"], line["units"]):
            bad(f"code/units cited as {m.group(0)!r}, line has {line['procedure_code']} {line['modifier']} x{line['units']}")
        for m in re.finditer(rf"\bDOS ({DATE})", ev):
            if m.group(1) != line["date_of_service"] and not re.search(rf"earlier visit[^|]*{m.group(1)}", ev):
                bad(f"date of service cited as {m.group(1)}, line says {line['date_of_service']}")
                break

        # -- other lines cited (rule 3 earlier visit)
        for m in re.finditer(r"earlier visit (HB\d{7}-\d\d) \((\w+) NPI (\d+) received (" + DATE + r")\)", ev):
            o = all_lines.get(m.group(1))
            if not o:
                bad(f"cites line {m.group(1)} which does not exist")
            elif (o["procedure_code"], o["rendering_npi"], o["received_date"]) != m.group(2, 3, 4) or \
                    (o["claim_number"], o["date_of_service"], o["billing_tin"]) != \
                    (line["claim_number"], line["date_of_service"], line["billing_tin"]):
                bad(f"earlier visit cite {m.group(0)!r} does not match that line")
            elif (o["received_date"], o["line_id"]) >= (line["received_date"], lid):
                bad(f"cited earlier visit {m.group(1)} was not received first")

        # -- notes: text must be in the note, and the note must be this line's note
        for m in re.finditer(r"note (TN-\d+) (?:says )?\"([^\"]+)\"", ev):
            n = notes.get(m.group(1))
            if not n or m.group(2) not in n["note"]:
                bad(f"cites note {m.group(1)} text {m.group(2)!r} which is not in that note")
            elif (n["claim_number"], n["rendering_npi"], n["date_of_service"], n["procedure_code"]) != \
                    (line["claim_number"], line["rendering_npi"], line["date_of_service"], line["procedure_code"]):
                bad(f"note {m.group(1)} is not the note for this line")

        # -- claim file
        for m in re.finditer(r"claims\.csv (WC\d\d-\d{5})(?::| )", ev):
            c = ref.claims.get(m.group(1))
            if not c:
                bad(f"cites claim {m.group(1)} which is not in claims.csv")
                continue
            tail = ev[m.end():m.end() + 160]
            for field, rx in (("claimant_dob", r"^ ?[^;|]*?DOB (" + DATE + ")"),
                              ("date_of_injury", r"^ ?date_of_injury (" + DATE + ")"),
                              ("accepted_body_parts", r"^ ?accepted_body_parts \"([^\"]*)\""),
                              ("claimant_name", r"^ ?([A-Z][^,;|()]*?) DOB"),
                              ("claimant_name", r"^ ?\(([^,;|]*), DOB")):
                mm = re.search(rx, tail)
                if mm and mm.group(1) != c[field]:
                    bad(f"claims.csv {m.group(1)} {field} cited as {mm.group(1)!r}, file says {c[field]!r}")
        m = re.search(rf"DOB on bill ({DATE})", ev)
        if m and m.group(1) != line["claimant_dob"]:
            bad(f"bill DOB cited as {m.group(1)}, line says {line['claimant_dob']}")

        # -- body part (rule 5)
        m = re.search(r"dx (\S+) body part ([^;(]+?)(?: \(from bills\.csv (HB\d+-\d\d) with the same dx\))?;", ev)
        if m:
            src = bills.get(m.group(3)) if m.group(3) else line
            if m.group(1) != line["diagnosis_code"]:
                bad(f"diagnosis cited as {m.group(1)}, line says {line['diagnosis_code']}")
            if not src or src["diagnosis_code"] != line["diagnosis_code"] or src.get("body_part") != m.group(2):
                bad(f"body part {m.group(2)!r} does not come from the cited record")

        # -- authorizations and visit counting (rule 8)
        cited_auths = []
        for m in re.finditer(r"(AU-\d+) (\d+) visits (" + DATE + ") to (" + DATE + ")", ev):
            a = auths.get(m.group(1))
            if not a or (a["approved_visits"], a["start_date"], a["end_date"]) != m.group(2, 3, 4) or \
                    (a["claim_number"], a["billing_tin"]) != (line["claim_number"], line["billing_tin"]):
                bad(f"authorization cite {m.group(0)!r} does not match authorizations.csv for this claim and TIN")
            else:
                cited_auths.append(a)
        m = re.search(r"visit (\d+) of claim \S+ at this TIN \(visit dates: ([^)]*)\)", ev)
        if m:
            dates = sorted({l["date_of_service"] for l in all_lines.values()
                            if l["procedure_code"] in TIMED and l["claim_number"] == line["claim_number"]
                            and l["billing_tin"] == line["billing_tin"]})
            listed = [d.strip() for d in m.group(2).split(",")]
            if not set(listed) <= set(dates):
                bad("cited visit dates include a date with no timed therapy line")
            if line["date_of_service"] not in listed or listed.index(line["date_of_service"]) + 1 != int(m.group(1)):
                bad(f"visit number {m.group(1)} does not match the cited visit dates")
            m2 = re.search(r"= (\d+) approved", ev)
            if m2 and int(m2.group(1)) != sum(int(a["approved_visits"]) for a in cited_auths):
                bad(f"approved total {m2.group(1)} does not add up from the cited authorizations")
            if any(not (a["start_date"] <= line["date_of_service"] <= a["end_date"]) for a in cited_auths):
                bad("a cited authorization does not cover this date of service")

        # -- provider file and pricing
        net = None
        for m in re.finditer(r"providers\.csv (.+?) TIN (\d\d-\d{7}): (\w+)(?: since (" + DATE + "))?", ev):
            p = ref.provider_by_tin.get(m.group(2))
            if not p or p["network_status"] != m.group(3) or (m.group(4) or "") != p["network_since"] \
                    or p["billing_provider"] != m.group(1) or m.group(2) != line["billing_tin"]:
                bad(f"provider cite {m.group(0)!r} does not match providers.csv for this line")
            else:
                net = p["network_status"] == "in_network" and p["network_since"] != "" \
                    and line["date_of_service"] >= p["network_since"]
        unit_rate = None
        for m in re.finditer(r"fee-schedule\.csv (\w+)(?: (\w\w))? ([\d.]+) per [^x]+x (92|100)% = ([\d.]+)/unit", ev):
            fee = ref.fees.get((m.group(1), m.group(2) or ""))
            if not fee or fee["fee_schedule_amount"] != m.group(3) or \
                    (m.group(1), m.group(2) or "") != (line["procedure_code"], line["modifier"]):
                bad(f"fee cite {m.group(0)!r} does not match fee-schedule.csv for this line")
                continue
            if net is not None and (m.group(4) == "92") != net:
                bad(f"priced at {m.group(4)}% but the provider is {'in' if net else 'out of'} network on the DOS")
            unit_rate = _cents(Decimal(m.group(3)) * Decimal(m.group(4)) / 100)
            if unit_rate != Decimal(m.group(5)):
                bad(f"unit rate {m.group(5)} should be {unit_rate}")
        m = re.search(r"allowed (\d+) x ([\d.]+) = ([\d.]+)", ev)
        if m:
            units, rate, total = int(m.group(1)), Decimal(m.group(2)), Decimal(m.group(3))
            if unit_rate is not None and rate != unit_rate:
                bad(f"allowed uses rate {rate}, fee cite gives {unit_rate}")
            if units * rate != total:
                bad(f"allowed arithmetic {m.group(0)!r} is wrong")
            if units > int(line["units"]):
                bad("allowed units exceed units billed")
            if units < int(line["units"]):
                mm = re.search(r"\"([^\"]+)\"[^|;]*?(?:-> |supports )(\d+)", ev)
                if not mm or int(mm.group(2)) != units:
                    bad("allowed units are below units billed without a note that supports them")
            allowed = min(total, billed)
            expect = billed - allowed if action == "reduce" else allowed
            if dollars != expect:
                bad(f"dollars at issue {dollars} should be {expect} for {action} (rule 11)")
        elif dollars != 0:
            bad("dollars at issue given without an allowed-amount calculation")

        for m in re.finditer(r"rental-history\.csv (WC\d\d-\d{5}) .*? E0730 RR (\d+) paid months", ev):
            if not any(x["claim_number"] == m.group(1) and x["rental_months_paid"] == m.group(2) for x in ref.rentals):
                bad(f"rental cite {m.group(0)!r} does not match rental-history.csv")
    return rows, problems
