"""Offline requirement extraction: obligation sentences + category + mandatory flag + page + section."""
import re

OBLIGATION = re.compile(r"\b(must|shall|required|requires|mandatory|minimum|at least|should|"
                        r"is eligible|needs? to|obliged)\b", re.I)
MANDATORY = re.compile(r"\b(must|shall|required|requires|mandatory|minimum|at least)\b", re.I)
HEADING = re.compile(r"^(\d+(\.\d+)*[.)]?\s+\S.{0,70}|[A-Z][A-Z &/,-]{4,70})$")
CATEGORY_RULES = [
    ("Deadline", r"\b(deadline|submitted? (before|by|on)|last date|closing date|due)\b"),
    ("Certificate", r"\b(certificate|certification|iso\s?\d{4,5}|registration|licen[cs]e|gst|pan\b|udyam|msme)\b"),
    ("Financial", r"\b(turnover|revenue|net worth|financial|bank guarantee|earnest|emd|balance sheet)\b"),
    ("Technical", r"\b(technical|specification|hardware|software|server|capacity|uptime|standard|performance)\b"),
    ("Eligibility", r"\b(experience|eligib|similar projects?|years|blacklist|qualif)\b"),
    ("Documentation", r"\b(submit|provide|furnish|attach|document|statement|declaration)\b"),
]


def categorize(text):
    for cat, pat in CATEGORY_RULES:
        if re.search(pat, text, re.I):
            return cat
    return "Other"


def _sentences(paragraph):
    parts = re.split(r"(?<=[.;!?])\s+(?=[A-Z0-9(])", paragraph)
    return [p.strip() for p in parts if p.strip()]


def extract_requirements_offline(pages):
    reqs, section, seen = [], "", set()
    for page_no, text in enumerate(pages, start=1):
        para = []
        lines = text.splitlines() + [""]
        for line in lines:
            s = line.strip()
            is_heading = bool(s) and len(s) < 75 and not s.endswith((".", ",", ";")) and HEADING.match(s) \
                and not re.search(OBLIGATION.pattern, s)
            if is_heading or not s:
                for sent in _sentences(" ".join(para)):
                    if OBLIGATION.search(sent) and len(sent) > 15:
                        key = re.sub(r"\W+", " ", sent.lower())
                        if key in seen:
                            continue
                        seen.add(key)
                        reqs.append({"id": f"R{len(reqs) + 1:02d}", "text": sent, "category": categorize(sent),
                                     "mandatory": bool(MANDATORY.search(sent)), "page": page_no,
                                     "section": section})
                para = []
                if is_heading:
                    section = s
            else:
                para.append(s)
    return reqs
