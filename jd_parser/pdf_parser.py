"""
pdf_parser.py
-------------
Handles raw text extraction from a PDF file using pypdf.
This module is intentionally simple — it just reads pages and returns text.
"""

from pypdf import PdfReader
import io


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Extract all text from a PDF given its raw bytes.

    Args:
        file_bytes: Raw PDF file content as bytes.

    Returns:
        A single string containing all extracted text, pages joined by newlines.

    Raises:
        ValueError: If the PDF is empty or unreadable.
    """
    reader = PdfReader(io.BytesIO(file_bytes))

    if len(reader.pages) == 0:
        raise ValueError("The uploaded PDF has no pages.")

    pages_text = []
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            pages_text.append(page_text.strip())

    full_text = "\n".join(pages_text)

    if not full_text.strip():
        raise ValueError("Could not extract any text from the PDF. It may be scanned/image-based.")

    return full_text
