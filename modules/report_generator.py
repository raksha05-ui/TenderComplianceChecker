"""PDF and Excel exports built only from stored result fields (nothing is invented)."""
import io
from datetime import datetime
from xml.sax.saxutils import escape

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

STATUS_ORDER = ["Potentially Non-Compliant", "Missing Evidence", "Needs Manual Review", "Compliant"]
STATUS_COLORS = {"Compliant": "#2e7d32", "Potentially Non-Compliant": "#c62828",
                 "Missing Evidence": "#ef6c00", "Needs Manual Review": "#1565c0"}
DISCLAIMER = ("This report is decision support only. It is not legal certification or a guarantee of tender "
              "eligibility. Evidence strength is a text-retrieval signal, not a probability of compliance. "
              "All findings should be verified by a qualified person before submission.")
NEXT_STEPS = {
    "Potentially Non-Compliant": "Resolve the discrepancy: obtain a corrected document or confirm the requirement is met.",
    "Missing Evidence": "Obtain and upload the missing supporting document(s).",
    "Needs Manual Review": "Have a person read the evidence and decide; the automated check was inconclusive.",
}


def _p(text):
    return escape(str(text if text not in (None, "") else "-"))


def results_dataframe(results):
    cols = ["req_id", "requirement", "mandatory", "req_page", "status", "document", "evidence_page",
            "evidence", "evidence_strength", "reason", "assessment_method"]
    df = pd.DataFrame(results)
    for c in cols:
        if c not in df:
            df[c] = None
    return df[cols]


def build_excel(results, summary=None):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        results_dataframe(results).to_excel(xw, sheet_name="Results", index=False)
        if summary:
            pd.DataFrame([{"metric": k, "value": v} for k, v in summary.items()]).to_excel(
                xw, sheet_name="Summary", index=False)
        for ws in xw.book.worksheets:
            for col in ws.columns:
                width = max(len(str(c.value or "")) for c in col[:50])
                ws.column_dimensions[col[0].column_letter].width = min(max(width + 2, 10), 60)
    return buf.getvalue()


def build_pdf(tender_name, vendor_docs, results, summary, mode="offline", generated_at=None):
    generated_at = generated_at or datetime.now().strftime("%Y-%m-%d %H:%M")
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm, title="Tender Compliance Report")
    ss = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=ss["BodyText"], fontSize=9, leading=12)
    small = ParagraphStyle("small", parent=body, fontSize=8, leading=10, textColor=colors.HexColor("#555555"))
    story = [Paragraph("Tender Compliance Report", ss["Title"])]

    story += [Paragraph("1. Tender details", ss["Heading2"])]
    info = [["Tender", _p(tender_name)], ["Generated", generated_at],
            ["Analysis mode", "Offline (no AI model used)" if mode == "offline" else _p(mode)],
            ["Supporting documents", _p(", ".join(vendor_docs) if vendor_docs else "none")]]
    t = Table([[Paragraph(f"<b>{a}</b>", body), Paragraph(b, body)] for a, b in info], colWidths=[40 * mm, 130 * mm])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story += [t]

    story += [Paragraph("2. Executive summary", ss["Heading2"])]
    story += [Paragraph(
        f"{summary['total']} requirements were analysed. {summary['Compliant']} appear compliant "
        f"({summary['compliant_pct']}%), {summary['Potentially Non-Compliant']} are potentially non-compliant, "
        f"{summary['Missing Evidence']} have missing evidence and {summary['Needs Manual Review']} need manual review. "
        f"Missing or uncertain items are not counted as compliant.", body), Spacer(1, 4)]
    rows = [["Status", "Count"]] + [[s, summary[s]] for s in STATUS_ORDER]
    st = Table(rows, colWidths=[70 * mm, 25 * mm])
    st.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
                            ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey), ("FONTSIZE", (0, 0), (-1, -1), 9)]))
    story += [st]

    story += [Paragraph("3. Requirement-by-requirement results", ss["Heading2"])]
    for r in results:
        color = STATUS_COLORS.get(r.get("status"), "#000000")
        story.append(Paragraph(
            f"<b>{_p(r.get('req_id'))}</b> - <font color='{color}'><b>{_p(r.get('status'))}</b></font>"
            f"{'' if r.get('mandatory', True) else ' (optional)'}", body))
        story.append(Paragraph(f"Requirement (tender p.{_p(r.get('req_page'))}): {_p(r.get('requirement'))}", body))
        if r.get("assessment_method"):
            story.append(Paragraph(f"Assessment method: {_p(r['assessment_method'])}", small))
        if r.get("document"):
            story.append(Paragraph(f"Evidence: {_p(r['document'])}, p.{_p(r.get('evidence_page'))} "
                                   f"(text similarity {_p(r.get('evidence_strength'))})", small))
            story.append(Paragraph(f"<i>\"{_p(r.get('evidence'))}\"</i>", small))
        else:
            story.append(Paragraph("Evidence: none found", small))
        story += [Paragraph(f"Reason: {_p(r.get('reason'))}", small), Spacer(1, 6)]

    issues = [r for r in results if r.get("status") in ("Potentially Non-Compliant", "Missing Evidence")]
    story += [Paragraph("4. Missing evidence and potential discrepancies", ss["Heading2"])]
    story += [Paragraph(f"{_p(r['req_id'])} [{_p(r['status'])}]: {_p(r['requirement'])[:200]}", body) for r in issues] \
        or [Paragraph("None identified.", body)]

    review = [r for r in results if r.get("status") == "Needs Manual Review"]
    story += [Paragraph("5. Items requiring human review", ss["Heading2"])]
    story += [Paragraph(f"{_p(r['req_id'])}: {_p(r['requirement'])[:200]}", body) for r in review] \
        or [Paragraph("None.", body)]

    story += [Paragraph("6. Recommended next steps", ss["Heading2"])]
    present = [s for s in STATUS_ORDER[:3] if summary[s]]
    story += [Paragraph(f"- <b>{_p(s)}</b> ({summary[s]}): {_p(NEXT_STEPS[s])}", body) for s in present] \
        or [Paragraph("- No open issues; still verify the evidence before submission.", body)]

    story += [Spacer(1, 10), Paragraph(DISCLAIMER, small)]
    doc.build(story)
    return buf.getvalue()
