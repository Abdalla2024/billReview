"""Checks on the practice month (data/2026-09) and rule edge cases built from its records.

The paper lines come from out/2026-09/paper-extraction.csv when it exists (written by a
full OCR run) so the suite runs in seconds; test_ocr.py re-reads the scans.
"""
import copy
import csv
import re
from decimal import Decimal
from pathlib import Path

import pytest

from billreview import cli, data
from billreview.rules import Review, note_minutes, units_supported

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MONTH = DATA / "2026-09"
EXTRACTION = ROOT / "out" / "2026-09" / "paper-extraction.csv"


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    out = tmp_path_factory.mktemp("out")
    pe = EXTRACTION if EXTRACTION.exists() else None
    verdicts, questions, acc, total, out_dir = cli.run(DATA, "2026-09", out, pe)
    return {"verdicts": {v["line"]["line_id"]: v for v in verdicts}, "questions": questions, "acc": acc,
            "total": total, "out": out_dir}


def flagged(run):
    with open(run["out"] / "flagged-lines.csv", newline="") as f:
        return {r["line_id"]: r for r in csv.DictReader(f)}


# ------------------------------------------------------------ output contract

def test_every_input_line_has_one_verdict(run):
    bills = data.read_csv(MONTH / "bills.csv")
    paper = data.read_csv(run["out"] / "paper-extraction.csv")
    assert run["acc"]["electronic"] == len(bills) == 193
    assert run["acc"]["paper"] == len(paper) == 25
    ids = [b["line_id"] for b in bills] + [p["line_id"] for p in paper]
    assert len(ids) == len(set(ids))
    assert set(run["verdicts"]) == set(ids)
    with open(run["out"] / "all-lines.csv", newline="") as f:
        assert sorted(r["line_id"] for r in csv.DictReader(f)) == sorted(ids)


def test_flagged_csv_columns_actions_and_money(run):
    with open(run["out"] / "flagged-lines.csv", newline="") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == ["line_id", "reason", "dollars_at_issue", "evidence", "action"]
        rows = list(reader)
    assert rows
    for r in rows:
        assert r["action"] in {"deny", "reduce", "request_records"}
        assert re.fullmatch(r"\d+\.\d\d", r["dollars_at_issue"])
        assert r["reason"] and r["evidence"]


def test_summary_total_at_very_top_matches_csv(run):
    rows = flagged(run).values()
    total = sum(Decimal(r["dollars_at_issue"]) for r in rows)
    first = (run["out"] / "review-summary.md").read_text().splitlines()[0]
    assert first == f"# Total dollars at issue: ${total:.2f}"
    text = (run["out"] / "review-summary.md").read_text()
    for action in ("deny", "request_records", "reduce"):
        part = sum(Decimal(r["dollars_at_issue"]) for r in rows if r["action"] == action)
        assert f"| {action} | {sum(1 for r in rows if r['action'] == action)} | ${part:.2f} |" in text
    assert "pending human review" in text


def test_evidence_self_check_passes(run):
    assert run["acc"]["evidence_problems"] == []


