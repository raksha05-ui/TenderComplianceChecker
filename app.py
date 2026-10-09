"""Tender & Document Compliance Checker - offline-first Streamlit app (Phase 1-6).

Run:  streamlit run app.py
"""
import os

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv

from modules import database
from modules.compliance_engine import assess_all, summarize
from modules.document_matcher import find_candidates
from modules.gemini_assessor import GeminiAssessmentError, assess_unresolved_with_gemini
from modules.pdf_extractor import extract_document
from modules.report_generator import build_excel, build_pdf
from modules.requirement_extractor import extract_requirements_offline
from modules.validators import VALID_CATEGORIES, VALID_STATUSES, ValidationError

load_dotenv()
st.set_page_config(page_title="Tender Compliance Checker", page_icon="📋", layout="wide")

STATUS_COLORS = {
    "Compliant": "#2e7d32",
    "Potentially Non-Compliant": "#c62828",
    "Missing Evidence": "#ef6c00",
    "Needs Manual Review": "#1565c0",
}
DISCLAIMER = (
    "Decision support only - not legal certification or a guarantee of tender eligibility. "
    "Offline mode uses text extraction, keyword/TF-IDF matching and simple rules. Gemini review is optional."
)

ss = st.session_state
for key, default in {"tender": None, "reqs": [], "vendor_docs": [], "results": [], "tender_name": "",
                     "vendor_names": [], "analysis_id": None, "store_excerpts": True}.items():
    ss.setdefault(key, default)


