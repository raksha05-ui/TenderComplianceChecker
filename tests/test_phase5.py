"""Phase 5 tests: SQLite history + PDF/Excel reports. Run: python tests/test_phase5.py"""
import io, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules import database
from modules.report_generator import build_excel, build_pdf

R = [
 {"req_id": "R01", "requirement": "Turnover must be >= Rs 5 Cr & audited <b>", "mandatory": True, "req_page": 2,
  "status": "Compliant", "document": "fin.pdf", "evidence_page": 3, "evidence": "Turnover Rs 6 Cr " * 60,
  "evidence_strength": 0.61, "reason": "6 Cr >= 5 Cr"},
 {"req_id": "R02", "requirement": "ISO 9001 certificate required", "mandatory": True, "req_page": 3,
  "status": "Missing Evidence", "document": None, "evidence_page": None, "evidence": "", "evidence_strength": 0,
  "reason": "No candidate passage"},
 {"req_id": "R03", "requirement": "Minimum 5 years experience", "mandatory": False, "req_page": 4,
  "status": "Potentially Non-Compliant", "document": "exp.pdf", "evidence_page": 1, "evidence": "3 years",
  "evidence_strength": 0.4, "reason": "3 < 5"},
 {"req_id": "R04", "requirement": "Valid GST registration", "mandatory": True, "req_page": 4,
  "status": "Needs Manual Review", "document": "gst.pdf", "evidence_page": 1, "evidence": "GSTIN ...",
  "evidence_strength": 0.3, "reason": "ambiguous"},
]
S = {"total": 4, "Compliant": 1, "Potentially Non-Compliant": 1, "Missing Evidence": 1, "Needs Manual Review": 1,
     "compliant_pct": 25.0, "note": "n"}

with tempfile.TemporaryDirectory() as d:
    p = os.path.join(d, "h.db")
    i = database.save_analysis("T1", ["a.pdf"], R, path=p)
    assert database.list_analyses(path=p)[0]["compliant"] == 1
    a = database.load_analysis(i, path=p)
    assert len(a["results"]) == 4 and len(a["results"][0]["evidence"]) == 500
    R[3]["status"] = "Compliant"
    assert database.save_analysis("T1", ["a.pdf"], R, analysis_id=i, path=p) == i
    assert len(database.list_analyses(path=p)) == 1 and database.list_analyses(path=p)[0]["compliant"] == 2
    j = database.save_analysis("T2", [], R, store_excerpts=False, path=p)
    assert all(r["evidence"] == "" for r in database.load_analysis(j, path=p)["results"])
    assert database.load_analysis(999, path=p) is None
    database.delete_analysis(j, path=p); assert len(database.list_analyses(path=p)) == 1
    print("database OK")

pdf = build_pdf("Tender <A&B>", ["fin.pdf"], R, S)
assert pdf[:4] == b"%PDF"
import fitz
txt = "".join(pg.get_text() for pg in fitz.open(stream=pdf, filetype="pdf"))
for needle in ["Tender <A&B>", "R02", "Missing Evidence", "Recommended next steps", "decision support"]:
    assert needle in txt, needle
xl = build_excel(R, S)
import pandas as pd
assert len(pd.read_excel(io.BytesIO(xl), sheet_name="Results")) == 4
assert build_pdf("Empty", [], [], {**S, "total": 0, "Compliant": 0, "Potentially Non-Compliant": 0,
       "Missing Evidence": 0, "Needs Manual Review": 0, "compliant_pct": 0})[:4] == b"%PDF"
print("report OK (pdf %d bytes, xlsx %d bytes)" % (len(pdf), len(xl)))
