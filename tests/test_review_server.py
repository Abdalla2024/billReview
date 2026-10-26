"""The supervisor review step: evidence is served, every line needs a decision, edits and rejects need a
reason, stale decisions are refused, and approval only writes new files in the output folder."""
import json
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from billreview import cli
from billreview.review_server import make_handler, sig

ROOT = Path(__file__).resolve().parents[1]
EXTRACTION = ROOT / "out" / "2026-09" / "paper-extraction.csv"


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    out = tmp_path_factory.mktemp("review")
    cli.run(ROOT / "data", "2026-09", out, EXTRACTION if EXTRACTION.exists() else None)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(out))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", out, httpd
    httpd.shutdown()


def get(base, path):
    with urllib.request.urlopen(base + path) as r:
        return r.status, r.read()


def post(base, path, body):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode(), method="POST")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)


def all_accepted(items):
    return {i["line_id"]: {"decision": "accept", "rec": sig(i)} for i in items}


def test_binds_to_loopback_only(server):
    assert server[2].server_address[0] == "127.0.0.1"


def test_page_data_and_evidence_are_served(server):
    base, out, _ = server
    assert get(base, "/")[0] == 200
    data = json.loads(get(base, "/review-data.json")[1])
    assert data["items"] and all(i["evidence"] and i["cited"] for i in data["items"])
    with pytest.raises(urllib.error.HTTPError):
        get(base, "/evidence/../../flagged-lines.csv")


def test_approval_refusals(server):
    base, out, _ = server
    items = json.loads(get(base, "/review-data.json")[1])["items"]
    d = all_accepted(items)
    first, second = items[0]["line_id"], items[1]["line_id"]
    assert post(base, "/api/approve", {"decisions": d})[0] == 400                                # no reviewer
    assert post(base, "/api/approve", {"reviewer": "T", "decisions": {}})[0] == 400              # undecided
    assert post(base, "/api/approve", {"reviewer": "T", "decisions": {**d, first: {
        "decision": "reject", "note": "", "rec": sig(items[0])}}})[0] == 400                     # reject, no reason
    for bad in ({"action": "pay"}, {"dollars_at_issue": "abc"}, {"note": ""}):
        edit = {"decision": "edit", "note": "checked", "action": "reduce", "dollars_at_issue": "1.00",
                "reason": "r", "rec": sig(items[1]), **bad}
        assert post(base, "/api/approve", {"reviewer": "T", "decisions": {**d, second: edit}})[0] == 400
    stale = {**d, first: {"decision": "accept", "rec": "deny|1.00|old"}}
    code, body = post(base, "/api/approve", {"reviewer": "T", "decisions": stale})
    assert code == 400 and "changed" in body["error"]
    assert not (out / "approvals").exists() or not list((out / "approvals").iterdir())


def test_approval_writes_new_files_and_keeps_earlier_ones(server):
    base, out, _ = server
    items = json.loads(get(base, "/review-data.json")[1])["items"]
    d = all_accepted(items)
    d[items[0]["line_id"]] = {"decision": "reject", "note": "provider corrected", "rec": sig(items[0])}
    d[items[1]["line_id"]] = {"decision": "edit", "note": "re-priced", "action": "reduce",
                              "dollars_at_issue": "12.5", "reason": "edited", "rec": sig(items[1])}
    code, body = post(base, "/api/approve", {"reviewer": "Test Supervisor", "decisions": d})
    assert code == 200 and body["approved_lines"] == len(items) - 1
    time.sleep(1.1)
    code2, body2 = post(base, "/api/approve", {"reviewer": "Test Supervisor", "decisions": d})
    assert code2 == 200 and body2["files"] != body["files"]
    files = sorted(p.name for p in (out / "approvals").iterdir())
    assert len(files) == 4
    log = json.loads((out / body["files"][1]).read_text())
    assert log["approved_by"] == "Test Supervisor" and "pending human review" in log["label"]
    rows = (out / body["files"][0]).read_text().splitlines()
    assert rows[0] == "line_id,reason,dollars_at_issue,evidence,action"
    assert any(r.startswith(f"{items[1]['line_id']},edited,12.50,") for r in rows)
    assert not any(r.startswith(items[0]["line_id"]) for r in rows)
    # nothing outside the output folder's approvals/ and draft file was written
    assert {p.name for p in out.iterdir()} <= {"flagged-lines.csv", "review-summary.md", "all-lines.csv",
                                               "paper-extraction.csv", "review-data.json", "approvals",
                                               "review-draft.json", "evidence"}
