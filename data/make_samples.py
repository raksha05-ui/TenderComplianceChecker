"""Create SYNTHETIC demo files in data/samples/ (fictional company, not real data)."""
import os
import pymupdf
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "samples")
os.makedirs(OUT, exist_ok=True)
ss = getSampleStyleSheet()


def make(name, blocks):
    story = []
    for kind, text in blocks:
        story.append(PageBreak() if kind == "br" else Paragraph(text, ss["Heading2"] if kind == "h" else ss["BodyText"]))
        story.append(Spacer(1, 6))
    SimpleDocTemplate(os.path.join(OUT, name), pagesize=A4).build(story)


make("tender_sample.pdf", [
    ("h", "SYNTHETIC SAMPLE - Tender No. DEMO/IT/2026/01 - Supply of Server Hardware"),
    ("h", "1. ELIGIBILITY CRITERIA"),
    ("p", "The bidder must have an average annual turnover of at least Rs 5 crore in the last three financial years."),
    ("p", "The bidder must have a minimum of 5 years of experience in executing similar projects."),
    ("br", ""),
    ("h", "2. REQUIRED CERTIFICATES"),
    ("p", "The bidder shall hold a valid GST registration certificate."),
    ("p", "The bidder must possess a valid ISO 9001 quality management certificate."),
    ("p", "The bidder must submit a valid ISO 14001 environmental certificate."),
    ("br", ""),
    ("h", "3. TECHNICAL SPECIFICATIONS"),
    ("p", "The bidder shall provide a technical compliance statement for the proposed server hardware, including rack capacity and uptime guarantees."),
    ("h", "4. SUBMISSION"),
    ("p", "Bids must be submitted before 30 November 2026."),
    ("p", "This tender is issued for demonstration purposes only."),
])
make("vendor_financials.pdf", [
    ("h", "Chartered Accountant Certificate - Acme Systems Pvt Ltd (FICTIONAL)"),
    ("p", "We certify that the average annual turnover of Acme Systems Pvt Ltd for the last three financial years was Rs 6.2 crore."),
])
make("vendor_registration.pdf", [
    ("h", "Acme Systems Pvt Ltd - Registrations (FICTIONAL)"),
    ("p", "GST registration certificate. GSTIN 07AAAAA0000A1Z5. Status: Active."),
    ("br", ""),
    ("h", "Quality certification"),
    ("p", "ISO 9001:2015 quality management system certificate. Valid until 31 March 2028."),
])
make("vendor_experience.pdf", [
    ("h", "Company profile - Acme Systems Pvt Ltd (FICTIONAL)"),
    ("p", "Our company has 3 years of experience in executing similar projects for public sector clients."),
])
make("vendor_technical.pdf", [
    ("h", "Technical note - Acme Systems Pvt Ltd (FICTIONAL)"),
    ("p", "Our servers generally conform to industry norms and we aim to offer reliable hardware to clients."),
])
# scanned (image-only) PDF: render text to an image, embed only the image
src = pymupdf.open()
pg = src.new_page(); pg.insert_text((72, 100), "Scanned experience letter - no text layer", fontsize=14)
pix = pg.get_pixmap(dpi=100)
scan = pymupdf.open(); sp = scan.new_page(); sp.insert_image(sp.rect, pixmap=pix)
scan.save(os.path.join(OUT, "vendor_scanned.pdf"))
with open(os.path.join(OUT, "corrupted.pdf"), "wb") as f:
    f.write(b"%PDF-1.4 this is not a real pdf")
print("Samples written to", OUT)
