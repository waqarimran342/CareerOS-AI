"""
Resume service for CareerOS AI.

Extracts plain text from an uploaded resume PDF using `pypdf`, so the
agents can analyze the real resume content instead of self-reported
summaries.
"""

import io
from typing import List

from pypdf import PdfReader

import config


class ResumeError(ValueError):
    """Raised for user-input problems (bad file, empty text, ...).

    The API layer turns these into HTTP 400 responses.
    """


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Return the text content of a resume PDF.

    Raises ResumeError if the file is not a readable PDF or contains no
    extractable text (e.g. a scanned image).
    """
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
    except Exception:
        raise ResumeError("The uploaded file could not be read as a PDF.")

    if not reader.pages:
        raise ResumeError("The PDF contains no pages.")

    pages: List[str] = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")

    text = "\n".join(pages).strip()

    if not text:
        raise ResumeError(
            "No text could be extracted from this PDF. Scanned/image-only "
            "resumes are not supported yet — please upload a text-based PDF."
        )

    # Keep prompts (and therefore cost/latency) under control by truncating
    # very long resumes. 12000 characters is roughly 6 dense pages.
    limit = config.settings.max_resume_chars
    if len(text) > limit:
        text = text[:limit] + "\n...[resume truncated for analysis]"

    return text