def test_evidence_check_catches_fabricated_cites(run, tmp_path):
    from billreview.verify import verify
    import shutil
    for name in ("flagged-lines.csv", "paper-extraction.csv"):
        shutil.copy(run["out"] / name, tmp_path / name)
    rows = list(flagged(run).values())
    rows[0]["evidence"] = rows[0]["evidence"].replace("fee-schedule.csv PX210 250.00", "fee-schedule.csv PX210 260.00")
    rows[1]["evidence"] += "; note TN-9999 says \"40 min\""
    rows[2]["evidence"] += "; authorizations.csv AU-26913 14 visits 2026-08-17 to 2026-12-31"
    with open(tmp_path / "flagged-lines.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["line_id", "reason", "dollars_at_issue", "evidence", "action"])
        w.writeheader()
        w.writerows(rows)
    _, problems = verify(tmp_path, DATA, MONTH)
    assert len(problems) == 3, problems


# ------------------------------------------------------------ rule outcomes on the practice month

EXPECTED = {
    # line_id: (action, dollars)  -- each checked by hand against the source files
    "HB2609662-01": ("deny", "380.00"),            # rule 1: paper bill, DOB is another claimant's
    "HB2609198-01": ("deny", "210.00"),            # rule 2: DOS 08-04 before DOI 08-11 (paper)
    "HB2609823-01": ("deny", "144.85"),            # rule 3: later of two PX360 same day, same TIN (paper)
    "HB2609695-01": ("reduce", "96.00"),           # rule 4: 38 min -> 2 units, billed 4
    "HB2609541-01": ("request_records", "1150.40"),  # rule 5: lumbar MRI on a shoulder claim
    "HB2609014-01": ("reduce", "160.00"),          # rule 6: PX210 billed 410 vs OON 250
    "HB2609922-01": ("reduce", "140.00"),          # rule 6: in network 1750 x 92% = 1610
    "HB2609644-01": ("deny", "420.00"),            # rule 7: TENS purchase at 2 rental months
    "HB2609969-01": ("request_records", "160.00"),  # rule 8: visit 13 of 12
    "HB2609958-01": ("request_records", "160.00"),  # rule 8: visit 14 of 12
    "HB2609928-01": ("deny", "160.00"),            # rule 8: visit 15 (deny beats the rule 6 reduce)
    "HB2609981-01": ("deny", "160.00"),            # rule 8: visit 16
}


@pytest.mark.parametrize("line_id", EXPECTED)
def test_expected_flags(run, line_id):
    r = flagged(run)[line_id]
    assert (r["action"], r["dollars_at_issue"]) == EXPECTED[line_id]


TRAPS = {
    "HB2609108-01": "ER visit on the date of injury is not before it (rule 2)",
    "HB2609623-01": "first of two same-day office visits is paid (rule 3)",
    "HB2609953-01": "telehealth PX360 TLV is not an office visit (rule 3)",
    "HB2609409-03": "office visit with a same-day telehealth line is not a duplicate",
    "HB2609947-01": "cervical X-ray: cervical spine was added to the accepted list later; current list applies (rule 5)",
    "HB2609334-01": "Tolliver before network_since 2026-08-15 is paid at 100% (rule 6)",
    "HB2609723-01": "TENS rental billed exactly at 92% of fee (rule 6)",
    "HB2609715-01": "TENS rental continues while the purchase is denied (rule 7)",
    "HB2609189-05": "42 minutes = 2 units + 12 leftover = 3 units (rule 4)",
    "HB2609347-03": "27 minutes = 1 unit + 12 leftover = 2 units (rule 4)",
    "HB2609051-02": "note gives no minutes: rule 4 does not apply",
    "HB2609189-02": "visit 1 under AU-26099 (2 approved) is within the approval (rule 8)",
    "HB2609189-05": "visit 4: AU-26099 + AU-26924 add up to 8 approved (rule 8, approved_date ignored)",
    "HB2609652-01": "visit 8 of 12 approved (rule 8)",
    "HB2609892-01": "PX120 billed under the fee schedule amount",
}


@pytest.mark.parametrize("line_id", TRAPS)
def test_traps_not_flagged(run, line_id):
    assert line_id in run["verdicts"], line_id
    assert not run["verdicts"][line_id]["flagged"], TRAPS[line_id]


def test_no_unexpected_flags(run):
    """Only the lines checked by hand above are flagged (catches new false positives)."""
    extra = set(flagged(run)) - set(EXPECTED) - {"HB2609214-01", "HB2609225-02", "HB2609455-02"}
    assert not extra


# ------------------------------------------------------------ rule 4 arithmetic

@pytest.mark.parametrize("minutes,units", [(7, 0), (11, 0), (12, 1), (15, 1), (26, 1), (27, 2), (30, 2),
                                           (38, 2), (42, 3), (45, 3), (56, 3), (57, 4), (63, 4)])
def test_units_supported(minutes, units):
    assert units_supported(minutes) == units


@pytest.mark.parametrize("text,minutes", [
    ("Therapeutic exercise, time 0:28. Theraband rows 3 x 12, wall slides 2 x 10.", 28),
    ("Therapeutic activities, time 1:03. Functional lifting and carrying tasks.", 63),
    ("Pt seen for manual therapy. Mobilization grade II to III, 3 bouts. Total timed minutes 48.", 48),
    ("Ther ex x 52 mins. Strengthening and range of motion.", 52),
    ("AROM flexion to 140 deg. Pain 4/10 before, 2/10 after. Timed treatment: 34 minutes.", 34),
    ("Manual therapy 42 min. STM and joint mobs. Pt reports 30 percent better since eval.", 42),
    ("Ther act x 67 mins. Simulated job tasks, 2 rounds of 6 lifts at 15 lb.", 67),
])
def test_note_minutes_formats(text, minutes):
    assert note_minutes(text)[0] == minutes


def test_note_without_minutes():
    assert note_minutes("Therapeutic exercise per plan of care. See daily flowsheet.")[0] is None


def test_every_practice_note_with_numbers_parses():
    for n in data.load_notes(MONTH):
        m, _ = note_minutes(n["note"])
        if re.search(r"min|\d:\d\d", n["note"]):
            assert m is not None, n["note_id"]


# ------------------------------------------------------------ edge cases built from practice records

@pytest.fixture(scope="module")
def base():
    ref = data.Reference(DATA / "reference")
    lines = data.load_electronic(MONTH)
    notes = data.load_notes(MONTH)
    return ref, lines, notes


def review(ref, lines, notes):
    return {v["line"]["line_id"]: v for v in Review(lines, notes, ref).run()}


def line(lines, line_id):
    return next(l for l in lines if l["line_id"] == line_id)


def test_rule3_same_received_day_denies_higher_line_id(base):
    ref, lines, notes = base
    lines = copy.deepcopy(lines)
    a = line(lines, "HB2609117-02")  # PX330 WC26-04279 2026-08-14 Quillan
    b = dict(a, line_id="HB2609999-01", bill_id="HB2609999", rendering_npi="1063529948")
    lines.append(b)
    v = review(ref, lines, notes)
    assert v["HB2609999-01"]["action"] == "deny" and not v["HB2609117-02"]["flagged"]


def test_rule3_different_tax_ids_are_not_duplicates(base):
    ref, lines, notes = base
    lines = copy.deepcopy(lines)
    a = line(lines, "HB2609117-02")
    lines.append(dict(a, line_id="HB2609999-01", bill_id="HB2609999", billing_tin="52-3817406",
                      rendering_npi="1043827715", billed_charge="100.00"))
    assert not review(ref, lines, notes)["HB2609999-01"]["flagged"]


def test_rule3_earlier_visit_counts_even_when_denied(base):
    """The earlier visit is denied by rule 2 but still makes the later one a duplicate."""
    ref, lines, notes = base
    lines = copy.deepcopy(lines)
    a = line(lines, "HB2609117-02")
    a["date_of_service"] = "2026-08-01"  # before DOI 2026-08-04
    lines.append(dict(a, line_id="HB2609999-01", bill_id="HB2609999", received_date="2026-09-20"))
    v = review(ref, lines, notes)
    assert v["HB2609117-02"]["rules"] == [2]
    assert v["HB2609999-01"]["action"] == "deny"
    assert 3 in v["HB2609999-01"]["rules"]


def test_rule1_ignores_name_and_uses_dob(base):
    ref, lines, notes = base
    lines = copy.deepcopy(lines)
    line(lines, "HB2609117-01")["claimant_name"] = "Paloma Reyes Hurst (typo)"
    line(lines, "HB2609117-02")["claimant_dob"] = "1989-05-31"
    v = review(ref, lines, notes)
    assert not v["HB2609117-01"]["flagged"]
    assert v["HB2609117-02"]["action"] == "deny" and v["HB2609117-02"]["rules"] == [1]


def test_rule5_never_denies(base):
    ref, lines, notes = base
    v = review(ref, lines, notes)
    r = v["HB2609541-01"]
    assert r["action"] == "request_records"
    assert r["dollars"] == Decimal("1150.40")  # allowed amount, not billed charge


def test_rule7_no_rental_means_no_rule(base):
    ref, lines, notes = base
    lines = copy.deepcopy(lines)
    p = line(lines, "HB2609644-01")
    # a claim with no TENS rental (body part set to its accepted one so rule 5 stays out of it)
    p.update(claim_number="WC26-04083", claimant_dob="1964-03-03", body_part="left knee")
    v = review(ref, lines, notes)
    assert v["HB2609644-01"]["action"] == "reduce"  # only the rate rule: 495 billed vs 420


def test_rule8_evaluation_not_counted(base):
    ref, lines, notes = base
    lines = copy.deepcopy(lines)
    ev = line(lines, "HB2609189-01")  # PX290 evaluation
    for d in ("2026-08-10", "2026-08-11", "2026-08-12", "2026-08-13", "2026-08-14"):
        lines.append(dict(ev, line_id=f"HB26099{d[-2:]}-01", date_of_service=d))
    v = review(ref, lines, notes)
    assert not any(v[f"HB26099{d}-01"]["flagged"] for d in ("10", "11", "12", "13", "14"))


def test_rule8_two_lines_same_day_are_one_visit_and_both_flagged(base):
    ref, lines, notes = base
    lines = copy.deepcopy(lines)
    t = line(lines, "HB2609981-01")  # visit 16 of 12 for WC26-04618
    lines.append(dict(t, line_id="HB2609982-01", bill_id="HB2609982", procedure_code="PX270",
                      billed_charge="96.00", units="2"))
    v = review(ref, lines, notes)
    assert v["HB2609982-01"]["action"] == "deny" and v["HB2609981-01"]["action"] == "deny"
    assert "visit 16 " in v["HB2609982-01"]["reason"]


def test_deny_dollars_use_note_supported_units(base):
    """Rule 11: a denied therapy line's dollars are its allowed amount, which uses the note's units."""
    ref, lines, notes = base
    lines = copy.deepcopy(lines)
    l = line(lines, "HB2609695-01")  # 4 units billed, note supports 2
    l["claimant_dob"] = "1900-01-01"
    v = review(ref, lines, notes)
    assert v["HB2609695-01"]["action"] == "deny" and v["HB2609695-01"]["dollars"] == Decimal("96.00")


# ------------------------------------------------------------ rehearsal hardening (synthetic edge cases)

def questions_for(ref, lines, notes, line_id):
    r = Review(lines, notes, ref)
    v = {x["line"]["line_id"]: x for x in r.run()}
    return v, [q["question"] for q in r.questions if line_id in q["line_ids"]]


def test_deny_without_fee_entry_reports_zero_and_asks(base):
    ref, lines, notes = base
    lines = copy.deepcopy(lines)
    l = line(lines, "HB2609117-02")
    l.update(modifier="GT", date_of_service="2026-08-01")  # before DOI, and no fee entry for PX330 GT
    v, qs = questions_for(ref, lines, notes, "HB2609117-02")
    assert v["HB2609117-02"]["action"] == "deny" and v["HB2609117-02"]["dollars"] == Decimal("0.00")
    assert any("cannot be computed" in q for q in qs)


def test_missing_note_is_a_question_not_a_flag(base):
    ref, lines, notes = base
    v, qs = questions_for(ref, copy.deepcopy(lines), [n for n in notes if n["note_id"] != "TN-5157"],
                          "HB2609695-01")
    assert not v["HB2609695-01"]["flagged"] and any("No treatment note" in q for q in qs)


def test_note_with_two_times_is_a_question_not_a_flag(base):
    ref, lines, notes = base
    notes = copy.deepcopy(notes)
    next(n for n in notes if n["note_id"] == "TN-5157")["note"] = "Ther ex 38 min. Manual 20 min."
    v, qs = questions_for(ref, copy.deepcopy(lines), notes, "HB2609695-01")
    assert not v["HB2609695-01"]["flagged"] and any("more than one time" in q for q in qs)


def test_hyphenated_minutes():
    assert note_minutes("Therapeutic exercise, 45-minute session.")[0] == 45


def test_rule8_counts_past_visits_in_order_and_reports_other_reading(base):
    """Approval drops to 3 visits in August, then 12 more from September: August visits 4-5 are the
    1st and 2nd past the approval, so September visits past 12 are the 3rd+ past and denied."""
    _, lines, notes = base
    ref = data.Reference(DATA / "reference")
    a = next(a for a in ref.authorizations if a["auth_id"] == "AU-26913")
    a.update(approved_visits="3", end_date="2026-08-31")
    ref.authorizations.append(dict(a, auth_id="AU-TEST", approved_visits="12", start_date="2026-09-01",
                                   end_date="2026-12-31"))
    r = Review(copy.deepcopy(lines), notes, ref)
    v = {x["line"]["line_id"]: x for x in r.run()}
    by_date = {x["line"]["date_of_service"]: x["action"] for x in v.values()
               if x["flagged"] and x["line"]["claim_number"] == "WC26-04618"}
    assert by_date == {"2026-08-28": "request_records", "2026-08-30": "request_records",
                       "2026-09-16": "deny", "2026-09-18": "deny", "2026-09-20": "deny", "2026-09-22": "deny"}
    q = [q for q in r.questions if "minus its approved total" in q["question"]]
    assert q and set(q[0]["line_ids"]) == {"HB2609969-01", "HB2609958-01"}


def test_rule8_rule1_reading_is_reported_when_it_matters(base):
    """A someone-else's therapy bill on the claim shifts visit numbers only under the other reading."""
    ref, lines, notes = base
    lines = copy.deepcopy(lines)
    t = line(lines, "HB2609381-01")  # WC26-04618 first visit 08-20
    lines.append(dict(t, line_id="HB2609990-01", bill_id="HB2609990", date_of_service="2026-08-19",
                      claimant_dob="1950-01-01"))
    r = Review(lines, notes, ref)
    v = {x["line"]["line_id"]: x for x in r.run()}
    assert v["HB2609990-01"]["action"] == "deny" and v["HB2609990-01"]["rules"] == [1]
    assert v["HB2609969-01"]["action"] == "request_records"  # unchanged primary reading
    q = [q for q in r.questions if "belongs to someone else when numbering" in q["question"]]
    # counting it would make 09-14 visit 13 (request_records) and 09-18 visit 15 (deny)
    assert q and set(q[0]["line_ids"]) == {"HB2609870-01", "HB2609958-01"}


def test_rule3_unreadable_received_date_is_a_question(base):
    ref, lines, notes = base
    lines = copy.deepcopy(lines)
    a = line(lines, "HB2609117-02")
    lines.append(dict(a, line_id="HB2609999-01", bill_id="HB2609999", received_date=""))
    v, qs = questions_for(ref, lines, notes, "HB2609999-01")
    assert not v["HB2609999-01"]["flagged"] and any("received date" in q for q in qs)


def test_in_network_without_date_is_priced_out_of_network_and_asked(base):
    _, lines, notes = base
    ref = data.Reference(DATA / "reference")
    for p in ref.providers:
        if p["billing_tin"] == "52-4097721":
            p["network_since"] = ""
    r = Review(copy.deepcopy(lines), notes, ref)
    v = {x["line"]["line_id"]: x for x in r.run()}
    assert not v["HB2609922-01"]["flagged"]  # PX130 1750 billed = 100% fee
    assert any("no network_since" in q["question"] for q in r.questions)


# ------------------------------------------------------------ input validation and paper parsing

def test_unusable_fields_are_reported_not_guessed():
    from billreview.cli import unusable_fields
    good = {"line_id": "HB1-01", "bill_id": "HB1", "claim_number": "WC", "claimant_dob": "1970-01-01",
            "billing_tin": "1", "rendering_npi": "1", "date_of_service": "2026-09-01", "procedure_code": "PX1",
            "units": "2", "billed_charge": "10.50", "received_date": "", "source": "electronic"}
    assert unusable_fields(good) == []
    assert unusable_fields(dict(good, units="1.0")) == ["units"]
    assert unusable_fields(dict(good, billed_charge="$10.50")) == ["billed_charge"]
    assert unusable_fields(dict(good, claimant_dob="")) == ["claimant_dob"]
    assert unusable_fields(dict(good, source="paper", bill_id="", line_id="UNREAD-PAGE01-01")) == ["bill_id"]


def test_paper_cell_parser():
    from billreview.ocr import _parse_cells
    p = _parse_cells(["09 05 26", "11", "E0730-RR", "A", "62.56", "1", "1386719405"])
    assert (p["procedure_code"], p["modifier"], p["date_of_service"]) == ("E0730", "RR", "2026-09-05")
    assert _parse_cells(["09 05 26", "11", "PX270", "A", "62.56", "", "1386719405"]) is None


def test_paper_dx_takes_body_part_only_when_unambiguous(base):
    from billreview import extract
    ref, lines, _ = base
    lines = copy.deepcopy(lines)
    row = {"line_id": "HB9-01", "bill_id": "HB9", "page": 1, "row": 1, "diagnosis_code": "S46.011A",
           "billing_tin": "52-3817406", "box": None}
    assert extract.to_bill_lines([row], ref, lines)[0]["body_part"] == "right shoulder"
    lines.append(dict(lines[0], line_id="HBX-01", diagnosis_code="S46.011A", body_part="left shoulder"))
    assert extract.to_bill_lines([row], ref, lines)[0]["body_part"] == ""


TAMPERS = [
    # (line_id, field, old, new, what the verifier must catch)
    ("HB2609014-01", "evidence", "x 100% = 250.00/unit", "x 100% = 251.00/unit", "unit rate arithmetic"),
    ("HB2609014-01", "evidence", "x 100% = 250.00/unit", "x 92% = 230.00/unit", "network percentage"),
    ("HB2609014-01", "dollars_at_issue", "160.00", "170.00", "rule 11 dollars"),
    ("HB2609695-01", "evidence", "note TN-5157", "note TN-5154", "note of another line"),
    ("HB2609695-01", "evidence", "allowed 2 x 48.00 = 96.00", "allowed 3 x 48.00 = 144.00", "units without note support"),
    ("HB2609969-01", "evidence", "visit 13 of claim", "visit 12 of claim", "visit number"),
    ("HB2609969-01", "evidence", "= 12 approved", "= 14 approved", "approved total"),
    ("HB2609823-01", "evidence", "NPI 1043827715 received", "NPI 1588204631 received", "earlier visit values"),
    ("HB2609198-01", "evidence", "date_of_injury 2026-08-11", "date_of_injury 2026-08-01", "claim DOI"),
    ("HB2609541-01", "evidence", "body part lumbar spine", "body part right shoulder", "body part"),
    ("HB2609662-01", "evidence", "Dana Kowalczyk-Reyes DOB", "Dana Kowalczyk DOB", "claimant name"),
    ("HB2609644-01", "evidence", "2 paid months", "3 paid months", "rental months"),
]


@pytest.mark.parametrize("line_id,field,old,new,what", TAMPERS, ids=[t[4] for t in TAMPERS])
def test_verifier_catches_each_kind_of_wrong_figure(run, tmp_path, line_id, field, old, new, what):
    import shutil
    from billreview.verify import verify
    shutil.copy(run["out"] / "paper-extraction.csv", tmp_path / "paper-extraction.csv")
    rows = list(flagged(run).values())
    row = next(r for r in rows if r["line_id"] == line_id)
    assert old in row[field], (what, row[field])
    row[field] = row[field].replace(old, new)
    with open(tmp_path / "flagged-lines.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["line_id", "reason", "dollars_at_issue", "evidence", "action"])
        w.writeheader()
        w.writerows(rows)
    _, problems = verify(tmp_path, DATA, MONTH)
    assert problems and all(p.startswith(line_id) for p in problems), (what, problems)
