import pymupdf
import pytest

from app.ingestion.documents import process_policy_document
from app.ingestion.extract import DocumentError, extract_pdf, sniff_kind, tesseract_available
from app.models import NOT_FOUND, DocType
from tests.conftest import make_pdf


def test_policy_pdf_extracts_clauses_with_metadata(policy):
    assert policy.status in ("processed", "processed_with_warnings")
    assert policy.page_count == 5
    assert len(policy.clauses) == 31
    c = next(c for c in policy.clauses if c.section == "2.5")
    assert c.page == 2 and c.heading == "Diagnostic Investigations"
    assert c.text.startswith("Laboratory investigations, pathology tests")
    assert c.document_id == policy.document_id and c.clause_id == f"{policy.document_id}:2.5"
    assert c.text_source == "text_layer" and c.verification_status == "verified_text_layer"
    assert policy.metadata["policy_number"] == "SYN-HP-2025-000123"
    assert policy.metadata["sum_insured"] == "500000.00"
    assert policy.synthetic is True


def test_running_headers_and_footers_are_not_clause_text(policy):
    for c in policy.clauses:
        assert "SYNTHETIC DEMONSTRATION" not in c.text and "Page " not in c.text


def test_every_page_reference_is_valid(policy, endorsement):
    for d in (policy, endorsement):
        assert all(c.page is not None and 1 <= c.page <= d.page_count for c in d.clauses)


def test_unsupported_file_rejected():
    with pytest.raises(DocumentError) as e:
        sniff_kind(b"\x89PNG\r\n\x1a\n\x00\x00binary")
    assert e.value.code == "unsupported_type"


def test_extension_is_not_trusted():
    with pytest.raises(DocumentError) as e:
        extract_pdf(b"this is plain text pretending to be a pdf")
    assert e.value.code == "unsupported_type"


def test_corrupted_pdf_rejected():
    with pytest.raises(DocumentError) as e:
        extract_pdf(b"%PDF-1.7\n%garbage that is not a real pdf structure\n")
    assert e.value.code in ("corrupted", "empty_document")


def test_empty_file_rejected():
    with pytest.raises(DocumentError) as e:
        extract_pdf(b"")
    assert e.value.code == "empty_file"


@pytest.mark.skipif(tesseract_available(), reason="OCR is installed; the no-OCR failure path cannot be exercised")
def test_scanned_pdf_without_ocr_is_rejected_not_silently_accepted():
    doc = pymupdf.open()
    page = doc.new_page()
    page.draw_rect(pymupdf.Rect(50, 50, 300, 300), fill=(0.5, 0.5, 0.5))  # image-like content, no text layer
    data = doc.tobytes()
    with pytest.raises(DocumentError) as e:
        extract_pdf(data)
    assert e.value.code == "unreadable" and "scanned text" in str(e.value)


def test_text_without_numbered_clauses_rejected(tmp_path):
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Just a letter with no clause numbering at all.")
    with pytest.raises(DocumentError) as e:
        process_policy_document(doc.tobytes(), "letter.pdf", DocType.policy)
    assert e.value.code == "no_clauses"


def test_missing_metadata_reported_not_invented(tmp_path):
    data = make_pdf(tmp_path, "bare.pdf", ["Bare Policy Wording"], [[("1.1 Medicines", "Medicines are payable.")]])
    d = process_policy_document(data, "bare.pdf", DocType.policy)
    assert d.metadata["sum_insured"] == NOT_FOUND
    assert d.metadata["effective_date"] == NOT_FOUND
    assert d.status == "processed_with_warnings"
    assert any("Not found in the provided documents" in w for w in d.warnings)


def test_endorsement_metadata(endorsement):
    m = endorsement.metadata
    assert m["effective_date"] == "2025-10-01" and m["issue_date"] == "2025-09-15"
    assert m["retrospective"] == "no"
    e11 = next(c for c in endorsement.clauses if c.section == "E1.1")
    assert e11.interpretation.replaces == ["2.2"]
    e13 = next(c for c in endorsement.clauses if c.section == "E1.3")
    assert e13.interpretation.overrides == ["4.1", "Annexure I"]


def test_filename_is_sanitised(tmp_path):
    data = make_pdf(tmp_path, "x.pdf", ["P"], [[("1.1 Drugs", "Drugs are payable.")]])
    d = process_policy_document(data, "..\\..\\etc/passwd<script>.pdf", DocType.policy)
    assert "/" not in d.filename and "\\" not in d.filename and "<" not in d.filename
