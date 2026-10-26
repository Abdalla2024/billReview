"""Local review page for the bill review supervisor.

    python -m billreview.review_server out/2026-09 [--port 8765]

Serves on 127.0.0.1 only. The supervisor inspects the evidence for each flagged line,
accepts, edits or rejects it, and approves the list. Each approval writes two new files into
<out>/approvals/ (approved-lines-<time>.csv and approval-log-<time>.json) and nothing else: no payment,
denial or change is sent to any other system.
"""
import argparse
import csv
import json
import re
from datetime import datetime, timezone
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

STATIC = Path(__file__).parent / "static" / "review.html"
ACTIONS = {"deny", "reduce", "request_records"}


def sig(item):
    """What a decision was made against; a re-run that changes it invalidates the decision."""
    return f"{item['action']}|{item['dollars_at_issue']}|{item['reason']}"
DECISIONS = {"accept", "edit", "reject"}


def make_handler(out_dir):
    out_dir = Path(out_dir).resolve()
    data = json.loads((out_dir / "review-data.json").read_text())
    items = {i["line_id"]: i for i in data["items"]}
    draft_path = out_dir / "review-draft.json"

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def send(self, code, body, ctype="application/json"):
            if isinstance(body, (dict, list)):
                body = json.dumps(body).encode()
            elif isinstance(body, str):
                body = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = self.path.split("?")[0]
            if path in ("/", "/index.html"):
                return self.send(200, STATIC.read_bytes(), "text/html; charset=utf-8")
            if path == "/review-data.json":
                return self.send(200, data)
            if path == "/api/draft":
                return self.send(200, json.loads(draft_path.read_text()) if draft_path.exists() else {})
            m = re.fullmatch(r"/evidence/(page-\d{2}\.png)", path)
            if m and (out_dir / "evidence" / m.group(1)).exists():
                return self.send(200, (out_dir / "evidence" / m.group(1)).read_bytes(), "image/png")
            self.send(404, {"error": "not found"})

        def body(self):
            n = int(self.headers.get("Content-Length", 0))
            return json.loads(self.rfile.read(n) or b"{}")

        def do_POST(self):
            if self.path == "/api/draft":
                draft_path.write_text(json.dumps(self.body(), indent=1))
                return self.send(200, {"ok": True})
            if self.path == "/api/approve":
                try:
                    return self.send(200, approve(self.body()))
                except ValueError as e:
                    return self.send(400, {"error": str(e)})
            self.send(404, {"error": "not found"})

    def approve(payload):
        reviewer = str(payload.get("reviewer", "")).strip()
        if not reviewer:
            raise ValueError("Enter the reviewer's name before approving.")
        decisions = payload.get("decisions", {})
        missing = [lid for lid in items if lid not in decisions or decisions[lid].get("decision") not in DECISIONS]
        if missing:
            raise ValueError(f"{len(missing)} lines have no decision yet: {', '.join(missing[:5])}")
        rows, log = [], []
        stale = [lid for lid, item in items.items() if decisions[lid].get("rec") not in (None, sig(item))]
        if stale:
            raise ValueError(f"The recommendation changed since these decisions were made; review again: "
                             f"{', '.join(stale[:5])}")
        for lid, item in items.items():
            d = decisions[lid]
            entry = {"line_id": lid, "decision": d["decision"], "note": d.get("note", ""),
                     "recommended": {k: item[k] for k in ("action", "dollars_at_issue", "reason")}}
            if d["decision"] == "reject":
                if not d.get("note", "").strip():
                    raise ValueError(f"{lid}: give a reason for rejecting the recommendation.")
                log.append(entry)
                continue
            action = d.get("action", item["action"]) if d["decision"] == "edit" else item["action"]
            dollars = d.get("dollars_at_issue", item["dollars_at_issue"]) if d["decision"] == "edit" \
                else item["dollars_at_issue"]
            reason = d.get("reason", item["reason"]) if d["decision"] == "edit" else item["reason"]
            if action not in ACTIONS:
                raise ValueError(f"{lid}: action must be deny, reduce or request_records")
            if not re.fullmatch(r"\d+(\.\d{1,2})?", str(dollars)):
                raise ValueError(f"{lid}: dollars must be a number with up to two decimals")
            dollars = f"{Decimal(str(dollars)):.2f}"
            if d["decision"] == "edit" and not d.get("note", "").strip():
                raise ValueError(f"{lid}: give a reason for the edit.")
            entry["approved"] = {"action": action, "dollars_at_issue": dollars, "reason": reason}
            log.append(entry)
            rows.append([lid, reason, dollars, item["evidence"], action])
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        # every approval is kept: earlier approval files are never overwritten
        tag = stamp.replace(":", "").replace("-", "").replace("+0000", "Z")
        approvals = out_dir / "approvals"
        approvals.mkdir(exist_ok=True)
        csv_path, log_path = approvals / f"approved-lines-{tag}.csv", approvals / f"approval-log-{tag}.json"
        if csv_path.exists() or log_path.exists():
            raise ValueError("An approval was saved in this same second; wait a moment and approve again.")
        with open(csv_path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["line_id", "reason", "dollars_at_issue", "evidence", "action"])
            w.writerows(rows)
        total = sum((Decimal(r[2]) for r in rows), Decimal("0"))
        log_path.write_text(json.dumps({
            "approved_by": reviewer, "approved_at": stamp, "month": data["month"],
            "approved_lines": len(rows), "rejected_lines": len(items) - len(rows),
            "approved_total_dollars_at_issue": f"{total:.2f}",
            "tool_total_dollars_at_issue": data["total"],
            "label": "suspected overpayments pending human review; recommendations only, nothing sent to any system",
            "decisions": log}, indent=1))
        return {"ok": True, "approved_lines": len(rows), "total": f"{total:.2f}", "approved_at": stamp,
                "files": [f"approvals/{csv_path.name}", f"approvals/{log_path.name}"]}

    return Handler


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir")
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(a.out_dir))
    print(f"Review page: http://127.0.0.1:{a.port}/  (local only; Ctrl+C to stop)")
    server.serve_forever()


if __name__ == "__main__":
    main()
