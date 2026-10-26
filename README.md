# billReview — RC-05 pre-payment medical bill review (synthetic data)

Reviews one month of workers' compensation provider bill lines, electronic (`bills.csv`) and scanned
paper (`paper-bills.pdf`), against the insurer's rules in [task.md](task.md). It writes the lines that should
not be paid as billed, each with a reason, dollars at issue, evidence and a recommended action
(`deny`, `reduce`, `request_records`). A bill review supervisor then approves the list on a local review page.

All dollar figures are **suspected overpayments pending human review**, not realized savings.
The tool only reads files and recommends. It never pays, denies or changes anything in another system.

## Setup

```sh
brew install tesseract            # local OCR for the scanned paper bills
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

## Run

```sh
.venv/bin/python -m billreview --data data            # finds the month folder holding bills.csv
.venv/bin/python -m billreview --data /path/to/holdout --out out/holdout
.venv/bin/python -m billreview.review_server out/2026-09   # http://127.0.0.1:8765 (local only)
```

Outputs in `out/<month>/`:

| File | What it is |
|---|---|
| `flagged-lines.csv` | The required output: `line_id, reason, dollars_at_issue, evidence, action` |
| `review-summary.md` | Total at the top, dollars per action, an explanation per group of lines, rule-12 questions, line accounting, extraction checks |
| `all-lines.csv` | Every input line with its verdict (flagged or not), so every line is accounted for |
| `paper-extraction.csv` | Every value read from the scans, with page, row and cross-check results |
| `approvals/approved-lines-<time>.csv`, `approvals/approval-log-<time>.json` | Written only when the supervisor approves on the review page (who, when, each accept/edit/reject with a reason); each approval adds new files and never overwrites earlier ones |

To correct an OCR misread, edit `paper-extraction.csv` and re-run with `--paper-extraction <file>`.

## How it works

- **Paper bills** ([billreview/ocr.py](billreview/ocr.py), [billreview/extract.py](billreview/extract.py)): each page is
  deskewed, its ruled grid is located, and each form cell is read separately with Tesseract and a per-field
  character whitelist. Every value is cross-checked: line charges must add up to the form total (box 28), the
  claim must exist, the NPI must belong to the tax ID in the provider file, and the diagnosis code must appear in
  `bills.csv` (which gives the body part). A line that cannot be read is reported, never guessed.
- **Rules** ([billreview/rules.py](billreview/rules.py)): rules 1–12 as written in task.md, in plain Python with
  `Decimal` money. There is no model in the decision path. Precedence is deny, then request_records, then reduce.
  Dollars follow rule 11.
- **Evidence self-check** ([billreview/verify.py](billreview/verify.py)): after each run, every record cited in
  `flagged-lines.csv` is re-read from the source files, and every figure is recomputed independently of the rules
  engine: unit rate and network %, allowed amount, rule-11 dollars, note ownership and units, visit numbers,
  approved totals, the earlier visit in a duplicate, claim DOB/DOI, body part and rental months.
- **Questions, not guesses** (rule 12): where task.md does not settle a case, the line is not flagged on that
  alone and the question is written in the summary. Standing interpretations are listed at the end of
  `review-summary.md`; open questions for the rehearsal are in [docs/rehearsal-questions.md](docs/rehearsal-questions.md).
- **Review page** ([billreview/review_server.py](billreview/review_server.py)): binds to 127.0.0.1 only. It shows each
  flagged line's evidence, treatment note, source record and, for paper lines, the scanned page with the row
  highlighted. The supervisor accepts, edits or rejects each line (a reason is required to edit or reject), and
  then approves the list.

## Tests

```sh
.venv/bin/python -m pytest -q tests
```

`tests/test_review.py` covers the output contract, line accounting, hand-checked flags and traps on the practice
month, rule-4 arithmetic and note formats, the evidence checker catching fabricated cites, and rule edge cases
built from practice records. `tests/test_ocr.py` re-reads the scans and compares them with values checked by eye
against each page (`tests/fixtures/paper-2026-09-verified.csv`).

Synthetic data only.
