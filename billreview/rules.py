"""The insurer's review rules (TASK.md rules 1-12), applied deterministically.

Every finding carries the records and values it compared, so the evidence column
can be checked against the source files. Money is handled in Decimal cents.
"""
import re
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

OFFICE_VISIT_CODES = {"PX330", "PX340", "PX350", "PX360", "PX370", "PX380"}
TIMED_THERAPY_CODES = {"PX270", "PX280", "PX320"}
EVALUATION_CODES = {"PX290", "PX300"}
IN_NETWORK_FACTOR = Decimal("0.92")
CENT = Decimal("0.01")

ACTION_RANK = {"deny": 0, "request_records": 1, "reduce": 2}


def money(x):
    return Decimal(str(x)).quantize(CENT, rounding=ROUND_HALF_UP)


def fmt(d):
    return f"{d:.2f}"


# ---------------------------------------------------------------- definitions

def is_office_visit(line):
    return line["procedure_code"] in OFFICE_VISIT_CODES and line["modifier"] == ""


def is_timed_therapy(line):
    return line["procedure_code"] in TIMED_THERAPY_CODES


_HM = re.compile(r"\b(\d{1,2}):(\d{2})\b")
_HR_MIN = re.compile(r"\b(\d+)\s*(?:hr|hrs|hour|hours)\s*(?:and\s*)?(\d+)\s*(?:min|mins|minute|minutes)\b", re.I)
_N_MIN = re.compile(r"\b(\d+)\s*-?\s*(?:min|mins|minute|minutes)\b", re.I)
_MIN_N = re.compile(r"\bminutes?\s*:?\s*(\d+)\b", re.I)
_RANGE = re.compile(r"\b\d+\s*(?:-|to)\s*\d+\s*(?:min|mins|minute|minutes)\b", re.I)
_TIME_WORD = re.compile(r"\b(?:hours?|hrs?|minutes?|mins?)\b", re.I)


def note_minutes(text):
    """Treatment minutes written in a therapy note, or None when the note gives none.

    Returns (minutes, matched_text). Only numbers written as a time (0:28) or next to a
    minutes word count; other numbers in the note (sets, reps, degrees, pounds) do not.
    If the note states two different totals it is ambiguous and returns None.
    """
    rng = _RANGE.search(text)
    if rng:  # "30-35 min" is a range, not one total
        return None, rng.group(0)
    found = []
    for rx, conv in ((_HM, lambda m: int(m[1]) * 60 + int(m[2])),
                     (_HR_MIN, lambda m: int(m[1]) * 60 + int(m[2])),
                     (_N_MIN, lambda m: int(m[1])),
                     (_MIN_N, lambda m: int(m[1]))):
        for m in rx.finditer(text):
            found.append((conv(m), m.group(0)))
        if found:
            break
    if not found and _TIME_WORD.search(text):  # e.g. "one hour": time stated without a number we can read
        return None, _TIME_WORD.search(text).group(0)
    values = {v for v, _ in found}
    if len(values) != 1:
        return None, (" / ".join(t for _, t in found) if found else "")
    return found[0]


def units_supported(minutes):
    """Rule 4: one unit per full 15 minutes; leftover counts as a unit only at 12 or more."""
    full, rest = divmod(minutes, 15)
    return full + (1 if rest >= 12 else 0)


# ---------------------------------------------------------------- the review

