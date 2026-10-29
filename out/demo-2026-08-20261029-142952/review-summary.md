# Total dollars at issue: $3140.92 (suspected overpayments pending human review)

**Suspected overpayments pending human review (not realized savings).** Bill review month 2026-08: 15 of 227 lines flagged. Nothing has been paid, denied or changed in any system; a bill review supervisor must approve this list before any action.

| Action | Lines | Dollars at issue |
|---|---:|---:|
| deny | 6 | $1182.05 |
| request_records | 3 | $1319.14 |
| reduce | 6 | $639.73 |
| **total** | **15** | **$3140.92** |

Dollars at issue follow rule 11: for deny and request_records, the allowed amount (what would otherwise be paid); for reduce, billed charge minus allowed amount.

## Flagged lines by reason

### deny: rule 1 (1 lines, $168.40)
Rule 1: the claim number matches but the date of birth does not, so the bill belongs to someone else. Names are not used to match. Dollars at issue are what would otherwise be paid (allowed amount).

| line_id | claim | DOS | code | billed | dollars | why |
|---|---|---|---|---:|---:|---|
| HB2608903-01 | WC26-02989 | 2026-08-10 | PX330 | 190.00 | 168.40 | Bill belongs to someone else: claim number matches but date of birth does not (rule 1) [paper: page 23] |

### deny: rule 2 (1 lines, $144.85)
Rule 2: the date of service is before the claim's date of injury, so the line is not part of the claim.

| line_id | claim | DOS | code | billed | dollars | why |
|---|---|---|---|---:|---:|---|
| HB2608372-01 | WC26-02971 | 2026-07-01 | PX360 | 160.00 | 144.85 | Date of service is before the date of injury (rule 2) |

### deny: rule 3 (1 lines, $194.40)
Rule 3: a second office visit for the same claimant, day and billing tax ID. The visit received first is kept (by received date, then line id); the later one is denied.

| line_id | claim | DOS | code | billed | dollars | why |
|---|---|---|---|---:|---:|---|
| HB2608838-01 | WC26-02917 | 2026-08-06 | PX370 | 240.00 | 194.40 | Duplicate office visit: second office visit for this claimant on the same day under the same billing tax ID (rule 3) [paper: page 21] |

### deny: rule 7 (1 lines, $386.40)
Rule 7: a TENS purchase on a claim whose TENS rental has fewer than 10 paid months. The purchase is denied and the rental keeps being paid.

| line_id | claim | DOS | code | billed | dollars | why |
|---|---|---|---|---:|---:|---|
| HB2608728-01 | WC26-03006 | 2026-08-07 | E0730 NU | 460.00 | 386.40 | TENS purchase while the rental has only 5 of 10 paid months; rental continues (rule 7) |

### deny: rule 8 (2 lines, $288.00)
Rule 8: therapy visits past the approved number of visits for that claim and billing tax ID. The first 2 visits past the approved number get request_records; later visits are denied. Evaluations are not counted as visits.

| line_id | claim | DOS | code | billed | dollars | why |
|---|---|---|---|---:|---:|---|
| HB2608877-01 | WC26-03077 | 2026-08-11 | PX270 | 165.00 | 144.00 | Therapy visit 13 is past the 10 approved visits; it is the 3rd visit past the approval (after the first 2 past: deny) (rule 8) |
| HB2608930-01 | WC26-03077 | 2026-08-14 | PX270 | 165.00 | 144.00 | Therapy visit 14 is past the 10 approved visits; it is the 4th visit past the approval (after the first 2 past: deny) (rule 8) |

### request_records: rule 5 (1 lines, $1031.14)
Rule 5: the line's body part (from its diagnosis code) is not on the claim's current accepted list. These are never denied for this reason: request records so the adjuster can decide compensability.

| line_id | claim | DOS | code | billed | dollars | why |
|---|---|---|---|---:|---:|---|
| HB2608695-01 | WC26-02958 | 2026-07-29 | PX170 | 1150.00 | 1031.14 | Body part is not on the claim's accepted list; adjuster decides compensability (rule 5) |

### request_records: rule 8 (2 lines, $288.00)
Rule 8: therapy visits past the approved number of visits for that claim and billing tax ID. The first 2 visits past the approved number get request_records; later visits are denied. Evaluations are not counted as visits.

