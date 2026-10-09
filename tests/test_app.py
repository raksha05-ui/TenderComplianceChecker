"""Render every page with REAL pipeline results. Run: python tests/test_app.py"""
import os, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); os.chdir(ROOT)
os.environ["TENDER_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")
from streamlit.testing.v1 import AppTest
from modules.compliance_engine import assess_all
from modules.document_matcher import find_candidates
from modules.pdf_extractor import extract_document
from modules.requirement_extractor import extract_requirements_offline

rd = lambda n: open(os.path.join(ROOT, "data", "samples", n), "rb").read()
tender = extract_document("tender_sample.pdf", rd("tender_sample.pdf"))
reqs = extract_requirements_offline(tender.pages)
vend = [extract_document(n, rd(n)) for n in ["vendor_financials.pdf", "vendor_registration.pdf", "vendor_experience.pdf"]]
results = assess_all(reqs, find_candidates(reqs, vend))

at = AppTest.from_file(os.path.join(ROOT, "app.py"), default_timeout=60).run()
for k, v in {"tender": tender, "tender_name": tender.name, "reqs": reqs, "vendor_docs": vend,
             "vendor_names": [d.name for d in vend], "results": results}.items():
    at.session_state[k] = v
for page in ["Home", "New Analysis", "Results", "Report", "Settings"]:
    at.sidebar.radio[0].set_value(page).run()
    assert not at.exception, (page, [e.value for e in at.exception])
    print("OK", page)
from modules import database
database.save_analysis(tender.name, [d.name for d in vend], results)
at.sidebar.radio[0].set_value("History").run(); assert not at.exception; print("OK History")
from modules.report_generator import build_pdf
from modules.compliance_engine import summarize
assert build_pdf(tender.name, [d.name for d in vend], results, summarize(results))[:4] == b"%PDF"
print("ALL APP TESTS PASSED")
