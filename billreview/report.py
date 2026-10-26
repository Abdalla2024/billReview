"""Write flagged-lines.csv, review-summary.md and the every-line verdict file."""
import csv
from collections import defaultdict
from decimal import Decimal

from .rules import fmt

FLAG_COLUMNS = ["line_id", "reason", "dollars_at_issue", "evidence", "action"]
ACTIONS = ["deny", "request_records", "reduce"]
LABEL = "suspected overpayments pending human review (not realized savings)"


def write_flagged(verdicts, path):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(FLAG_COLUMNS)
        for v in verdicts:
            if v["flagged"]:
                w.writerow([v["line"]["line_id"], v["reason"], fmt(v["dollars"]), v["evidence"], v["action"]])


def write_all_lines(verdicts, path):
    cols = ["line_id", "source", "source_ref", "claim_number", "date_of_service", "procedure_code", "modifier",
            "units", "billed_charge", "allowed_amount", "verdict", "dollars_at_issue", "reason"]
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for v in verdicts:
            l, c = v["line"], v.get("calc")
            w.writerow([l["line_id"], l["source"], l["source_ref"], l.get("claim_number", ""),
                        l.get("date_of_service", ""), l.get("procedure_code", ""), l.get("modifier", ""),
                        l.get("units", ""), l.get("billed_charge", ""), fmt(c["allowed"]) if c else "",
                        v["action"] if v["flagged"] else v.get("status", "not flagged"),
                        fmt(v["dollars"]) if v["flagged"] else "", v.get("reason", "")])


def _group_key(v):
    reason = v["reason"]
    rule = ",".join(str(r) for r in v["rules"])
    if v["action"] == "reduce":
        kinds = []
        if "rule 4" in reason:
            kinds.append("therapy units above what the note supports (rule 4)")
        if "rule 6" in reason:
            kinds.append("billed above the provider's rate (rule 6)")
        return "reduce", "Reduce: " + " and ".join(kinds)
    return v["action"], f"{v['action']}: rule {rule}"


INTERPRETATIONS = [
    "Provider's rate: the fee times 92% (in network) or 100% is rounded to the cent half-up, per unit, "
    "then multiplied by the units. task.md does not name a rounding mode; it only matters at an exact half cent.",
    "Rule 8: visits past the approved number are counted in date order; the first 2 such visits get "
    "request_records and every later one is denied. A question is raised wherever counting by visit number "
    "minus approved total would give a different action.",
    "Rule 8: therapy lines on a bill that rule 1 says belongs to someone else are not counted as the "
    "claimant's visits. A question is raised wherever counting them would change another line's action.",
    "In network needs a network_since date on or before the date of service; an in_network provider with no "
    "date is priced at 100% and raised as a question.",
    "Rule 7: paid rental months come only from rental-history.csv (this month's rental lines are not added). "
    "A TENS rental or purchase after 10 paid months is raised as a question, not flagged.",
    "Rule 5: the line's body part must match an entry of the claim's accepted list exactly (ignoring case). "
    "A paper line takes its body part from bills.csv only when that diagnosis code has one body part there.",
    "Rule 4: a note with no minutes leaves rule 4 out (as written); a note with two different times, a missing "
    "note or two matching notes is raised as a question and rule 4 is not applied.",
    "Rule 11: when a stopped line's allowed amount cannot be computed (no fee entry or unknown tax ID), dollars "
    "at issue are 0.00 with a question; the billed charge is never used instead.",
    "A claim number not in claims.csv, or a line with a missing or unreadable field, is not reviewed or flagged "
    "and is listed as a question.",
    "Rule 3 tie-break on the same received date uses the higher line_id as text (HB2609823-01 > HB2609623-01).",
    "When rule 4 and rule 6 both reduce a line, it is one reduce to the allowed amount (rate x note-supported "
    "units, capped at the billed charge).",
]


GROUP_TEXT = {
    "1": "Rule 1: the claim number matches but the date of birth does not, so the bill belongs to someone "
         "else. Names are not used to match. Dollars at issue are what would otherwise be paid (allowed amount).",
    "2": "Rule 2: the date of service is before the claim's date of injury, so the line is not part of the claim.",
    "3": "Rule 3: a second office visit for the same claimant, day and billing tax ID. The visit received "
         "first is kept (by received date, then line id); the later one is denied.",
    "5": "Rule 5: the line's body part (from its diagnosis code) is not on the claim's current accepted list. "
         "These are never denied for this reason: request records so the adjuster can decide compensability.",
    "7": "Rule 7: a TENS purchase on a claim whose TENS rental has fewer than 10 paid months. The purchase "
         "is denied and the rental keeps being paid.",
    "8": "Rule 8: therapy visits past the approved number of visits for that claim and billing tax ID. "
         "The first 2 visits past the approved number get request_records; later visits are denied. "
         "Evaluations are not counted as visits.",
}