| line_id | claim | DOS | code | billed | dollars | why |
|---|---|---|---|---:|---:|---|
| HB2608788-01 | WC26-03077 | 2026-08-08 | PX270 | 165.00 | 144.00 | Therapy visit 12 is past the 10 approved visits; it is the 2nd visit past the approval (first 2 past: request records) (rule 8) |
| HB2608852-01 | WC26-03077 | 2026-08-05 | PX270 | 165.00 | 144.00 | Therapy visit 11 is past the 10 approved visits; it is the 1st visit past the approval (first 2 past: request records) (rule 8) |

### Reduce: billed above the provider's rate (rule 6) (5 lines, $557.85)
Reduced to the allowed amount: the fee schedule amount for the code and modifier, at 92% when the billing tax ID is in network on the date of service and 100% when not, rounded per unit, times the units billed or the units the therapy note supports when fewer, never more than the billed charge.

| line_id | claim | DOS | code | billed | dollars | why |
|---|---|---|---|---:|---:|---|
| HB2608020-01 | WC26-03041 | 2026-06-26 | PX150 | 95.00 | 24.60 | billed above the provider's rate (rule 6) |
| HB2608126-02 | WC26-03024 | 2026-06-16 | PX340 | 255.00 | 49.75 | billed above the provider's rate (rule 6) |
| HB2608276-01 | WC26-03024 | 2026-07-24 | PX260 | 520.00 | 60.00 | billed above the provider's rate (rule 6) [paper: page 5] |
| HB2608602-01 | WC26-02917 | 2026-08-03 | PX250 | 1250.00 | 185.10 | billed above the provider's rate (rule 6) |
| HB2608674-01 | WC26-03059 | 2026-08-05 | PX120 | 2980.00 | 238.40 | billed above the provider's rate (rule 6) [paper: page 18] |

### Reduce: therapy units above what the note supports (rule 4) (1 lines, $81.88)
Reduced to the allowed amount: the fee schedule amount for the code and modifier, at 92% when the billing tax ID is in network on the date of service and 100% when not, rounded per unit, times the units billed or the units the therapy note supports when fewer, never more than the billed charge.

| line_id | claim | DOS | code | billed | dollars | why |
|---|---|---|---|---:|---:|---|
| HB2608635-01 | WC26-02934 | 2026-07-26 | PX280 | 122.82 | 81.88 | therapy units billed (3) exceed units the note supports (1) (rule 4) |

## Questions the rules do not answer (rule 12, not flagged on these alone)
- HB2608432-01: Missing or unreadable billing_tin in paper-bills.pdf page 10 (bill HB2608432 line 01); the line was not reviewed and is not flagged. Read the scan, correct paper-extraction.csv and re-run with --paper-extraction.
- HB2608432-02: Missing or unreadable billing_tin in paper-bills.pdf page 10 (bill HB2608432 line 02); the line was not reviewed and is not flagged. Read the scan, correct paper-extraction.csv and re-run with --paper-extraction.
- HB2608923-05: Missing or unreadable rendering_npi, date_of_service, procedure_code, units, billed_charge in paper-bills.pdf page 25 (bill HB2608923 line 05); the line was not reviewed and is not flagged. Read the scan, correct paper-extraction.csv and re-run with --paper-extraction.

## Every line accounted for
- Electronic lines in bills.csv: 184
- Paper lines read from paper-bills.pdf: 43 on 26 pages
- Total reviewed: 227 = 15 flagged + 212 not flagged (of which 3 could not be reviewed; see questions)
- Every line and its verdict is in `all-lines.csv`.
- Evidence self-check: every record and value cited in flagged-lines.csv was re-read from the source files and matches.

## Paper bill extraction (review before approving)
Paper lines were read from the scans by local OCR (Tesseract). Each value was cross-checked: the line charges must add up to the form's total charge (box 28), the claim must exist, the rendering NPI must belong to the billing tax ID in the provider file, and the diagnosis code must appear in bills.csv (which gives the body part). Values and page/row are in `paper-extraction.csv`; the review page shows each page image beside the values read.

Lines whose extraction did not pass every check (verify against the scan):
- HB2608432-01 (page 10 row 1): could not read billing_tin; NPI 1184593027 is not listed under tax ID  in providers.csv
- HB2608432-02 (page 10 row 2): could not read billing_tin; NPI 1184593027 is not listed under tax ID  in providers.csv
- HB2608923-01 (page 25 row 1): service rows read: [1, 5] (gap: a row may have been missed)
- HB2608923-05 (page 25 row 5): could not read service line; service rows read: [1, 5] (gap: a row may have been missed)

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
