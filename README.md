# Tender & Document Compliance Checker (offline-first, Phases 1-5)

**Strategy:** the offline pipeline (extraction + TF-IDF matching + rules) is complete and demonstrable on its own. Google AI Studio settings can be recorded in `.env`, but this version does not make Gemini API calls; analysis remains offline.

Upload a tender PDF, extract its requirements, upload vendor documents (PDF/DOCX), and get an
explainable compliance status per requirement. **Works fully offline - no API key needed.**

## Run
```bash
python -m venv .venv && source .venv/bin/activate   # optional
pip install -r requirements.txt
python data/make_samples.py          # creates SYNTHETIC demo files in data/samples/
streamlit run app.py
```

Google AI Studio configuration (recognized by Settings, but not currently used to make API calls):
```bash
# Add these values to .env. Keep your API key private.
GOOGLE_API_KEY=your-google-ai-studio-key
LLM_PROVIDER=google
LLM_MODEL=gemini-flash-latest
```

Demo: on **New Analysis** upload `data/samples/tender_sample.pdf`, then the four `vendor_*.pdf`
files (skip `vendor_scanned.pdf` to see the OCR warning, or add it to see it handled).

## Tests
```bash
python tests/run_pipeline.py   # end-to-end test on synthetic samples (asserts every expected status)
python tests/test_app.py       # renders all pages with sample results
python tests/test_phase5.py    # SQLite history + PDF/Excel report tests
```

## How the offline pipeline works
1. **pdf_extractor** - PyMuPDF per-page text (page numbers kept); detects image-only PDFs (needs OCR), corrupted/empty/wrong-type files.
2. **requirement_extractor** - finds obligation sentences (must/shall/minimum/...), tags category, mandatory flag, page.
3. **document_matcher** - TF-IDF + cosine similarity over sentence-window passages -> top-3 candidate evidence per requirement.
4. **compliance_engine** - deterministic checks (turnover thresholds, years of experience, expiry dates, deadlines, named certificates), otherwise conservative "Needs Manual Review". A document merely existing never produces "Compliant".

## Offline-mode limitations
- No semantic understanding: paraphrased evidence can be missed; vague text goes to manual review.
- Evidence strength is text similarity, **not** a probability of compliance.
- Scanned PDFs need OCR first (e.g. `ocrmypdf`). DOCX text is reported as page 1.
- Decision support only - not legal certification or a guarantee of eligibility.

## Phase 5 additions
- **History** (SQLite, `data/history.db`): every analysis is saved automatically; reopen or delete from the History page. Reviewer overrides on Results are saved too. Only requirement text, statuses, reasons and short evidence excerpts (max 500 chars, can be disabled in Settings) are stored - never API keys or full document text. Add `data/history.db` to `.gitignore`.
- **Report** page: PDF report (tender details, executive summary, per-requirement results with evidence and page refs, missing evidence, manual-review items, next steps), plus Excel and CSV.
- **Settings** page: shows whether an API key is configured (never the key), the excerpt-storage toggle and the DB location.

## Not built yet
Optional LLM mode (Phase 6: key via `.env`, see `.env.example`), UI polish, screenshots and final test write-up (Phase 7).
