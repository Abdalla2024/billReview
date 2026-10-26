# RC-05: questions to bring to the October 29 rehearsal

These are the places where task.md does not settle what the tool should do. For each one, the tool applies the
handling below every time. When a different reading would change a verdict, it lists the affected lines under
"Questions the rules do not answer" in `review-summary.md` and on the review page. None of these situations
occurs in the 2026-09 practice month; each was checked only with synthetic edge cases built from practice records.

| # | Question | Current handling (conservative) |
|---|---|---|
| 1 | **Rule 8, approvals that change during the month.** "The first 2 visits past the approved number": are these the first two past visits in date order, or visits whose number minus the approved total is 1 or 2? The two readings differ only when the covering authorizations change mid-month (for example, an approval ends and a new one starts). | Date order, which is the literal text. Lines where the other reading would differ are raised as a question. |
| 2 | **Rule 8 and rule 1.** Does a therapy line on a bill that belongs to someone else (rule 1) count when numbering the claimant's visits? Rule 3 says it does not count for office visits; rule 8 says a visit "keeps its number even if another rule stops one of its lines". | Not counted, because rule 1 says it is not this claimant's bill. Lines where counting it would change the action are raised as a question. |
| 3 | **Rounding of the provider's rate.** "Rounded to the cent per unit": half-up, or another mode? | Half-up. This only matters when fee × 92% lands on an exact half cent. |
| 4 | **In network with no `network_since` date.** | Priced at 100% (out of network), which can only understate a reduction, and raised as a question. |
| 5 | **TENS after 10 paid months.** Rule 7 says the unit then belongs to the claimant, but not what to do with a further rental or purchase line. | Not flagged; raised as a question for the adjuster. |
| 6 | **Rule 11 when no fee-schedule entry exists** for a line that is denied or gets request_records. | Flagged with 0.00 dollars at issue and a question; the billed charge is never substituted. |
| 7 | **Body-part wording.** Must the body part match the accepted list word for word (for example "lumbar spine" vs "low back")? | Exact match, ignoring case. A paper line gets a body part only when its diagnosis code has a single body part in bills.csv. |
| 8 | **Therapy notes.** What should happen with a missing note, two matching notes, or a note with two different times? | Rule 4 is not applied, the line is not flagged on that alone (rule 9 excludes missing documentation), and a question is raised. |
| 9 | **Unreadable paper fields.** If a scan's bill ID, claim number, DOB, date of service, code, units, charge, NPI or tax ID cannot be read, the line cannot be reviewed. | Listed as not reviewed, with a question; it never gets a guessed value or a made-up line_id. An unreadable received-date stamp only blocks rule 3, which then raises a question. |

## What was verified, and what was not

Verified on the practice month (2026-09) and on synthetic edge cases built from its records:
- every input line gets exactly one verdict
- the output columns and actions match task.md
- each calculation and evidence cite is recomputed from the source files
- the 25 paper lines match the values I checked by eye against the scans
- the review page refuses incomplete or stale approvals and writes only to its output folder

Not verified:
- **The holdout month.** It has not been seen or used. The renamed-month copy only showed that the same input gives the same output from a different folder name.
- **Paper forms laid out differently** from the practice scans (other row heights, rotated or multi-page bills, handwriting). The tool checks the table geometry and reports a mismatch, but it has not seen such a form.
- **Note phrasings not in the practice notes.** Ranges ("30-35 min"), times written as words ("one hour") and clock ranges ("10:30-11:15") raise a question instead of being read. Other phrasings that never appeared in the practice notes may not be read.
- **Precision and dollars caught against an answer key.** No answer key was available; practice results are not an accuracy score.
