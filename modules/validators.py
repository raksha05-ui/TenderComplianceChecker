"""Shared constants and input validation."""
import os

VALID_STATUSES = ["Compliant", "Potentially Non-Compliant", "Missing Evidence", "Needs Manual Review"]
VALID_CATEGORIES = ("Eligibility", "Financial", "Technical", "Certificate", "Deadline", "Documentation", "Other")
ALLOWED_EXTENSIONS = (".pdf", ".docx")
MAX_FILE_MB = 20


class ValidationError(Exception):
    """Raised for unusable uploads (wrong type, empty, too large, corrupted)."""


def validate_upload(name, data):
    ext = os.path.splitext(name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(f"{name}: unsupported file type '{ext or 'none'}'. Use PDF or DOCX.")
    if not data:
        raise ValidationError(f"{name}: the file is empty.")
    if len(data) > MAX_FILE_MB * 1024 * 1024:
        raise ValidationError(f"{name}: larger than {MAX_FILE_MB} MB.")
    return ext


def validate_requirement(r):
    """Return a cleaned requirement dict or raise ValidationError (used for LLM output too)."""
    text = str(r.get("text", "")).strip()
    if len(text) < 8:
        raise ValidationError("requirement text too short")
    cat = r.get("category") if r.get("category") in VALID_CATEGORIES else "Other"
    return {**r, "text": text, "category": cat, "mandatory": bool(r.get("mandatory", True))}
