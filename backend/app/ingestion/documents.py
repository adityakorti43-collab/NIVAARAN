"""Turn an uploaded policy or endorsement into a DocumentRecord with structured, source-referenced clauses."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.ingestion.extract import DocumentError, extract_pdf
from app.ingestion.segment import endorsement_metadata, parse_date, policy_metadata, segment
from app.models import NOT_FOUND, Clause, DocType, DocumentRecord
from app.policy.interpret import interpret


def process_policy_document(data: bytes, filename: str, doc_type: DocType, synthetic: bool = False) -> DocumentRecord:
    if doc_type not in (DocType.policy, DocType.endorsement, DocType.benefit_summary):
        raise DocumentError("Only policy, endorsement and benefit-summary documents are processed into clauses.", "wrong_type")
    ex = extract_pdf(data)
    raw, meta = segment(ex.pages)
    warnings = list(ex.warnings)
    if not raw:
        raise DocumentError("Text was extracted, but no numbered clauses (e.g. '2.1 Heading') were found. Nivaaran "
                            "needs a policy wording with numbered clauses to cite evidence.", "no_clauses")
    md = endorsement_metadata(meta) if doc_type == DocType.endorsement else policy_metadata(meta)
    title = md.get("title", "")
    if doc_type == DocType.endorsement and "endorsement" not in (title + " ".join(meta)).lower():
        warnings.append("Uploaded as an endorsement, but the document does not describe itself as an endorsement.")
    if doc_type == DocType.policy and "endorsement no" in title.lower():
        warnings.append("Uploaded as a policy, but the document title looks like an endorsement.")
    missing = [k for k, v in md.items() if v == NOT_FOUND]
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
        synthetic=synthetic or "synthetic" in " ".join(p.text[:300].lower() for p in ex.pages[:1]),
        metadata=md, clauses=clauses, pages=ex.pages, uploaded_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))


def _safe_name(name: str) -> str:
    base = name.replace("\\", "/").rsplit("/", 1)[-1]
    return "".join(ch for ch in base if ch.isalnum() or ch in "._- ")[:120] or "document"