class Review:
    def __init__(self, lines, notes, ref):
        self.lines = lines
        self.ref = ref
        self.notes = {}
        self._dup_notes = defaultdict(list)
        for n in notes:
            key = (n["claim_number"], n["rendering_npi"], n["date_of_service"], n["procedure_code"])
            if key in self.notes:
                self._dup_notes[key].append(n["note_id"])
            else:
                self.notes[key] = n
        self.questions = []      # rule 12: questions the rules do not answer
        self.findings = defaultdict(list)   # line_id -> [finding]
        self.calc = {}           # line_id -> allowed amount calculation

    # -- helpers -------------------------------------------------------------
    def question(self, line_ids, text):
        self.questions.append({"line_ids": list(line_ids), "question": text})

    def flag(self, line, rule, action, reason, evidence):
        self.findings[line["line_id"]].append(
            {"rule": rule, "action": action, "reason": reason, "evidence": evidence})

    def network(self, line):
        """Rule 6 / definitions: (in_network, evidence text) from the provider file."""
        p = self.ref.provider_by_tin.get(line["billing_tin"])
        if p is None:
            return None, f"billing tax ID {line['billing_tin']} not in providers.csv"
        since = p["network_since"]
        inn = p["network_status"] == "in_network" and since != "" and line["date_of_service"] >= since
        ev = (f"providers.csv {p['billing_provider']} TIN {p['billing_tin']}: {p['network_status']}"
              + (f" since {since}" if since else ""))
        if p["network_status"] == "in_network" and not inn:
            ev += f" (DOS {line['date_of_service']} is before network_since, so out of network)"
        return inn, ev

    def compute_allowed(self, line):
        """Allowed amount per the definitions: provider's rate x units (note-supported when
        fewer), never more than the billed charge. Returns a dict, or None if not computable."""
        fee = self.ref.fees.get((line["procedure_code"], line["modifier"]))
        billed = money(line["billed_charge"])
        units = int(line["units"])
        inn, net_ev = self.network(line)
        if fee is None or inn is None:
            return None
        factor = IN_NETWORK_FACTOR if inn else Decimal("1")
        unit_rate = money(Decimal(fee["fee_schedule_amount"]) * factor)
        units_paid = units
        note_ev = None
        if is_timed_therapy(line):
            key = (line["claim_number"], line["rendering_npi"], line["date_of_service"], line["procedure_code"])
            note = self.notes.get(key)
            if note is None:
                self.question([line["line_id"]], "No treatment note matches this timed therapy line (claim, "
                              "rendering NPI, date of service, procedure code). TASK.md says every timed line has "
                              "one; rule 4 was not applied and the line is not flagged for it (rule 9: missing "
                              "documentation is not checked). Reviewer: confirm the note file is complete.")
            elif key in self._dup_notes:
                note = None
                self.question([line["line_id"]], f"More than one note matches this timed therapy line "
                              f"({', '.join([self.notes[key]['note_id']] + self._dup_notes[key])}); rule 4 was "
                              "not applied. Reviewer: decide which note governs.")
            if note is not None:
                minutes, said = note_minutes(note["note"])
                if minutes is None and said:
                    self.question([line["line_id"]], f"Note {note['note_id']} does not state one clear time "
                                  f"({said}); rule 4 needs one treatment-minutes figure, so it was not applied. "
                                  "Reviewer: read the note and decide the minutes.")
                if minutes is not None:
                    sup = units_supported(minutes)
                    note_ev = {"note": note, "minutes": minutes, "said": said, "supported": sup}
                    units_paid = min(units, sup)
        rate_total = unit_rate * units_paid
        allowed = min(billed, rate_total)
        mod = f" {line['modifier']}" if line["modifier"] else ""
        fee_ev = (f"fee-schedule.csv {line['procedure_code']}{mod} {fee['fee_schedule_amount']} per {fee['per']}"
                  f" x {'92%' if inn else '100%'} = {fmt(unit_rate)}/unit")
        return {"billed": billed, "units": units, "units_paid": units_paid, "unit_rate": unit_rate,
                "rate_total": rate_total, "allowed": allowed, "in_network": inn,
                "network_ev": net_ev, "fee_ev": fee_ev, "note_ev": note_ev}

    def allowed_text(self, c):
        t = f"allowed {c['units_paid']} x {fmt(c['unit_rate'])} = {fmt(c['rate_total'])}"
        if c["rate_total"] > c["billed"]:
            t += f", capped at billed {fmt(c['billed'])}"
        return t

    # -- run -----------------------------------------------------------------
    def check_provider_file(self):
        rows = defaultdict(set)
        for p in self.ref.providers:
            rows[p["billing_tin"]].add((p["network_status"], p["network_since"]))
        used = {l["billing_tin"] for l in self.lines}
        for tin, vals in rows.items():
            if tin not in used:
                continue
            ids = [l["line_id"] for l in self.lines if l["billing_tin"] == tin]
            if len(vals) > 1:
                self.question(ids, f"providers.csv rows for tax ID {tin} disagree on network status/date "
                              f"({sorted(vals)}); the first row was used. Reviewer: confirm network status.")
            for status, since in vals:
                if status == "in_network" and not since:
                    self.question(ids, f"providers.csv says tax ID {tin} is in_network but gives no "
                                  "network_since date. The definition needs the date of service to be on or after "
                                  "network_since, so these lines were priced at 100% (out of network), which can "
                                  "only understate a reduction. Reviewer: confirm the network start date.")

    def run(self):
        self.check_provider_file()
        for line in self.lines:
            c = self.compute_allowed(line)
            self.calc[line["line_id"]] = c
            if c is None:
                fee = self.ref.fees.get((line["procedure_code"], line["modifier"]))
                why = ("no fee-schedule entry for " + line["procedure_code"] + " " + line["modifier"]).strip() \
                    if fee is None else f"billing tax ID {line['billing_tin']} is not in providers.csv"
                self.question([line["line_id"]], f"Cannot compute the allowed amount: {why}. "
                              "Not flagged on this alone; the reviewer should price it by hand.")
        belongs = self.rule1_claimant()
        self.rule2_before_injury(belongs)
        self.rule3_duplicate_office_visits(belongs)
        self.rule4_6_reduce()
        self.rule5_body_part(belongs)
        self.rule7_tens(belongs)
        self.rule8_therapy_authorizations(belongs)
        return self.verdicts()

    def rule1_claimant(self):
        belongs = {}
        by_bill = defaultdict(set)
        for line in self.lines:
            by_bill[line["bill_id"]].add((line["claim_number"], line["claimant_dob"]))
        for bill, keys in by_bill.items():
            if len(keys) > 1:
                self.question([l["line_id"] for l in self.lines if l["bill_id"] == bill],
                              f"Bill {bill} carries different claim numbers or dates of birth on its lines "
                              f"({sorted(keys)}). Rule 1 was applied line by line; reviewer should confirm.")
        for line in self.lines:
            claim = self.ref.claims.get(line["claim_number"])
            if claim is None:
                belongs[line["line_id"]] = False
                self.question([line["line_id"]], f"Claim number {line['claim_number']} is not in claims.csv. "
                              "Rules 1-8 need the claim record; not flagged on this alone. Route to the "
                              "adjuster/intake to identify the claim.")
                continue
            if line["claimant_dob"] != claim["claimant_dob"]:
                belongs[line["line_id"]] = False
                # context for the reviewer only (names never decide rule 1): whose DOB is on the bill?
                others = [c for c in self.ref.claims.values() if c["claimant_dob"] == line["claimant_dob"]]
                if others:
                    ctx = "; bill DOB matches " + ", ".join(
                        f"claims.csv {c['claim_number']} ({c['claimant_name']}, DOB {c['claimant_dob']})"
                        for c in others)
                else:
                    ctx = "; bill DOB matches no claimant on file"
                if line["source"] == "paper":
                    ctx += "; DOB read from the scan: confirm on the page image"
                self.flag(line, 1, "deny",
                          "Bill belongs to someone else: claim number matches but date of birth does not (rule 1)",
                          f"{line['source_ref']}: claim {line['claim_number']}, DOB on bill {line['claimant_dob']}"
                          f" (name on bill: {line['claimant_name']}); claims.csv {line['claim_number']}:"
                          f" {claim['claimant_name']} DOB {claim['claimant_dob']}{ctx}")
            else:
                belongs[line["line_id"]] = True
        return belongs

    def rule2_before_injury(self, belongs):
        for line in self.lines:
            if not belongs.get(line["line_id"]):
                continue
            doi = self.ref.claims[line["claim_number"]]["date_of_injury"]
            if line["date_of_service"] < doi:
                self.flag(line, 2, "deny", "Date of service is before the date of injury (rule 2)",
                          f"{line['source_ref']}: DOS {line['date_of_service']}; claims.csv "
                          f"{line['claim_number']} date_of_injury {doi}")

    def rule3_duplicate_office_visits(self, belongs):
        groups = defaultdict(list)
        for line in self.lines:
            if belongs.get(line["line_id"]) and is_office_visit(line):
                groups[(line["claim_number"], line["date_of_service"], line["billing_tin"])].append(line)
        for (claim, dos, tin), group in groups.items():
            if len(group) < 2:
                continue
            if any(not l.get("received_date") for l in group):
                self.question([l["line_id"] for l in group],
                              f"Same-day office visits (claim {claim}, {dos}, TIN {tin}) but a received date could "
                              "not be read, so rule 3 cannot tell which was received later. Not flagged; "
                              "reviewer: read the mailroom stamp and deny the later one.")
                continue
            group.sort(key=lambda l: (l["received_date"], l["line_id"]))
            first = group[0]
            for dup in group[1:]:
                self.flag(dup, 3, "deny",
                          "Duplicate office visit: second office visit for this claimant on the same day under "
                          "the same billing tax ID (rule 3)",
                          f"{dup['source_ref']}: {dup['procedure_code']} DOS {dos} TIN {tin} NPI "
                          f"{dup['rendering_npi']} received {dup['received_date']}; earlier visit "
                          f"{first['line_id']} ({first['procedure_code']} NPI {first['rendering_npi']} "
                          f"received {first['received_date']}) is the one paid")

    def rule4_6_reduce(self):
        for line in self.lines:
            c = self.calc.get(line["line_id"])
            if c is None or c["allowed"] >= c["billed"]:
                continue
            parts, reasons, rules = [], [], []
            n = c["note_ev"]
            if n and c["units_paid"] < c["units"]:
                rules.append("4")
                reasons.append(f"therapy units billed ({c['units']}) exceed units the note supports "
                               f"({n['supported']}) (rule 4)")
                parts.append(f"note {n['note']['note_id']} says \"{n['said']}\" = {n['minutes']} min -> "
                             f"{n['supported']} units")
            if c["billed"] > c["unit_rate"] * c["units"]:
                rules.append("6")
                reasons.append("billed above the provider's rate (rule 6)")
            self.flag(line, "/".join(rules), "reduce",
                      "Reduce to allowed amount: " + "; ".join(reasons),
                      "; ".join([f"{line['source_ref']}: {line['procedure_code']}"
                                 f"{(' ' + line['modifier']) if line['modifier'] else ''} x{c['units']} billed "
                                 f"{fmt(c['billed'])}"] + parts + [c["fee_ev"], c["network_ev"],
                                                                    self.allowed_text(c)]))

    def rule5_body_part(self, belongs):
        for line in self.lines:
            if not belongs.get(line["line_id"]):
                continue
            claim = self.ref.claims[line["claim_number"]]
            accepted = [b.strip().lower() for b in claim["accepted_body_parts"].split(";") if b.strip()]
            bp = (line.get("body_part") or "").strip().lower()
            if not bp:
                self.question([line["line_id"]], "No body part for this line's diagnosis code, so rule 5 "
                              "could not be checked.")
                continue
            if bp not in accepted:
                self.flag(line, 5, "request_records",
                          "Body part is not on the claim's accepted list; adjuster decides compensability (rule 5)",
                          f"{line['source_ref']}: dx {line['diagnosis_code']} body part {line['body_part']}"
                          f"{line.get('body_part_ev', '')}; claims.csv {line['claim_number']} accepted_body_parts "
                          f"\"{claim['accepted_body_parts']}\" (updated {claim['body_parts_updated']})")

    def rule7_tens(self, belongs):
        rentals = defaultdict(list)
        for r in self.ref.rentals:
            if r["procedure_code"] == "E0730":
                rentals[r["claim_number"]].append(r)
        for line in self.lines:
            if not belongs.get(line["line_id"]) or line["procedure_code"] != "E0730":
                continue
            rs = rentals.get(line["claim_number"])
            if not rs:
                continue   # rule 7 does not apply to a claim with no TENS rental
            paid = sum(int(r["rental_months_paid"]) for r in rs)
            ev = "; ".join(f"rental-history.csv {r['claim_number']} {r['billing_provider']} E0730 RR "
                           f"{r['rental_months_paid']} paid months through {r['paid_through']}" for r in rs)
            if line["modifier"] == "NU" and paid < 10:
                self.flag(line, 7, "deny",
                          f"TENS purchase while the rental has only {paid} of 10 paid months; rental continues (rule 7)",
                          f"{line['source_ref']}: E0730 NU billed {line['billed_charge']}; {ev}")
            elif line["modifier"] == "RR" and paid >= 10:
                self.question([line["line_id"]],
                              f"TENS rental billed after {paid} paid rental months ({ev}). Rule 7 says the unit "
                              "then belongs to the claimant but does not say what to do with the rental line; "
                              "not flagged. Recommend the reviewer hold it and confirm with the adjuster.")
            elif line["modifier"] == "NU" and paid >= 10:
                self.question([line["line_id"]],
                              f"TENS purchase after {paid} paid rental months ({ev}). Rule 7 only covers purchase "
                              "before 10 months; not flagged.")

    def rule8_outcomes(self, lines, auths, ordinal=True):
        """Rule 8 for the given timed therapy lines: {line_id: (action, visit, approved, past_rank, info)}.

        A visit is past the approved number when its number is higher than the total approved visits of
        the authorizations whose dates include it. With ordinal=True (the written rule) the first 2 such
        visits in date order get request_records and every later one is denied; ordinal=False is the
        alternative reading (visit number minus approved total) kept only to detect where they differ.
        """
        visits = defaultdict(lambda: defaultdict(list))  # (claim, tin) -> dos -> [timed lines]
        for line in lines:
            visits[(line["claim_number"], line["billing_tin"])][line["date_of_service"]].append(line)
        out = {}
        for (claim, tin), by_day in visits.items():
            past_seen = 0
            for number, dos in enumerate(sorted(by_day), start=1):
                covering = [a for a in auths.get((claim, tin), []) if a["start_date"] <= dos <= a["end_date"]]
                if not covering:
                    for l in by_day[dos]:
                        out[l["line_id"]] = ("no_auth", number, None, None, (claim, tin, dos, by_day, covering))
                    continue
                approved = sum(int(a["approved_visits"]) for a in covering if a["approved_visits"].strip())
                if number <= approved:
                    continue
                past_seen += 1
                rank = past_seen if ordinal else number - approved
                action = "request_records" if rank <= 2 else "deny"
                for l in by_day[dos]:
                    out[l["line_id"]] = (action, number, approved, rank, (claim, tin, dos, by_day, covering))
        return out

    def rule8_therapy_authorizations(self, belongs):
        auths = defaultdict(list)
        for a in self.ref.authorizations:
            if a["service_category"].strip().lower() == "physical therapy":
                auths[(a["claim_number"], a["billing_tin"])].append(a)
                if not a["approved_visits"].strip().isdigit():
                    self.question([], f"Therapy authorization {a['auth_id']} ({a['claim_number']}, TIN "
                                  f"{a['billing_tin']}) has no usable approved_visits value "
                                  f"({a['approved_visits']!r}); it was counted as 0 approved visits. Reviewer: "
                                  "confirm with utilization review before acting on rule 8 lines for this claim.")
        timed = [l for l in self.lines if is_timed_therapy(l)]
        # Visits are the claimant's own: a bill that belongs to someone else under rule 1 is not counted.
        own = [l for l in timed if belongs.get(l["line_id"])]
        result = self.rule8_outcomes(own, auths)

        # Readings task.md does not settle: report every line where they would change the verdict.
        alt_rank = self.rule8_outcomes(own, auths, ordinal=False)
        alt_rule1 = self.rule8_outcomes([l for l in timed if l["claim_number"] in self.ref.claims], auths)
        for alt, text in (
                (alt_rank, "Rule 8 reading: the tool counts visits past the approval in date order (the first 2 "
                           "past visits get request_records, later past visits are denied). If instead each "
                           "visit's number minus its approved total decided it, these lines would get: {}. This "
                           "only differs when the covering approvals change during the month."),
                (alt_rule1, "Rule 8 reading: the tool does not count therapy lines on a bill that rule 1 says "
                            "belongs to someone else when numbering this claimant's visits. If those lines "
                            "were counted, these lines would get: {}.")):
            diff = {lid: alt.get(lid, ("not flagged",))[0] for lid in set(result) | set(alt)
                    if belongs.get(lid) and result.get(lid, ("not flagged",))[0] != alt.get(lid, ("not flagged",))[0]}
            if diff:
                self.question(sorted(diff), text.format(", ".join(f"{k} {v}" for k, v in sorted(diff.items()))))

        for line in own:
            r = result.get(line["line_id"])
            if r is None:
                continue
            action, number, approved, rank, (claim, tin, dos, by_day, covering) = r
            if action == "no_auth":
                self.question([line["line_id"]], f"Therapy visit on {dos} (claim {claim}, TIN {tin}) has no "
                              "physical therapy authorization covering its date. TASK.md says this should not "
                              "happen; not flagged. Reviewer should check the authorization log.")
                continue
            auth_ev = "; ".join(f"{a['auth_id']} {a['approved_visits']} visits {a['start_date']} to "
                                f"{a['end_date']}" for a in covering)
            nth = {1: "1st", 2: "2nd", 3: "3rd"}.get(rank, f"{rank}th")
            self.flag(line, 8, action,
                      f"Therapy visit {number} is past the {approved} approved visits; it is the {nth} visit past "
                      f"the approval ({'first 2 past: request records' if action == 'request_records' else 'after the first 2 past: deny'}) (rule 8)",
                      f"{line['source_ref']}: {line['procedure_code']} DOS {dos}, TIN {tin}; visit "
                      f"{number} of claim {claim} at this TIN (visit dates: "
                      f"{', '.join(sorted(by_day))}); authorizations.csv {auth_ev} = {approved} approved")

    # -- combine (rules 10, 11) ----------------------------------------------
    def verdicts(self):
        out = []
        for line in self.lines:
            fs = self.findings.get(line["line_id"], [])
            c = self.calc.get(line["line_id"])
            if not fs:
                out.append({"line": line, "flagged": False, "calc": c})
                continue
            fs = sorted(fs, key=lambda f: ACTION_RANK[f["action"]])
            action = fs[0]["action"]
            chosen = [f for f in fs if f["action"] == action]
            if c is None:
                # rule 11 needs the allowed amount; never substitute the billed charge
                dollars = Decimal("0.00")
                self.question([line["line_id"]], f"Line is flagged {action} but its allowed amount cannot be "
                              "computed (see the pricing question for this line), so dollars at issue are shown "
                              "as 0.00 rather than guessed. Reviewer: price the line and edit the dollars.")
            elif action == "reduce":
                dollars = c["billed"] - c["allowed"]
            else:
                dollars = c["allowed"]
            other = [f for f in fs if f["action"] != action]
            evidence = " | ".join(f["evidence"] for f in chosen)
            if action != "reduce" and c is not None:
                evidence += (f" | dollars at issue = allowed amount: {c['fee_ev']}; {c['network_ev']}; "
                             + self.allowed_text(c))
                if c["note_ev"] and c["units_paid"] < c["units"]:
                    n = c["note_ev"]
                    evidence += (f" (note {n['note']['note_id']} \"{n['said']}\" supports {n['supported']} "
                                 f"of {c['units']} units)")
            out.append({"line": line, "flagged": True, "action": action, "dollars": dollars,
                        "reason": " + ".join(f["reason"] for f in chosen), "evidence": evidence,
                        "rules": [f["rule"] for f in chosen], "also": other, "calc": c})
        return out
