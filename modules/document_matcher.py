"""Candidate evidence retrieval: sentence-window passages ranked by TF-IDF cosine + keyword boost."""
import re

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

CERT_TOKEN = re.compile(r"\b(iso\s?-?\d{4,5}|gst(?:in)?|pan|udyam|msme|cmmi|fssai|ce marking)\b", re.I)
TOP_K = 3


def _stem(w):
    for suf in ("ing", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def analyzer(text):
    """Lowercase, drop stop words, crude stemming (server/servers), then add bigrams."""
    toks = [_stem(w) for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in ENGLISH_STOP_WORDS]
    return toks + [f"{a} {b}" for a, b in zip(toks, toks[1:])]


def cert_tokens(text):
    return {re.sub(r"[\s-]", "", t).lower() for t in CERT_TOKEN.findall(text)}


def _passages(doc, window=2):
    out = []
    for page_no, text in enumerate(doc.pages, start=1):
        sents = [s.strip() for s in re.split(r"(?<=[.;!?])\s+|\n+", text) if len(s.strip()) > 3]
        for i in range(len(sents)):
            chunk = " ".join(sents[i:i + window])
            out.append({"document": doc.name, "page": page_no, "text": chunk})
    return out


def find_candidates(reqs, docs, top_k=TOP_K):
    """Return {req_id: [candidate dicts sorted by score]}. Candidates keep document name + page."""
    passages = [p for d in docs for p in _passages(d)]
    if not reqs or not passages:
        return {r["id"]: [] for r in reqs}
    corpus = [p["text"] for p in passages] + [r["text"] for r in reqs]
    vec = TfidfVectorizer(analyzer=analyzer, sublinear_tf=True)
    try:
        m = vec.fit_transform(corpus)
    except ValueError:  # empty vocabulary
        return {r["id"]: [] for r in reqs}
    pm, rm = m[: len(passages)], m[len(passages):]
    sims = cosine_similarity(rm, pm)
    ptoks = [cert_tokens(p["text"]) for p in passages]
    result = {}
    for i, r in enumerate(reqs):
        want = cert_tokens(r["text"])
        scored = []
        for j, p in enumerate(passages):
            score = float(sims[i, j]) + (0.5 if want and want & ptoks[j] else 0.0)
            if score > 0:
                scored.append({**p, "score": round(score, 3)})
        scored.sort(key=lambda c: -c["score"])
        picked, seen = [], set()
        for c in scored:  # drop near-duplicate overlapping windows
            key = (c["document"], c["page"], c["text"][:60])
            if key not in seen:
                seen.add(key)
                picked.append(c)
            if len(picked) == top_k:
                break
        result[r["id"]] = picked
    return result