def write_summary(verdicts, questions, extraction_rows, accounting, path, month):
    flagged = [v for v in verdicts if v["flagged"]]
    total = sum((v["dollars"] for v in flagged), Decimal("0"))
    by_action = defaultdict(lambda: [Decimal("0"), 0])
    for v in flagged:
        by_action[v["action"]][0] += v["dollars"]
        by_action[v["action"]][1] += 1
    out = []
    out.append(f"# Total dollars at issue: ${fmt(total)} (suspected overpayments pending human review)")
    out.append("")
    out.append(f"**{LABEL.capitalize()}.** Bill review month {month}: {len(flagged)} of "
               f"{accounting['total']} lines flagged. Nothing has been paid, denied or changed in any system; "
               "a bill review supervisor must approve this list before any action.")
    out.append("")
    out.append("| Action | Lines | Dollars at issue |")
    out.append("|---|---:|---:|")
    for a in ACTIONS:
        d, n = by_action[a]
        out.append(f"| {a} | {n} | ${fmt(d)} |")
    out.append(f"| **total** | **{len(flagged)}** | **${fmt(total)}** |")
    out.append("")
    out.append("Dollars at issue follow rule 11: for deny and request_records, the allowed amount (what would "
               "otherwise be paid); for reduce, billed charge minus allowed amount.")
    out.append("")

    out.append("## Flagged lines by reason")
    groups = defaultdict(list)
    for v in flagged:
        groups[_group_key(v)].append(v)
    order = sorted(groups, key=lambda k: (ACTIONS.index(k[0]), k[1]))
    for key in order:
        vs = groups[key]
        d = sum((v["dollars"] for v in vs), Decimal("0"))
        out.append("")
        out.append(f"### {key[1]} ({len(vs)} lines, ${fmt(d)})")
        rules = sorted({str(r) for v in vs for r in v["rules"]})
        for r in rules:
            if r in GROUP_TEXT:
                out.append(GROUP_TEXT[r])
        if key[0] == "reduce":
            out.append("Reduced to the allowed amount: the fee schedule amount for the code and modifier, at 92% "
                       "when the billing tax ID is in network on the date of service and 100% when not, rounded "
                       "per unit, times the units billed or the units the therapy note supports when fewer, "
                       "never more than the billed charge.")
        out.append("")
        out.append("| line_id | claim | DOS | code | billed | dollars | why |")
        out.append("|---|---|---|---|---:|---:|---|")
        for v in sorted(vs, key=lambda v: v["line"]["line_id"]):
            l = v["line"]
            code = l["procedure_code"] + (f" {l['modifier']}" if l["modifier"] else "")
            why = v["reason"].split(": ", 1)[-1] if key[0] == "reduce" else v["reason"]
            if l["source"] == "paper":
                why += f" [paper: page {l['page']}]"
            out.append(f"| {l['line_id']} | {l['claim_number']} | {l['date_of_service']} | {code} | "
                       f"{l['billed_charge']} | {fmt(v['dollars'])} | {why} |")
    out.append("")

    out.append("## Questions the rules do not answer (rule 12, not flagged on these alone)")
    if questions:
        for q in questions:
            out.append(f"- {', '.join(q['line_ids']) or 'Reference data'}: {q['question']}")
    else:
        out.append("- None this month.")
    out.append("")

    out.append("## Every line accounted for")
    out.append(f"- Electronic lines in bills.csv: {accounting['electronic']}")
    out.append(f"- Paper lines read from paper-bills.pdf: {accounting['paper']} "
               f"on {accounting['pages']} pages")
    out.append(f"- Total reviewed: {accounting['total']} = {len(flagged)} flagged + "
               f"{accounting['total'] - len(flagged)} not flagged"
               + (f" (of which {accounting['unreadable']} could not be reviewed; see questions)"
                  if accounting["unreadable"] else ""))
    out.append("- Every line and its verdict is in `all-lines.csv`.")
    probs = accounting.get("evidence_problems", [])
    out.append("- Evidence self-check: " + ("every record and value cited in flagged-lines.csv was re-read from the "
               "source files and matches." if not probs else f"{len(probs)} problems: " + "; ".join(probs)))
    out.append("")

    out.append("## Paper bill extraction (review before approving)")
    out.append("Paper lines were read from the scans by local OCR (Tesseract). Each value was cross-checked: "
               "the line charges must add up to the form's total charge (box 28), the claim must exist, the "
               "rendering NPI must belong to the billing tax ID in the provider file, and the diagnosis code "
               "must appear in bills.csv (which gives the body part). Values and page/row are in "
               "`paper-extraction.csv`; the review page shows each page image beside the values read.")
    bad = [r for r in extraction_rows if r["ocr_checks"]]
    if bad:
        out.append("")
        out.append("Lines whose extraction did not pass every check (verify against the scan):")
        for r in bad:
            out.append(f"- {r['line_id']} (page {r['page']} row {r['row']}): {'; '.join(r['ocr_checks'])}")
    else:
        out.append("")
        out.append(f"All {len(extraction_rows)} paper lines passed every cross-check.")
    out.append("")
    out.append("## Interpretations applied where task.md is silent")
    out.append("Each is applied the same way every run; where a different reading would change a verdict this "
               "month, the affected lines are listed under the questions above.")
    out.extend(f"- {t}" for t in INTERPRETATIONS)
    out.append("")
    out.append("## What this tool does not do")
    out.append("It only reads files and recommends. It does not pay, deny, hold or change anything in any "
               "system, and it does not contact providers or claimants. Late arrival, bundling, modifier "
               "correctness and missing documentation are not checked (rule 9).")
    out.append("")
    with open(path, "w") as f:
        f.write("\n".join(out))
    return total
