"""End-to-end offline pipeline test on synthetic samples. Run: python tests/run_pipeline.py"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from datetime import date
from modules.compliance_engine import assess_all, summarize
from modules.document_matcher import find_candidates
from modules.pdf_extractor import extract_document
from modules.requirement_extractor import extract_requirements_offline
from modules.validators import ValidationError

S = os.path.join(ROOT, "data", "samples")
rd = lambda n: open(os.path.join(S, n), "rb").read()

tender = extract_document("tender_sample.pdf", rd("tender_sample.pdf"))
reqs = extract_requirements_offline(tender.pages)
vendors = [extract_document(n, rd(n)) for n in
           ["vendor_financials.pdf", "vendor_registration.pdf", "vendor_experience.pdf", "vendor_technical.pdf"]]
results = assess_all(reqs, find_candidates(reqs, vendors), today=date(2026, 10, 9))

for r in results:
    print(f"{r['req_id']} p{r['req_page']} [{r['category']}] {r['status']}\n   {r['requirement'][:90]}\n"
          f"   -> {r['document']} p{r['evidence_page']} | {r['reason']}")
print(summarize(results))

def status(fragment):
    return next(r["status"] for r in results if fragment in r["requirement"])

expected = {
    "turnover": "Compliant",                      # clearly satisfies
    "5 years of experience": "Potentially Non-Compliant",   # contradictory (3 < 5)
    "GST": "Compliant",
    "ISO 9001": "Compliant",
    "ISO 14001": "Missing Evidence",              # no supporting document
    "technical compliance statement": "Needs Manual Review",  # vague evidence
    "30 November 2026": "Needs Manual Review",
}
assert len(reqs) == 7, len(reqs)
for frag, st in expected.items():
    assert status(frag) == st, (frag, status(frag), st)
assert next(r for r in results if "turnover" in r["requirement"])["req_page"] == 1
assert next(r for r in results if "ISO 14001" in r["requirement"])["req_page"] == 2
assert summarize(results)["compliant_pct"] == round(100 * 3 / 7, 1)

# expired certificate -> flagged
exp = assess_all(reqs, find_candidates(reqs, vendors), today=date(2029, 1, 1))
assert next(r for r in exp if "ISO 9001" in r["requirement"])["status"] == "Potentially Non-Compliant"

# file handling
scan = extract_document("vendor_scanned.pdf", rd("vendor_scanned.pdf")); assert scan.needs_ocr and scan.warnings
for name, data in [("corrupted.pdf", rd("corrupted.pdf")), ("empty.pdf", b""), ("x.txt", b"hello"),
                   ("bad.docx", b"not a docx")]:
    try:
        extract_document(name, data); raise SystemExit(f"{name} should have been rejected")
    except ValidationError as e:
        print("rejected:", e)
print("\nALL PIPELINE TESTS PASSED")
