# RC-05 Medical bill review before payment (practice set)

SYNTHETIC DATA. Every insurer, provider, claimant, claim, bill, code and amount is fictional. Office, therapy, imaging, injection and surgery codes (PX...) are an in-house code set, not CPT. Equipment lines use HCPCS-style codes: E0730 (TENS unit), L1832 (knee brace), L3807 (wrist brace); modifier NU means bought new and RR means rented for a month.

## Scenario
The bill review team of a workers' compensation insurer checks one month of provider bills on 30 open claims before anything is paid: about 200 bill lines, most received electronically and some on paper. A line that is paid when it should not be is money the insurer rarely gets back; a line held up without a good reason costs provider calls and appeals.

## Input
- `data/2026-09/bills.csv`: this month's electronic bill lines (CMS-1500 and UB-04 style). Every line has a `line_id`.
- `data/2026-09/paper-bills.pdf`: the bills from providers that still mail paper forms, scanned, one bill per page (CMS-1500 style). These lines are not in bills.csv. The mailroom stamps each page with its bill id and received date. A paper line's `line_id` is the bill id, a dash and its two-digit line number on the form (for example HB2609149-03). The form gives the diagnosis code but no body part: use the body part bills.csv gives for the same diagnosis code (every diagnosis code on a paper bill also appears in bills.csv).
- `data/2026-09/treatment-notes.csv`: one note for each timed therapy line; a note matches its line by claim number, rendering NPI, date of service and procedure code. The treatment minutes are written in the note text, the way therapists write them.
- `data/reference/fee-schedule.csv`: the fee schedule, keyed by procedure code and modifier. The `per` column says what one unit is.
- `data/reference/providers.csv`: the provider file: each billing provider's network status and the date it joined the network (`network_since`). Every row of one billing tax ID has the same status.
- `data/reference/claims.csv`: the claim file: claimant, date of birth, date of injury, accepted body parts, and the date that list last changed (`body_parts_updated`).
- `data/reference/authorizations.csv`: the authorization records. Therapy authorizations are the rows with `service_category` physical therapy; they carry the approved visits.
- `data/reference/rental-history.csv`: equipment rental months already paid before this month.

## Build
A tool that reviews all of the month's lines, electronic and paper, and finds the ones that should not be paid as billed.

## Required output
1. `flagged-lines.csv`, one row per flagged line (a line you leave out counts as not flagged), with exactly these columns: `line_id`, `reason`, `dollars_at_issue` (two decimals), `evidence` (the records that prove it: line ids, claim number, note, authorization or fee-schedule entries and the values compared), `action` (`deny`, `reduce` or `request_records`).
2. `review-summary.md`, with the total dollars at issue for the month at the very top, then the dollars for each action, then a short explanation per flagged line or group of lines.

## Words used in the rules
- **Office visit**: a line with procedure code PX330, PX340, PX350, PX360, PX370 or PX380 and no modifier. A telehealth line (modifier TLV) is not an office visit.
- **Timed therapy line**: a line with PX270, PX280 or PX320 (billed per 15 minutes). **Therapy evaluation**: PX290 or PX300.
- **Therapy visit**: one date of service with at least one timed therapy line for the same claim and billing tax ID. Two lines on the same day are one visit.
- **In network**: the provider file says `in_network` and the date of service is on or after `network_since`. Otherwise the provider is out of network for that line.
- **Provider's rate**: the fee schedule amount for the line's code and modifier, at 92 percent when the provider is in network and 100 percent when it is not, rounded to the cent per unit, then times the units.
- **Allowed amount**: what the line would be paid: the provider's rate for the units billed, or for the units the note supports when that is fewer (rule 4), but never more than the billed charge.

