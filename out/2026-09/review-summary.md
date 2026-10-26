# Total dollars at issue: $3656.00 (suspected overpayments pending human review)

**Suspected overpayments pending human review (not realized savings).** Bill review month 2026-09: 15 of 218 lines flagged. Nothing has been paid, denied or changed in any system; a bill review supervisor must approve this list before any action.

| Action | Lines | Dollars at issue |
|---|---:|---:|
| deny | 6 | $1474.85 |
| request_records | 3 | $1470.40 |
| reduce | 6 | $710.75 |
| **total** | **15** | **$3656.00** |

Dollars at issue follow rule 11: for deny and request_records, the allowed amount (what would otherwise be paid); for reduce, billed charge minus allowed amount.

## Flagged lines by reason

### deny: rule 1 (1 lines, $380.00)
Rule 1: the claim number matches but the date of birth does not, so the bill belongs to someone else. Names are not used to match. Dollars at issue are what would otherwise be paid (allowed amount).

| line_id | claim | DOS | code | billed | dollars | why |
|---|---|---|---|---:|---:|---|
| HB2609662-01 | WC26-04390 | 2026-09-03 | PX380 | 425.00 | 380.00 | Bill belongs to someone else: claim number matches but date of birth does not (rule 1) [paper: page 8] |

### deny: rule 2 (1 lines, $210.00)
Rule 2: the date of service is before the claim's date of injury, so the line is not part of the claim.

| line_id | claim | DOS | code | billed | dollars | why |
|---|---|---|---|---:|---:|---|
| HB2609198-01 | WC26-04351 | 2026-08-04 | PX110 | 260.00 | 210.00 | Date of service is before the date of injury (rule 2) [paper: page 4] |

### deny: rule 3 (1 lines, $144.85)
Rule 3: a second office visit for the same claimant, day and billing tax ID. The visit received first is kept (by received date, then line id); the later one is denied.

| line_id | claim | DOS | code | billed | dollars | why |
|---|---|---|---|---:|---:|---|
| HB2609823-01 | WC26-04117 | 2026-09-02 | PX360 | 185.00 | 144.85 | Duplicate office visit: second office visit for this claimant on the same day under the same billing tax ID (rule 3) [paper: page 10] |

### deny: rule 7 (1 lines, $420.00)
Rule 7: a TENS purchase on a claim whose TENS rental has fewer than 10 paid months. The purchase is denied and the rental keeps being paid.

| line_id | claim | DOS | code | billed | dollars | why |
|---|---|---|---|---:|---:|---|
| HB2609644-01 | WC26-04466 | 2026-09-04 | E0730 NU | 495.00 | 420.00 | TENS purchase while the rental has only 2 of 10 paid months; rental continues (rule 7) |

### deny: rule 8 (2 lines, $320.00)
Rule 8: therapy visits past the approved number of visits for that claim and billing tax ID. The first 2 visits past the approved number get request_records; later visits are denied. Evaluations are not counted as visits.

| line_id | claim | DOS | code | billed | dollars | why |
|---|---|---|---|---:|---:|---|
| HB2609928-01 | WC26-04618 | 2026-09-20 | PX320 | 190.00 | 160.00 | Therapy visit 15 is past the 12 approved visits; it is the 3rd visit past the approval (after the first 2 past: deny) (rule 8) |
| HB2609981-01 | WC26-04618 | 2026-09-22 | PX320 | 190.00 | 160.00 | Therapy visit 16 is past the 12 approved visits; it is the 4th visit past the approval (after the first 2 past: deny) (rule 8) |

### request_records: rule 5 (1 lines, $1150.40)
Rule 5: the line's body part (from its diagnosis code) is not on the claim's current accepted list. These are never denied for this reason: request records so the adjuster can decide compensability.

| line_id | claim | DOS | code | billed | dollars | why |
|---|---|---|---|---:|---:|---|
| HB2609541-01 | WC26-04351 | 2026-08-29 | PX180 | 1480.00 | 1150.40 | Body part is not on the claim's accepted list; adjuster decides compensability (rule 5) |

### request_records: rule 8 (2 lines, $320.00)
Rule 8: therapy visits past the approved number of visits for that claim and billing tax ID. The first 2 visits past the approved number get request_records; later visits are denied. Evaluations are not counted as visits.

| line_id | claim | DOS | code | billed | dollars | why |
|---|---|---|---|---:|---:|---|
| HB2609958-01 | WC26-04618 | 2026-09-18 | PX320 | 190.00 | 160.00 | Therapy visit 14 is past the 12 approved visits; it is the 2nd visit past the approval (first 2 past: request records) (rule 8) |
| HB2609969-01 | WC26-04618 | 2026-09-16 | PX320 | 190.00 | 160.00 | Therapy visit 13 is past the 12 approved visits; it is the 1st visit past the approval (first 2 past: request records) (rule 8) |

