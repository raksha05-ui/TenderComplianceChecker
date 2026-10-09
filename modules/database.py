"""SQLite history of analyses (no API keys, no full document text).

Only requirement text, statuses, reasons and SHORT evidence excerpts are stored.
Set store_excerpts=False to keep even the excerpts out of the database.
"""
import json
import os
import sqlite3
from datetime import datetime

DB_PATH = os.getenv("TENDER_DB_PATH", os.path.join("data", "history.db"))
MAX_EXCERPT = 500

SCHEMA = """
CREATE TABLE IF NOT EXISTS analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tender_name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    mode TEXT NOT NULL,
    vendor_docs TEXT NOT NULL,
    total INTEGER NOT NULL,
    compliant INTEGER NOT NULL,
    non_compliant INTEGER NOT NULL,
    missing INTEGER NOT NULL,
    review INTEGER NOT NULL,
    results_json TEXT NOT NULL
);
"""


def _conn(path=None):
    path = path or DB_PATH
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute(SCHEMA)
    return con


def _counts(results):
    c = {"Compliant": 0, "Potentially Non-Compliant": 0, "Missing Evidence": 0, "Needs Manual Review": 0}
    for r in results:
        if r.get("status") in c:
            c[r["status"]] += 1
    return c


def _prepare(results, store_excerpts):
    out = []
    for r in results:
        r = dict(r)
        ev = r.get("evidence") or ""
        r["evidence"] = ev[:MAX_EXCERPT] if store_excerpts else ""
        out.append(r)
    return out


def save_analysis(tender_name, vendor_doc_names, results, mode="offline",
                  store_excerpts=True, analysis_id=None, path=None):
    """Insert a new analysis, or update it when analysis_id is given. Returns the id."""
    now = datetime.now().isoformat(timespec="seconds")
    c = _counts(results)
    payload = json.dumps(_prepare(results, store_excerpts), default=str)
    con = _conn(path)
    try:
        if analysis_id:
            cur = con.execute(
                "UPDATE analyses SET updated_at=?, total=?, compliant=?, non_compliant=?, missing=?, review=?, "
                "results_json=? WHERE id=?",
                (now, len(results), c["Compliant"], c["Potentially Non-Compliant"], c["Missing Evidence"],
                 c["Needs Manual Review"], payload, analysis_id))
            if cur.rowcount:
                con.commit()
                return analysis_id
        cur = con.execute(
            "INSERT INTO analyses (tender_name, created_at, updated_at, mode, vendor_docs, total, compliant, "
            "non_compliant, missing, review, results_json) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (tender_name, now, now, mode, json.dumps(list(vendor_doc_names)), len(results), c["Compliant"],
             c["Potentially Non-Compliant"], c["Missing Evidence"], c["Needs Manual Review"], payload))
        con.commit()
        return cur.lastrowid
    finally:
        con.close()


def list_analyses(path=None):
    con = _conn(path)
    try:
        rows = con.execute("SELECT id, tender_name, created_at, updated_at, mode, total, compliant, "
                           "non_compliant, missing, review FROM analyses ORDER BY id DESC").fetchall()
    finally:
        con.close()
    return [dict(r) for r in rows]


def load_analysis(analysis_id, path=None):
    con = _conn(path)
    try:
        row = con.execute("SELECT * FROM analyses WHERE id=?", (analysis_id,)).fetchone()
    finally:
        con.close()
    if not row:
        return None
    d = dict(row)
    d["results"] = json.loads(d.pop("results_json"))
    d["vendor_docs"] = json.loads(d["vendor_docs"])
    return d


def delete_analysis(analysis_id, path=None):
    con = _conn(path)
    try:
        con.execute("DELETE FROM analyses WHERE id=?", (analysis_id,))
        con.commit()
    finally:
        con.close()