## Rules
These are the insurer's own review rules. Apply them as written; general industry practice does not apply.
1. Match a bill to a claimant by claim number and date of birth. The claimant name on the bill does not count, because names are keyed by hand. If the claim number matches but the date of birth does not, the bill belongs to someone else: deny it.
2. Any line whose date of service is before the claim's date of injury is not part of the claim: deny it.
3. One office visit per claimant per day per billing tax ID is paid. A second office visit on the same day under the same billing tax ID is a duplicate even when a different doctor in that group signed it; deny the one received later (by `received_date`; on the same day, the higher `line_id`). Rule 3 compares only office visits that belong to the claimant under rule 1. The earlier visit counts for this rule even if another rule stops or reduces it. Two visits on the same day under different tax IDs are not duplicates.
4. Therapy units: from the minutes in the note, allow one unit for each full 15 minutes; the leftover minutes count as one more unit only when they are 12 or more. When a line bills more units than the note supports, reduce it to the allowed amount. If the note gives no minutes, rule 4 does not apply to that line.
5. Accepted body parts come from the claim file: use the current list for every date of service. Never deny a line because its body part is not accepted; give it `request_records` (the adjuster decides compensability).
6. Network status comes from the provider file. Anything billed above the provider's rate is reduced to it.
7. TENS units (E0730) are rental only for the first 10 months; after 10 paid rental months the unit belongs to the claimant. Paid months are in `rental-history.csv`. A TENS purchase line (modifier NU) on a claim whose TENS rental has fewer than 10 paid months is denied, and the rental keeps being paid. Rule 7 does not apply to a claim with no TENS rental. No rental in this month has reached 10 paid months.
8. Therapy authorizations: an authorization covers the therapy visits for its claim and billing tax ID with a date of service from its `start_date` to its `end_date`. Number the visits for each claim and billing tax ID 1, 2, 3 and so on in date-of-service order; a visit keeps its number even if another rule stops one of its lines. When a claim has two or more therapy authorizations for the same billing tax ID, their approved visits add up: a visit is past the approved number when its number is higher than the total approved visits of the authorizations whose dates include that visit. The `approved_date` does not change the count. The evaluation is not a visit and does not use up an approved visit. No therapy visit under these authorizations was billed before this month, so this month's lines, electronic and paper, hold every visit to count. Every timed therapy line falls inside one of its claim's therapy authorizations for that billing tax ID. Every timed therapy line of the first 2 visits past the approved number gets `request_records`; every timed therapy line of every later visit is denied.
9. Do not deny or hold a line because the bill arrived late. This review does not check bundling, whether modifiers are correct, or missing documentation.
10. When a line breaks more than one rule, deny comes first, then request records; a reduce applies only when nothing stops the line.
11. Dollars at issue: for a deny or request records, the line's allowed amount (what would otherwise have been paid), not the billed charge; for a reduce, the billed charge minus the allowed amount.
12. Every line gets a verdict: flagged with one action, or not flagged. When a line raises a question these rules do not answer, do not flag it on that question alone; write the question and how you would handle it in the summary.
13. The tool only reads and recommends. It never pays, denies or changes anything in another system. A bill review supervisor approves the list before anything happens.

## How it is scored
On Thursday 10/29 you get a holdout month you have not seen, with its own TASK.md (the same text with its own month folder): different claims, claimants, providers, dates and amounts, the same kinds of problems and traps, and the same file layout. You run your tool on it live. Build the tool so you can point it at a new data folder; doing that is not a hand edit, but changing the output by hand is. The `flagged-lines.csv` your tool produces, before any person edits it, is scored against a hidden answer key:
- **Dollars caught**: for each answer-key line you flag with the same action, the key's dollars at issue, or your amount if it is lower. The share is dollars caught divided by the key's total.
- **Precision**: lines you flag with the key's action, divided by all lines you flag.
- **Traps**: lines that look wrong but are correct under these rules. Flagging one, with any action, rules out a 5.

| Score | What it takes |
|---|---|
| 5 | At least 90 percent of the dollars, precision at least 90 percent, and no trap flagged |
| 4 | At least 80 percent of the dollars and precision at least 80 percent |
| 3 | At least 70 percent of the dollars and precision at least 65 percent |
| 2 | Below that |
| 1 | The tool does not run on the holdout month |

This score is the accuracy part (25 points) of the Demo Brief's judging table: points = score / 5 x 25.
