"""Rule-based compliance assessment. Conservative: existence of a document never means Compliant."""
import re
from datetime import date, datetime

from modules.document_matcher import cert_tokens
from modules.validators import VALID_STATUSES

NO_EXPIRY = {"gst", "gstin", "pan", "udyam", "msme"}
MIN_SCORE = 0.08           # below this the best passage is treated as unrelated
UNITS = {"crore": 1e7, "crores": 1e7, "cr": 1e7, "lakh": 1e5, "lakhs": 1e5, "lac": 1e5,
         "million": 1e6, "mn": 1e6, "billion": 1e9}
AMOUNT = re.compile(r"(?:rs\.?|inr|₹)?\s*([\d,]+(?:\.\d+)?)\s*(crores?|cr|lakhs?|lac|million|mn|billion)\b", re.I)
RS_PLAIN = re.compile(r"(?:rs\.?|inr|₹)\s*([\d,]{5,}(?:\.\d+)?)", re.I)
YEARS = re.compile(r"(\d+)\s*\+?\s*(?:full\s+)?years?", re.I)
EXPIRY = re.compile(r"(?:valid(?:ity)?|expir(?:y|es|ing)?)(?:\s+(?:until|till|upto|up to|through|on|date))?\s*[:\-]?\s*"
                    r"(\d{1,2}[ /-][A-Za-z]{3,9}[ /-]\d{4}|\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2})", re.I)
DATE_FORMATS = ("%d %B %Y", "%d %b %Y", "%d-%b-%Y", "%d/%b/%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%B-%Y")


def parse_date(s):
    s = s.strip().replace(",", "")
    for f in DATE_FORMATS:
        try:
            return datetime.strptime(s, f).date()
        except ValueError:
            pass
    return None


def amounts(text):
    vals = [float(n.replace(",", "")) * UNITS[u.lower()] for n, u in AMOUNT.findall(text)]
    vals += [float(n.replace(",", "")) for n in RS_PLAIN.findall(text)]
    return vals


def fmt_money(v):
    return f"Rs {v / 1e7:g} crore" if v >= 1e7 else f"Rs {v:,.0f}"


def _result(req, status, reason, cand=None):
    assert status in VALID_STATUSES
    return {
        "req_id": req["id"], "requirement": req["text"], "category": req.get("category", "Other"),
        "mandatory": req.get("mandatory", True), "req_page": req.get("page"), "status": status, "reason": reason,
        "document": cand["document"] if cand else None, "evidence_page": cand["page"] if cand else None,
        "evidence": cand["text"][:400] if cand else "", "evidence_strength": round(cand["score"], 2) if cand else 0.0,
    }


def assess_requirement(req, cands, today=None):
    today = today or date.today()
    text, low = req["text"], req["text"].lower()
    # Deadlines belong to the tender process, not to vendor evidence.
    if req.get("category") == "Deadline":
        return _result(req, "Needs Manual Review",
                       "Submission deadlines/process rules cannot be proven by vendor documents; confirm manually.",
                       cands[0] if cands else None)
    want = cert_tokens(text)
    if (not cands or cands[0]["score"] < MIN_SCORE) and not want:
        return _result(req, "Missing Evidence", "No passage in the uploaded documents relates to this requirement.")
    best = cands[0] if cands else None

    # Certificates: the named certificate must actually appear in the evidence; check expiry/status.
    if want:
        hits = [(c, want & cert_tokens(c["text"])) for c in cands if want & cert_tokens(c["text"])]
        if not hits:
            return _result(req, "Missing Evidence",
                           f"No evidence of {', '.join(sorted(w.upper() for w in want))} in the uploaded documents.")
        names = lambda h: ", ".join(sorted(h)).upper()
        for c, h in hits:  # a stated expiry date anywhere in the hit passages decides first
            m = EXPIRY.search(c["text"])
            d = parse_date(m.group(1)) if m else None
            if d:
                if d < today:
                    return _result(req, "Potentially Non-Compliant", f"{names(h)} found but it expired on {d:%d %b %Y}.", c)
                return _result(req, "Compliant", f"{names(h)} found and valid until {d:%d %b %Y}.", c)
        c, h = hits[0]
        if re.search(r"cancel+ed|suspended|inactive|revoked|expired", c["text"], re.I):
            return _result(req, "Potentially Non-Compliant", f"{names(h)} found but the text indicates an invalid status.", c)
        if h <= NO_EXPIRY:
            return _result(req, "Compliant",
                           f"{names(h)} registration found in the evidence (these registrations carry no expiry date). "
                           "Verify the number on the issuing portal.", c)
        return _result(req, "Needs Manual Review", f"{names(h)} is mentioned but no validity/expiry date could be read.", c)

    # Financial threshold (turnover / net worth).
    if re.search(r"turnover|revenue|net worth", low) and amounts(text):
        need = max(amounts(text))
        for c in cands:
            if re.search(r"turnover|revenue|net worth", c["text"], re.I) and amounts(c["text"]):
                got = max(amounts(c["text"]))
                if got >= need:
                    return _result(req, "Compliant", f"Evidence shows {fmt_money(got)}, meeting the required {fmt_money(need)}.", c)
                return _result(req, "Potentially Non-Compliant",
                               f"Evidence shows {fmt_money(got)}, below the required {fmt_money(need)}.", c)
        return _result(req, "Needs Manual Review", "A related passage exists but no comparable amount could be read.", best)

    # Years of experience.
    if "experience" in low and YEARS.search(text):
        need = int(YEARS.search(text).group(1))
        for c in cands:
            if re.search(r"experience|operat|established|since", c["text"], re.I) and YEARS.search(c["text"]):
                got = max(int(y) for y in YEARS.findall(c["text"]))
                if got >= need:
                    return _result(req, "Compliant", f"Evidence states {got} years, meeting the required {need}.", c)
                return _result(req, "Potentially Non-Compliant", f"Evidence states {got} years, below the required {need}.", c)
        return _result(req, "Needs Manual Review", "Related text found but no number of years could be read.", best)

    return _result(req, "Needs Manual Review",
                   "Related text was found but this requirement cannot be checked by simple rules; a person must read it.", best)


def assess_all(reqs, candidates, today=None):
    return [assess_requirement(r, candidates.get(r["id"], []), today) for r in reqs]


def summarize(results):
    s = {k: sum(r["status"] == k for r in results) for k in VALID_STATUSES}
    total = len(results)
    s["total"] = total
    s["compliant_pct"] = round(100 * s["Compliant"] / total, 1) if total else 0.0
    s["note"] = (f"Calculated as Compliant / all {total} requirements. Missing evidence, potential non-compliance "
                 "and items needing review are not counted as compliant.")
    return s
