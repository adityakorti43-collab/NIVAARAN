"""Turn an uploaded policy or endorsement into a DocumentRecord with structured, source-referenced clauses."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from app.ingestion.extract import DocumentError, extract_pdf
from app.ingestion.segment import endorsement_metadata, parse_date, policy_metadata, segment
from app.models import NOT_FOUND, Clause, DocType, DocumentRecord
from app.policy.interpret import interpret


LABEL = {DocType.policy: "Policy wording", DocType.endorsement: "Endorsement / amendment", DocType.benefit_summary: "Benefits brochure"}
LABEL_A = {DocType.policy: "a policy wording", DocType.endorsement: "an endorsement", DocType.benefit_summary: "a benefits brochure"}


def detect_type(meta: dict[str, str]) -> DocType | None:
    """The type a document states about itself in its title block, when it says so unambiguously; otherwise None."""
    head = (meta.get("title", "") + " " + " ".join(k for k in meta if k != "title")).lower()
    if "endorsement no" in head or "endorsement number" in head:
        return DocType.endorsement
    if "benefits at a glance" in head or "brochure" in head:
        return DocType.benefit_summary
    if "policy wording" in head:
        return DocType.policy
    return None


AMOUNT_LINE_RE = re.compile(r"\d[\d,]*\.\d{2}\s*$")


def looks_like_bill(meta: dict[str, str], pages) -> bool:
    """A hospital bill/invoice: it calls itself a bill and is mostly lines ending in amounts, with no clause wording."""
    head = (meta.get("title", "") + " " + " ".join(meta)).lower()
    text = "\n".join(p.text for p in pages)
    named = bool(re.search(r"\b(itemi[sz]ed (final )?bill|final bill|hospital bill|tax invoice|invoice|bill (no|number|date))\b", head + " " + text[:600].lower()))
    amount_lines = sum(bool(AMOUNT_LINE_RE.search(ln.strip())) for ln in text.splitlines())
    clause_words = len(re.findall(r"\b(payable|excluded|exclusion|covered|insured|policyholder|sum insured)\b", text, re.I))
    return named and amount_lines >= 5 and clause_words < 3


def guess_type(meta: dict[str, str], raw: list[dict]) -> DocType:
    """Automatic type for an upload: what the document says about itself, then what its title suggests, then what its
    clauses do (an amendment mostly replaces or overrides other clauses). Defaults to a policy wording."""
    stated = detect_type(meta)
    if stated:
        return stated
    title = meta.get("title", "").lower()
    if re.search(r"\b(endorsement|amendment|rider|addendum)\b", title):
        return DocType.endorsement
    if re.search(r"\b(brochure|prospectus|key features|summary of benefits|benefit summary|customer information sheet)\b", title):
        return DocType.benefit_summary
    amending = sum(bool(re.search(r"replaces clause|notwithstanding clause|this endorsement", c.get("text", ""), re.I)) for c in raw)
    if raw and len(raw) <= 12 and amending >= max(1, len(raw) // 2):
        return DocType.endorsement
    return DocType.policy


def process_policy_document(data: bytes, filename: str, doc_type: DocType | None, synthetic: bool = False) -> DocumentRecord:
    """doc_type None means: work out the type from the document itself."""
    if doc_type is not None and doc_type not in (DocType.policy, DocType.endorsement, DocType.benefit_summary):
        raise DocumentError("Only policy, endorsement and benefit-summary documents are processed into clauses.", "wrong_type")
    ex = extract_pdf(data)
    raw, meta = segment(ex.pages)
    warnings = list(ex.warnings)
    if not raw:
        raise DocumentError("The file opened, but it contains too little readable text to analyse. If it is a scan or a photo, "
                            "upload a clearer copy (or the PDF from your insurer).", "no_clauses")
    if meta.get("_segmentation") == "paragraphs":
        warnings.append("This document has no clause numbers, so Nivaaran numbered its paragraphs (P1, P2, ...) to cite them. "
                        "Interpretation may be less precise than for a numbered policy wording.")
    if looks_like_bill(meta, ex.pages):
        raise DocumentError("This looks like a hospital bill, not an insurance document. Add bills when you create a claim: "
                            "Claim workspace → New claim → Upload itemised bill.", "is_bill")
    if doc_type is None:
        doc_type = guess_type(meta, raw)
    else:
        detected = detect_type(meta)
        if detected and detected != doc_type:
            # an explicit choice is kept (it is the user's deliberate correction), but the mismatch is reported
            warnings.append(f"Saved as '{LABEL[doc_type]}' as you chose, although the document describes itself as {LABEL_A[detected]}.")
    md = endorsement_metadata(meta) if doc_type == DocType.endorsement else policy_metadata(meta)
    title = md.get("title", "")
    if doc_type == DocType.endorsement and "endorsement" not in (title + " ".join(meta)).lower():
        warnings.append("Uploaded as an endorsement, but the document does not describe itself as an endorsement.")
    if doc_type == DocType.policy and "endorsement no" in title.lower():
        warnings.append("Uploaded as a policy, but the document title looks like an endorsement.")
    missing = [k for k, v in md.items() if v == NOT_FOUND]
    if doc_type == DocType.benefit_summary:   # a brochure isn't expected to name the policyholder or coverage history
        missing = [k for k in missing if k not in ("policyholder", "continuous_coverage_since")]
    if missing:
        warnings.append("Not found in the provided documents: " + ", ".join(m.replace("_", " ") for m in missing) + ".")
    doc_id = f"{ {DocType.policy: 'pol', DocType.endorsement: 'end'}.get(doc_type, 'sum')}-{uuid.uuid4().hex[:8]}"
    ocr_pages = {p.number for p in ex.pages if p.source == "ocr"}
    eff = parse_date(md.get("effective_date")) if md.get("effective_date") not in (None, NOT_FOUND) else None
    clauses = []
    for c in raw:
        it = interpret(c["heading"], c["text"], c["group"])
        from_ocr = c["page"] in ocr_pages
        clauses.append(Clause(
            clause_id=f"{doc_id}:{c['section']}", document_id=doc_id, doc_type=doc_type, section=c["section"],
            heading=c["heading"], text=c["text"], page=c["page"], group=c["group"], effective_date=eff,
            text_source="ocr" if from_ocr else "text_layer",
            extraction_confidence="medium" if from_ocr else ("high" if it.category.value != "other" else "low"),
            verification_status="ocr_unverified" if from_ocr else "verified_text_layer", interpretation=it))
    if any(c.interpretation.category.value == "other" for c in clauses):
        warnings.append(f"{sum(c.interpretation.category.value == 'other' for c in clauses)} clause(s) could not be "
                        "interpreted and are kept for reference only.")
    sections = [c.section for c in clauses]
    dups = {s for s in sections if sections.count(s) > 1}
    if dups:
        warnings.append("Duplicate clause numbers found: " + ", ".join(sorted(dups)) + "; review the source document.")
    return DocumentRecord(
        document_id=doc_id, doc_type=doc_type, filename=_safe_name(filename), size_bytes=len(data), sha256=ex.sha256,
        page_count=ex.page_count, status="processed_with_warnings" if warnings else "processed", warnings=warnings,
        synthetic=synthetic,
        metadata=md, clauses=clauses, pages=ex.pages, uploaded_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))


def _safe_name(name: str) -> str:
    base = name.replace("\\", "/").rsplit("/", 1)[-1]
    return "".join(ch for ch in base if ch.isalnum() or ch in "._- ")[:120] or "document"