def inject_custom_css():
    st.markdown(
        """
        <style>
            .stApp {
                background: linear-gradient(180deg, #020817 0%, #0b1220 46%, #111827 100%);
                color: #e2e8f0;
            }
            .block-container {
                padding-top: 1rem;
                padding-bottom: 2.5rem;
            }
            div[data-testid="stSidebar"] {
                background: linear-gradient(180deg, #0b1120 0%, #111827 100%);
                border-right: 1px solid rgba(148,163,184,0.14);
            }
            [data-testid="stSidebar"] * {
                color: #edf4ff;
            }
            [data-testid="stSidebar"] .stRadio {
                color: #edf4ff;
            }
            [data-testid="stSidebar"] label {
                color: #edf4ff !important;
            }
            [data-testid="stSidebar"] .st-bd {
                background: transparent;
            }
            .welcome-card {
                background: linear-gradient(135deg, rgba(15, 23, 42, 0.9), rgba(30, 41, 59, 0.92));
                border: 1px solid rgba(148,163,184,0.18);
                border-radius: 20px;
                padding: 1.1rem 1.3rem;
                box-shadow: 0 18px 42px rgba(15, 23, 42, 0.45);
                margin-bottom: 1.2rem;
            }
            .welcome-card h3,
            .welcome-card p {
                color: #e2e8f0;
            }
            .step-box {
                background: linear-gradient(180deg, rgba(15, 23, 42, 0.94) 0%, rgba(17, 24, 39, 0.94) 100%);
                border: 1px solid rgba(148,163,184,0.18);
                border-radius: 18px;
                padding: 1rem 1rem 0.95rem;
                box-shadow: 0 16px 30px rgba(2, 6, 23, 0.42);
                height: 100%;
            }
            .step-box h4,
            .step-box p {
                color: #e2e8f0;
            }
            .small-text {
                color: #cbd5e1;
                font-size: 0.92rem;
                line-height: 1.5;
            }
            [data-testid="stMetricValue"] {
                font-size: 1.45rem;
                color: #f8fafc;
            }
            [data-testid="stMetricLabel"] {
                color: #cbd5e1;
            }
            .stAlert {
                border-radius: 12px;
            }
            .stButton > button {
                border-radius: 12px;
                font-weight: 700;
                background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
                color: white;
                border: none;
                box-shadow: 0 12px 22px rgba(59, 130, 246, 0.26);
                padding: 0.7rem 1.5rem;
            }
            .stButton > button:hover {
                filter: brightness(1.04);
            }
            .stFileUploader > section {
                background: rgba(15, 23, 42, 0.72);
                border: 1.5px dashed rgba(96,165,250,0.9);
                border-radius: 16px;
                padding: 0.75rem 0.9rem;
                box-shadow: inset 0 1px 2px rgba(148,163,184,0.18);
            }
            .page-shell {
                background: rgba(15, 23, 42, 0.72);
                border: 1px solid rgba(148,163,184,0.14);
                border-radius: 24px;
                padding: 1.5rem 1.7rem 1rem;
                box-shadow: 0 22px 50px rgba(2, 6, 23, 0.4);
            }
            .main-title {
                margin: 0 0 0.25rem 0;
                font-size: clamp(2.2rem, 4vw, 3rem);
                line-height: 1.1;
                font-weight: 800;
                color: #f8fafc;
            }
            .sub-heading {
                font-size: 1.2rem;
                margin: 0.75rem 0 1.25rem;
                color: #cbd5e1;
                font-weight: 600;
            }
            .step-card {
                background: linear-gradient(180deg, rgba(15,23,42,0.94), rgba(17,24,39,0.96));
                border: 1px solid rgba(148,163,184,0.16);
                border-radius: 18px;
                padding: 1.25rem 1.35rem 1rem;
                margin: 0.9rem 0 1.2rem;
                box-shadow: 0 12px 24px rgba(2, 6, 23, 0.28);
            }
            .step-row {
                display: flex;
                align-items: center;
                gap: 0.9rem;
                margin-bottom: 0.8rem;
            }
            .step-badge {
                width: 2rem;
                height: 2rem;
                border-radius: 50%;
                background: linear-gradient(135deg, #3b82f6, #2563eb);
                color: white;
                display: inline-flex;
                align-items: center;
                justify-content: center;
                font-weight: 700;
                font-size: 0.95rem;
                box-shadow: 0 8px 16px rgba(37, 99, 235, 0.2);
            }
            .step-title {
                margin: 0;
                font-size: 2rem;
                line-height: 1.15;
                font-weight: 800;
                color: #f8fafc;
            }
            .step-caption {
                margin: 0.35rem 0 0.7rem;
                color: #cbd5e1;
                font-size: 1rem;
            }
            .footer-note {
                margin-top: 0.8rem;
                color: #cbd5e1;
                font-size: 0.95rem;
                text-align: center;
            }
            .stDataFrame, .stDataEditor {
                border-radius: 12px;
                overflow: hidden;
            }
            .stTabs [role="tablist"] {
                gap: 0.6rem;
            }
            .stTabs [role="tab"] {
                border-radius: 10px 10px 0 0;
                background: rgba(15, 23, 42, 0.74);
                color: #e2e8f0;
                border: 1px solid rgba(148,163,184,0.18);
            }
            .stTextInput > div > div > input,
            .stNumberInput > div > div > input,
            .stTextArea textarea,
            .stSelectbox > div > div,
            .stDateInput > div > div,
            .stMultiSelect > div > div {
                background: rgba(15, 23, 42, 0.88) !important;
                color: #f8fafc !important;
                border: 1px solid rgba(148,163,184,0.2) !important;
            }
            .stTextInput label,
            .stNumberInput label,
            .stTextArea label,
            .stSelectbox label,
            .stDateInput label,
            .stMultiSelect label {
                color: #e2e8f0 !important;
            }
            .css-1v0mbdj, .css-1544g2n {
                background: transparent;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


inject_custom_css()


def load_files(files, label):
    docs = []
    for f in files:
        try:
            doc = extract_document(f.name, f.getvalue())
        except (ValidationError, ValueError) as exc:
            st.error(str(exc))
            continue
        for w in doc.warnings:
            st.warning(w)
        docs.append(doc)
    return docs


def page_home():
    st.markdown(
        """
        <div style="display:flex; align-items:center; justify-content:space-between; gap:1rem; margin-bottom:0.75rem; flex-wrap:wrap;">
            <div>
                <div style="font-size:0.8rem; letter-spacing:0.12em; text-transform:uppercase; color:#4f46e5; font-weight:700;">Tender review dashboard</div>
                <h1 style="margin:0.25rem 0 0; color:#f8fafc;">Tender & Document Compliance Checker</h1>
            </div>
            <div style="padding:0.5rem 0.8rem; border-radius:999px; background:rgba(79,70,229,0.08); color:#4f46e5; font-weight:600; border:1px solid rgba(79,70,229,0.14);">Offline mode</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(DISCLAIMER)

    intro = st.container()
    with intro:
        st.markdown(
            """
            <div class="welcome-card">
                <h3 style="margin-top:0;">Simple, guided compliance review for tender teams</h3>
                <p>Upload a tender, add supporting vendor documents, and review requirement-by-requirement compliance in a few clear steps.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    c1, c2, c3 = st.columns(3)
    c1.metric("Tender loaded", ss.tender_name or "None")
    c2.metric("Requirements", len(ss.reqs))
    c3.metric("Vendor documents", len(ss.vendor_docs))

    st.markdown("### Quick start")
    steps = st.columns(3)
    with steps[0]:
        st.markdown(
            """
            <div class="step-box">
                <h4>1. Prepare</h4>
                <p class="small-text">Pick the tender PDF and any vendor documents you want checked.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with steps[1]:
        st.markdown(
            """
            <div class="step-box">
                <h4>2. Review</h4>
                <p class="small-text">Adjust extracted requirements if needed, then run the match and review logic.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with steps[2]:
        st.markdown(
            """
            <div class="step-box">
                <h4>3. Export</h4>
                <p class="small-text">Open the results, export a PDF/Excel report, and keep a record in history.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if not ss.tender_name:
        st.info("Start with **New Analysis** in the sidebar to upload a tender PDF and the supporting documents.")
    elif ss.results:
        render_dashboard(ss.results)


def page_new():
    st.markdown("<div class='page-shell'>", unsafe_allow_html=True)
    st.markdown("<h1 class='main-title'>New Analysis</h1>", unsafe_allow_html=True)
    st.markdown("<p class='sub-heading'>Follow the steps below to upload documents and run the compliance check.</p>", unsafe_allow_html=True)

    st.markdown("<div class='step-card'><div class='step-row'><div class='step-badge'>1</div><h3 class='step-title'>Upload the tender document</h3></div></div>", unsafe_allow_html=True)
    up = st.file_uploader("Select a tender PDF", type=["pdf"], key="tender_up", help="Upload the official tender or request for proposal.")
    st.markdown("</div>", unsafe_allow_html=True)
    if up and st.button("Extract requirements", type="primary"):
        with st.spinner("Extracting text and requirements..."):
            docs = load_files([up], "tender")
            if docs and not docs[0].needs_ocr:
                ss.tender = docs[0]
                ss.tender_name, ss.analysis_id = docs[0].name, None
                ss.reqs = extract_requirements_offline(docs[0].pages)
                ss.results = []
            elif docs:
                st.error("This tender has no extractable text. Run OCR on it first.")
    if ss.tender:
        st.success(f"{ss.tender.name}: {len(ss.tender.pages)} page(s), {len(ss.reqs)} requirement(s) found.")
        if not ss.reqs:
            st.warning("No requirement-style sentences were detected. Offline extraction relies on words like "
                       "'must', 'shall', 'required', 'minimum'.")
        else:
            st.caption("Review the extracted obligations below. You can edit the requirement text, category, or mark items optional.")
            df = pd.DataFrame(ss.reqs)[["id", "text", "category", "mandatory", "page", "section"]]
            edited = st.data_editor(
                df, num_rows="dynamic", width="stretch", hide_index=True,
                column_config={
                    "category": st.column_config.SelectboxColumn(options=list(VALID_CATEGORIES)),
                    "text": st.column_config.TextColumn(width="large"),
                    "id": st.column_config.TextColumn(disabled=True),
                },
            )
            rows = edited.dropna(subset=["text"]).to_dict("records")
            for i, r in enumerate(rows, start=1):
                r["id"] = r.get("id") or f"R{i:02d}"
                r["page"] = None if pd.isna(r.get("page")) else int(r["page"])
                r["section"] = "" if pd.isna(r.get("section")) else r["section"]
            ss.reqs = rows

    st.markdown("<div class='step-card'><div class='step-row'><div class='step-badge'>2</div><h3 class='step-title'>Upload supporting documents</h3></div></div>", unsafe_allow_html=True)
    files = st.file_uploader("Select vendor PDFs or DOCX files", type=["pdf", "docx"],
                             accept_multiple_files=True, key="vendor_up",
                             help="Upload bids, certificates, turnover details, and other evidence files.")
    st.markdown("</div>", unsafe_allow_html=True)
    if files and st.button("Load documents"):
        ss.vendor_docs = load_files(files, "vendor")
        ss.vendor_names = [d.name for d in ss.vendor_docs]
        ss.results, ss.analysis_id = [], None
    if ss.vendor_docs:
        st.write(pd.DataFrame([{"document": d.name, "pages": len(d.pages), "characters": d.char_count,
                                "needs OCR": d.needs_ocr} for d in ss.vendor_docs]))

    st.markdown("<div class='step-card'><div class='step-row'><div class='step-badge'>3</div><h3 class='step-title'>Run the compliance check</h3></div><p class='step-caption'>When you are ready, click below to match evidence and review the outcome.</p></div>", unsafe_allow_html=True)
    ready = bool(ss.reqs and ss.vendor_docs)
    google_key = os.getenv("GOOGLE_API_KEY")
    google_ready = os.getenv("LLM_PROVIDER", "offline").lower() == "google" and bool(google_key)
    use_gemini = False
    if google_ready:
        use_gemini = st.checkbox(
            "Ask Gemini to review uncertain matches",
            key="use_gemini_review",
            help="Only requirements left at Needs Manual Review and their matched evidence passages are sent to Google. "
                 "Do not enable this if the documents contain information you cannot share with Google.",
        )
        st.caption(f"Optional second-pass model: `{os.getenv('LLM_MODEL', 'gemini-3.8-flash')}`. "
                   "Offline analysis remains the default.")
    else:
        st.caption("Gemini review is unavailable. Set LLM_PROVIDER=google and GOOGLE_API_KEY to enable it.")
    if st.button("Check compliance", type="primary", disabled=not ready):
        usable = [d for d in ss.vendor_docs if not d.needs_ocr]
        with st.spinner("Matching evidence and evaluating compliance..."):
            cands = find_candidates(ss.reqs, usable)
            ss.results = assess_all(ss.reqs, cands)
        analysis_mode = "offline"
        if use_gemini:
            try:
                ss.results = assess_unresolved_with_gemini(
                    ss.reqs, cands, ss.results, google_key, os.getenv("LLM_MODEL", "gemini-3.8-flash")
                )
                if any(r.get("assessment_method") == "Gemini-assisted review" for r in ss.results):
                    analysis_mode = "Gemini-assisted review"
                    st.info("Gemini reviewed only unresolved items with matched evidence. Verify its findings manually.")
                else:
                    st.info("No unresolved requirements with matched evidence needed Gemini review.")
            except GeminiAssessmentError as exc:
                st.warning(f"Gemini review was unavailable; showing the offline results. Details: {exc}")
        try:
            ss.analysis_id = database.save_analysis(ss.tender_name, ss.vendor_names, ss.results,
                                                    mode=analysis_mode, store_excerpts=ss.store_excerpts)
        except Exception as exc:  # DB problems must not lose the in-memory results
            ss.analysis_id = None
            st.warning(f"Results were not saved to history: {exc}")
        st.success("Analysis complete. Review the results in the Results section.")
    st.markdown("</div>", unsafe_allow_html=True)
    if not ready:
        st.markdown("<p class='footer-note'>You need at least one tender requirement and one supporting document before calculating results.</p>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def render_dashboard(results):
    s = summarize(results)
    cols = st.columns(5)
    cols[0].metric("Total", s["total"])
    cols[1].metric("Compliant", s["Compliant"])
    cols[2].metric("Potentially non-compliant", s["Potentially Non-Compliant"])
    cols[3].metric("Missing evidence", s["Missing Evidence"])
    cols[4].metric("Manual review", s["Needs Manual Review"])
    st.caption(f"Compliant: {s['compliant_pct']}%. {s['note']}")
    counts = pd.Series([r["status"] for r in results]).value_counts().reindex(VALID_STATUSES, fill_value=0)
    fig = px.bar(x=counts.index, y=counts.values, color=counts.index, color_discrete_map=STATUS_COLORS,
                 labels={"x": "", "y": "Requirements"})
    fig.update_layout(showlegend=False, height=300, margin=dict(t=10, b=10))
    st.plotly_chart(fig, width="stretch")


def page_results():
    st.header("Compliance results")
    if not ss.results:
        st.info("No results yet. Run an analysis from **New Analysis**.")
        return
    render_dashboard(ss.results)

    order = {s: i for i, s in enumerate(["Potentially Non-Compliant", "Missing Evidence", "Needs Manual Review", "Compliant"])}
    st.subheader("Issues needing attention")
    for r in sorted(ss.results, key=lambda r: (order[r["status"]], not r["mandatory"])):
        if r["status"] == "Compliant":
            continue
        st.markdown(f"**{r['req_id']}** - :{'red' if r['status'].startswith('Pot') else 'orange'}[{r['status']}]"
                    f"{'' if r['mandatory'] else ' (optional)'} - {r['requirement'][:110]}")

    st.subheader("Inspect and correct")
    for r in ss.results:
        label = f"{r['req_id']} | {r['status']} | {r['requirement'][:80]}"
        with st.expander(label):
            st.markdown(f"**Requirement** (tender p.{r['req_page']}): {r['requirement']}")
            st.markdown(f"**Why:** {r['reason']}")
            if r.get("assessment_method"):
                st.caption(f"Assessment: {r['assessment_method']}")
            if r["document"]:
                st.markdown(f"**Evidence** - {r['document']}, p.{r['evidence_page']}")
                st.code(r["evidence"], language=None)
                st.caption(f"Evidence strength (text similarity {r['evidence_strength']}) is a retrieval signal, "
                           "not a probability that the requirement is met.")
            new = st.selectbox("Override status after your review", VALID_STATUSES,
                               index=VALID_STATUSES.index(r["status"]), key=f"ov_{r['req_id']}")
            if new != r["status"]:
                r["status"], r["reason"] = new, r["reason"] + " [status changed by reviewer]"
                if ss.analysis_id:
                    database.save_analysis(ss.tender_name, ss.vendor_names, ss.results,
                                           store_excerpts=ss.store_excerpts, analysis_id=ss.analysis_id)
                st.rerun()

    df = pd.DataFrame(ss.results)
    st.download_button("Download results (CSV)", df.to_csv(index=False).encode("utf-8"),
                       "compliance_results.csv", "text/csv")
    st.caption(DISCLAIMER)


def page_report():
    st.header("Report generation")
    if not ss.results:
        st.info("No results yet. Run an analysis from **New Analysis** first, or reopen one from **History**.")
        return
    s = summarize(ss.results)
    st.write(f"**{ss.tender_name}** - {s['total']} requirements, {s['compliant_pct']}% compliant. {s['note']}")
    pending = sum(1 for r in ss.results if r["status"] == "Needs Manual Review")
    if pending:
        st.warning(f"{pending} item(s) still need manual review. Correct them on **Results** before finalising.")
    c1, c2, c3 = st.columns(3)
    c1.download_button("Download PDF report",
                       build_pdf(ss.tender_name, ss.vendor_names, ss.results, s,
                                 mode="Gemini-assisted review" if any(
                                     r.get("assessment_method") == "Gemini-assisted review" for r in ss.results
                                 ) else "offline"),
                       "compliance_report.pdf", "application/pdf", type="primary")
    c2.download_button("Download Excel", build_excel(ss.results, s), "compliance_results.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    c3.download_button("Download CSV", pd.DataFrame(ss.results).to_csv(index=False).encode("utf-8"),
                       "compliance_results.csv", "text/csv")
    st.caption(DISCLAIMER)


def page_history():
    st.header("Analysis history")
    try:
        rows = database.list_analyses()
    except Exception as exc:
        st.error(f"Could not read history: {exc}")
        return
    if not rows:
        st.info("No saved analyses yet. Each completed analysis is saved here automatically.")
        return
    st.dataframe(pd.DataFrame(rows).rename(columns={
        "tender_name": "tender", "created_at": "created", "non_compliant": "non-compliant"}).drop(
        columns=["updated_at"]), width="stretch", hide_index=True)
    pick = st.selectbox("Select an analysis", [r["id"] for r in rows],
                        format_func=lambda i: next(f"#{r['id']} - {r['tender_name']} ({r['created_at']})"
                                                   for r in rows if r["id"] == i))
    c1, c2 = st.columns(2)
    if c1.button("Reopen in Results", type="primary"):
        a = database.load_analysis(pick)
        ss.results, ss.tender_name, ss.vendor_names, ss.analysis_id = (
            a["results"], a["tender_name"], a["vendor_docs"], a["id"])
        st.success("Loaded. Open **Results** or **Report** in the sidebar.")
    if c2.button("Delete"):
        database.delete_analysis(pick)
        if ss.analysis_id == pick:
            ss.analysis_id = None
        st.rerun()


def page_settings():
    st.header("Settings and configuration")
    google_key = os.getenv("GOOGLE_API_KEY")
    llm_provider = os.getenv("LLM_PROVIDER", "offline").lower()
    llm_model = os.getenv("LLM_MODEL", "gemini-3.8-flash")
    legacy_anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    has_key = bool(google_key or legacy_anthropic_key)
    provider_name = "Google AI Studio" if google_key else "Anthropic (legacy)" if legacy_anthropic_key else "offline"
    st.markdown(f"**Provider:** `{llm_provider}`. **Model:** `{llm_model}`. {provider_name} API key "
                f"{'detected' if has_key else 'not set'} "
                "(the key itself is never displayed or stored).")
    st.info("Analysis runs offline unless you explicitly enable Gemini review on the New Analysis page. "
            "When enabled, only unresolved requirements and matched evidence passages are sent to Google.")
    st.markdown("API keys belong in environment variables or Streamlit secrets, never in the database.")
    ss.store_excerpts = st.toggle("Save short evidence excerpts (max 500 chars) in history", value=ss.store_excerpts,
                                  help="Turn off to keep document text out of the database entirely.")
    st.caption(f"History database: `{database.DB_PATH}` (local file, single user - do not share it).")
    st.caption(DISCLAIMER)


PAGES = {"Home": page_home, "New Analysis": page_new, "Results": page_results,
         "Report": page_report, "History": page_history, "Settings": page_settings}
choice = st.sidebar.radio("Navigate", list(PAGES))
st.sidebar.caption("Mode: **offline by default**; Gemini review is opt-in")
PAGES[choice]()
