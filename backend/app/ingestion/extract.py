"""Upload validation and text extraction.

- Validates file signatures (magic bytes), not just extensions.
- Never executes uploaded content; PDFs are only parsed for text.
- Pages without a text layer are OCR'd only when Tesseract is available; otherwise the document is
  rejected with an actionable message instead of being silently accepted.
"""
from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass

import pymupdf

from app.config import MAX_PAGES, MAX_UPLOAD_BYTES
from app.models import PageText


class DocumentError(Exception):
    """A user-correctable problem with an uploaded document."""

    def __init__(self, message: str, code: str = "document_invalid"):
        super().__init__(message)
        self.code = code


@dataclass
class Extracted:
    pages: list[PageText]
    page_count: int
    sha256: str
    warnings: list[str]
    kind: str  # pdf | csv | json


def sniff_kind(data: bytes) -> str:
    head = data[:1024].lstrip()
    if data[:5] == b"%PDF-":
        return "pdf"
    if head[:1] in (b"{", b"["):
        return "json"
    try:
        sample = data[:4096].decode("utf-8")
    except UnicodeDecodeError:
        raise DocumentError("Unsupported file type. Upload a PDF document, or a CSV/JSON itemised bill.",
                            "unsupported_type")
    if "," in sample and "\n" in sample:
        return "csv"
    raise DocumentError("Unsupported file type. Upload a PDF document, or a CSV/JSON itemised bill.",
                        "unsupported_type")


def check_size(data: bytes) -> None:
    if len(data) == 0:
        raise DocumentError("The uploaded file is empty.", "empty_file")
    if len(data) > MAX_UPLOAD_BYTES:
        raise DocumentError(f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.", "too_large")


def tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


def extract_pdf(data: bytes) -> Extracted:
    check_size(data)
    if data[:5] != b"%PDF-":
        raise DocumentError("This file is not a valid PDF (missing PDF signature).", "unsupported_type")
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:  # corrupted or truncated files
        raise DocumentError("The PDF could not be opened. It may be corrupted or truncated; please re-export "
                            "or re-scan the document.", "corrupted") from exc
    with doc:
        if doc.needs_pass:
            raise DocumentError("The PDF is password-protected. Remove the password and upload again.", "encrypted")
        if doc.page_count == 0:
            raise DocumentError("The PDF contains no pages.", "empty_document")
        if doc.page_count > MAX_PAGES:
            raise DocumentError(f"The PDF has {doc.page_count} pages; the limit is {MAX_PAGES}.", "too_many_pages")
        pages: list[PageText] = []
        warnings: list[str] = []
        ocr_ok = tesseract_available()
        for i, page in enumerate(doc, start=1):
            try:
                text = page.get_text("text") or ""
            except Exception as exc:
                raise DocumentError(f"Page {i} could not be read; the PDF may be corrupted.", "corrupted") from exc
            if text.strip():
                pages.append(PageText(number=i, text=text, source="text_layer", char_count=len(text)))
                continue
            if ocr_ok:
                try:
                    tp = page.get_textpage_ocr(full=True)
                    text = page.get_text("text", textpage=tp) or ""
                except Exception:
                    text = ""
                if text.strip():
                    pages.append(PageText(number=i, text=text, source="ocr", char_count=len(text)))
                    warnings.append(f"Page {i} was read with OCR; its text is unverified against the original.")
                    continue
                warnings.append(f"Page {i} has no readable text even after OCR.")
            else:
                warnings.append(f"Page {i} has no text layer (likely scanned) and OCR is unavailable.")
            pages.append(PageText(number=i, text="", source="empty", char_count=0))
        if not any(p.char_count for p in pages):
            raise DocumentError(
                "Nivaaran couldn't find any text in this file. It looks like a photo or scan"
                + (", and the text couldn't be read. Try a clearer, straight-on scan, or the PDF your insurer sent." if ocr_ok else
                   ", and this server can't read scanned text yet. Please upload the PDF your insurer sent (one where you can "
                   "select the text)."),
                "unreadable")
        return Extracted(pages=pages, page_count=doc.page_count, sha256=hashlib.sha256(data).hexdigest(),
                         warnings=warnings, kind="pdf")


def pdf_words(data: bytes) -> list[list[tuple[float, float, str]]]:
    """Return per-page word tuples (x0, y0, word) for table-like parsing of bills."""
    out = []
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        for page in doc:
            out.append([(w[0], w[1], w[4]) for w in page.get_text("words")])
    return out