### Reduce: billed above the provider's rate (rule 6) (5 lines, $614.75)
Reduced to the allowed amount: the fee schedule amount for the code and modifier, at 92% when the billing tax ID is in network on the date of service and 100% when not, rounded per unit, times the units billed or the units the therapy note supports when fewer, never more than the billed charge.

| line_id | claim | DOS | code | billed | dollars | why |
|---|---|---|---|---:|---:|---|
| HB2609014-01 | WC26-04117 | 2026-08-21 | PX210 | 410.00 | 160.00 | billed above the provider's rate (rule 6) |
| HB2609214-01 | WC26-04502 | 2026-08-28 | PX260 | 560.00 | 100.00 | billed above the provider's rate (rule 6) |
| HB2609225-02 | WC26-04573 | 2026-08-19 | PX160 | 260.00 | 110.00 | billed above the provider's rate (rule 6) |
| HB2609455-02 | WC26-04502 | 2026-08-03 | PX340 | 310.00 | 104.75 | billed above the provider's rate (rule 6) |
| HB2609922-01 | WC26-04573 | 2026-09-08 | PX130 | 1750.00 | 140.00 | billed above the provider's rate (rule 6) |

### Reduce: therapy units above what the note supports (rule 4) (1 lines, $96.00)
Reduced to the allowed amount: the fee schedule amount for the code and modifier, at 92% when the billing tax ID is in network on the date of service and 100% when not, rounded per unit, times the units billed or the units the therapy note supports when fewer, never more than the billed charge.

| line_id | claim | DOS | code | billed | dollars | why |
|---|---|---|---|---:|---:|---|
| HB2609695-01 | WC26-04208 | 2026-08-26 | PX270 | 192.00 | 96.00 | therapy units billed (4) exceed units the note supports (2) (rule 4) |

## Questions the rules do not answer (rule 12, not flagged on these alone)
- None this month.

## Every line accounted for
- Electronic lines in bills.csv: 193
- Paper lines read from paper-bills.pdf: 25 on 13 pages
- Total reviewed: 218 = 15 flagged + 203 not flagged
- Every line and its verdict is in `all-lines.csv`.
- Evidence self-check: every record and value cited in flagged-lines.csv was re-read from the source files and matches.

## Paper bill extraction (review before approving)
Paper lines were read from the scans by local OCR (Tesseract). Each value was cross-checked: the line charges must add up to the form's total charge (box 28), the claim must exist, the rendering NPI must belong to the billing tax ID in the provider file, and the diagnosis code must appear in bills.csv (which gives the body part). Values and page/row are in `paper-extraction.csv`; the review page shows each page image beside the values read.

All 25 paper lines passed every cross-check.

## Interpretations applied where task.md is silent
Each is applied the same way every run; where a different reading would change a verdict this month, the affected lines are listed under the questions above.
- Provider's rate: the fee times 92% (in network) or 100% is rounded to the cent half-up, per unit, then multiplied by the units. task.md does not name a rounding mode; it only matters at an exact half cent.
- Rule 8: visits past the approved number are counted in date order; the first 2 such visits get request_records and every later one is denied. A question is raised wherever counting by visit number minus approved total would give a different action.
- Rule 8: therapy lines on a bill that rule 1 says belongs to someone else are not counted as the claimant's visits. A question is raised wherever counting them would change another line's action.
- In network needs a network_since date on or before the date of service; an in_network provider with no date is priced at 100% and raised as a question.
- Rule 7: paid rental months come only from rental-history.csv (this month's rental lines are not added). A TENS rental or purchase after 10 paid months is raised as a question, not flagged.
- Rule 5: the line's body part must match an entry of the claim's accepted list exactly (ignoring case). A paper line takes its body part from bills.csv only when that diagnosis code has one body part there.
- Rule 4: a note with no minutes leaves rule 4 out (as written); a note with two different times, a missing note or two matching notes is raised as a question and rule 4 is not applied.
- Rule 11: when a stopped line's allowed amount cannot be computed (no fee entry or unknown tax ID), dollars at issue are 0.00 with a question; the billed charge is never used instead.
- A claim number not in claims.csv, or a line with a missing or unreadable field, is not reviewed or flagged and is listed as a question.
- Rule 3 tie-break on the same received date uses the higher line_id as text (HB2609823-01 > HB2609623-01).
- When rule 4 and rule 6 both reduce a line, it is one reduce to the allowed amount (rate x note-supported units, capped at the billed charge).

## What this tool does not do
It only reads files and recommends. It does not pay, deny, hold or change anything in any system, and it does not contact providers or claimants. Late arrival, bundling, modifier correctness and missing documentation are not checked (rule 9).
