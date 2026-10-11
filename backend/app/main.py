"""Nivaaran API — Insurance clarity. Backed by evidence.

Every data endpoint resolves the signed-in user on the server (session cookie -> app.auth.require_user) and
enforces ownership on each record it touches. Records owned by someone else return 404, so identifiers cannot be
used to probe for other users' data.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal, Optional
from urllib.parse import urlencode

from fastapi import Cookie, Depends, FastAPI, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from app import env  # noqa: F401  (reads .env before any other module reads settings)
from app import __version__, auth, policy_tools, social, store, translate, tts
from app.adjudication.adjudicate import adjudicate, retriever_for
from app.adjudication.compare import compare
from app.auth import User, require_user
from app.bills.parse import build_bill, parse_bill_bytes, revise_bill
from app.config import BACKEND_DIR, CORS_ORIGINS, EVAL_DIR, MAX_UPLOAD_BYTES, UPLOAD_DIR, ensure_dirs, log
from app.costs import costs as cost_mod
from app.ingestion.documents import process_policy_document
from app.ingestion.extract import DocumentError, sniff_kind, tesseract_available
from app.models import AnalysisResult, Bill, Claim, ClaimFacts, DocType, DocumentRecord, Hypotheticals, NOT_FOUND
from app.policy.versions import active_clauses, build_versions
from app.qa import llm
from app.qa.assistant import answer as qa_answer
from app.reports.pdf import render_pdf
from app.retrieval.retrievers import embedding_backend, reranker_available
from app.retrieval.text import normalize_item
from app.verification.verify import ItemContext, verify

def _startup():
    removed = auth.cleanup_demo_users()
    if removed:
        log.info("Removed %d expired demo workspaces", removed)

    def warm():
        try:
            from app.retrieval.retrievers import warm_up
            warm_up()
            log.info("Retrieval models loaded")
        except Exception as exc:  # the first request will load (or report) them instead
            log.warning("Model warm-up skipped: %s", exc)

    import threading
    threading.Thread(target=warm, daemon=True, name="model-warmup").start()


@asynccontextmanager
async def _lifespan(_: FastAPI):
    _startup()
    yield


app = FastAPI(title="Nivaaran API", version=__version__, lifespan=_lifespan,
              description="Insurance clarity. Backed by evidence. Decision-support estimates only; no guarantee of insurer approval.")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True,
                   allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["Content-Type"])
ensure_dirs()


@app.exception_handler(DocumentError)
async def _doc_err(_: Request, exc: DocumentError):
    return JSONResponse(status_code=422, content={"error": exc.code, "message": str(exc)})


@app.exception_handler(ValueError)
async def _val_err(_: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"error": "invalid_input", "message": str(exc)})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _404(what: str):
    raise HTTPException(status_code=404, detail=f"{what} not found")


async def _read_upload(file: UploadFile) -> bytes:
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise DocumentError(f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.", "too_large")
    return data


def _image_to_pdf(data: bytes) -> bytes:
    """JPEG/PNG uploads are wrapped as a one-page PDF so the same extraction (and OCR, when installed) applies."""
    import pymupdf
    try:
        with pymupdf.open(stream=data) as img:
            return img.convert_to_pdf()
    except Exception as exc:
        raise DocumentError("The image could not be read. Upload a clear JPEG or PNG, or a PDF.", "corrupted") from exc


def _sniff_upload(data: bytes) -> str:
    if data[:3] == b"\xff\xd8\xff" or data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image"
    return sniff_kind(data)


# ------------------------------------------------------------------ ownership helpers

def _doc(doc_id: str, user: User) -> DocumentRecord:
    d = store.get_document(doc_id)
    if not d or d.owner_id != user.id:
        _404("Document")
    return d


def _claim(claim_id: str, user: User) -> Claim:
    c = store.get_claim(claim_id)
    if not c or c.owner_id != user.id:
        _404("Claim")
    return c


def _doc_summary(d: DocumentRecord, with_clauses: bool = True) -> dict:
    out = d.model_dump(mode="json", exclude={"pages", "owner_id"} | (set() if with_clauses else {"clauses"}))
    out["clause_count"] = len(d.clauses)
    out["ocr_pages"] = [p.number for p in d.pages if p.source == "ocr"]
    out["empty_pages"] = [p.number for p in d.pages if p.source == "empty"]
    return out


def _existing_identical(data: bytes, doc_type: DocType, user: User) -> Optional[DocumentRecord]:
    """Identical uploads by the same user reuse the stored record (no duplicate endorsements in the version registry)."""
    digest = hashlib.sha256(data).hexdigest()
    return next((d for d in store.list_documents(user.id) if d.sha256 == digest and d.doc_type == doc_type), None)


def _docs_for(claim: Claim) -> dict[str, DocumentRecord]:
    docs = {}
    for did in [claim.policy_document_id, *claim.endorsement_ids, *claim.benefit_summary_ids]:
        d = store.get_document(did)
        if not d or d.owner_id != claim.owner_id:
            raise HTTPException(status_code=409, detail=f"Document {did} referenced by the claim no longer exists")
        docs[did] = d
    return docs


def _current(claim_id: str, user: User) -> tuple[Claim, AnalysisResult, dict[str, DocumentRecord]]:
    c = _claim(claim_id, user)
    an = store.list_analyses(claim_id)
    if not an:
        raise HTTPException(status_code=409, detail="Claim has not been analysed yet")
    return c, an[-1], _docs_for(c)


# ------------------------------------------------------------------ system

@app.get("/api/health")
def health():
    return {"status": "ok", "product": "Nivaaran", "version": __version__}


@app.get("/api/system")
def system():
    return {"product": "Nivaaran", "tagline": "Insurance clarity. Backed by evidence.", "version": __version__,
            "embedding_backend": embedding_backend(), "reranker_available": reranker_available(),
            "ocr_available": tesseract_available(), "max_upload_mb": MAX_UPLOAD_BYTES // (1024 * 1024),
            "ai_mode": llm.mode_label(),
            "external_services": ("Claude API (answers reworded from cited evidence only)" if llm.enabled() else
                                  "None. Documents are processed locally; no document text is sent to external models.")}


# ------------------------------------------------------------------ auth: one way in (Google)

def _login_error(message: str, next_: str = "") -> RedirectResponse:
    q = {"error": message} | ({"next": next_} if next_ else {})
    return RedirectResponse(f"/login?{urlencode(q)}", status_code=303)


class SpeakBody(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    lang: Literal["en", "hi"] = "en"


class PageTranslateBody(BaseModel):
    lang: str = Field(max_length=5)
    texts: list[str] = Field(max_length=120)


@app.get("/api/translate/languages")
def translate_languages():
    return translate.languages()


@app.post("/api/translate")
def translate_texts(body: PageTranslateBody, request: Request, nivaaran_session: Optional[str] = Cookie(default=None)):
    """Translate visible page text. Open to signed-out visitors too (the landing page), with a per-client hourly cap."""
    client = (nivaaran_session or "")[:16] or (request.client.host if request.client else "anon")
    return {"lang": body.lang, "translations": translate.translate(body.texts, body.lang, client), "rtl": body.lang in translate.RTL}


@app.get("/api/speech")
def speech_status(user: User = Depends(require_user)):
    """Whether the natural (neural) voice is available; otherwise the page uses the browser's voices."""
    return {"neural": tts.enabled(), "provider": tts.provider()}


@app.post("/api/speech")
def speech(body: SpeakBody, user: User = Depends(require_user)):
    audio = tts.synthesize(body.text, body.lang)
    return Response(content=audio, media_type="audio/wav" if audio[:4] == b"RIFF" else "audio/mpeg", headers={"Cache-Control": "private, max-age=86400"})


@app.get("/api/auth/providers")
def auth_providers():
    """Which sign-in methods this server has credentials for. The page shows both and explains any that are not set up."""
    return social.configured()


@app.get("/api/auth/me")
def me(user: User = Depends(require_user)):
    return {"user": user.model_dump()}


class ProfileBody(BaseModel):
    name: Optional[str] = Field(default=None, max_length=80)


@app.patch("/api/auth/me")
def update_me(body: ProfileBody, user: User = Depends(require_user)):
    return {"user": auth.update_profile(user, body.name).model_dump()}


@app.post("/api/auth/logout")
def logout(response: Response, nivaaran_session: Optional[str] = Cookie(default=None)):
    auth.end_session(response, nivaaran_session)
    return {"signed_out": True}


@app.delete("/api/auth/me")
def delete_me(response: Response, user: User = Depends(require_user), nivaaran_session: Optional[str] = Cookie(default=None)):
    auth.delete_account(user)
    auth.end_session(response, nivaaran_session)
    return {"deleted": True, "note": "Your account, documents, claims, analyses, chats and reports were deleted (standard deletion; no secure wipe)."}


@app.get("/api/auth/google/start")
def google_start(request: Request, next: Optional[str] = None, link: bool = False, app: bool = False, nivaaran_session: Optional[str] = Cookie(default=None)):
    """Begin Google sign-in. With link=1 (from Settings, signed in) the Google identity is added to the current account."""
    link_user = auth.user_from_token(nivaaran_session) if link else None
    if link and not link_user:
        return _login_error("Please sign in before linking a Google account.", "/settings")
    try:
        return RedirectResponse(social.authorize_url(next, link_user, app=app, base=social.base_for(str(request.base_url))), status_code=303)
    except HTTPException as exc:
        return _login_error(str(exc.detail), next or "")


@app.get("/api/auth/google/callback")
def google_callback(request: Request, code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None):
    if error:
        return _login_error("Google sign-in was cancelled." if error in ("access_denied",) else "Google sign-in didn't complete. Please try again.")
    try:
        st = social.consume_state(state)
        if not code:
            raise HTTPException(status_code=400, detail="Sign-in was interrupted. Please try again.")
        u = social.google_user(social.exchange_code(code, st.verifier, social.base_for(str(request.base_url))), st.link_user_id)
    except HTTPException as exc:
        return _login_error(str(exc.detail))
    if st.app:
        # Signed in through the phone's browser for the Android/iOS app: hand a single-use, 15-minute sign-in link back
        # to the app, which opens it inside its own view (where the session cookie then lives).
        q = {"next": "/settings?linked=google"} if st.link_user_id else {"token": auth.create_login_link(u.id), "next": st.next}
        return RedirectResponse(f"{social.APP_SCHEME}://auth?{urlencode(q)}", status_code=303)
    if st.link_user_id:   # linking from Settings keeps the existing session
        return RedirectResponse("/settings?linked=google", status_code=303)
    resp = RedirectResponse(st.next, status_code=303)
    auth.start_session(resp, u.id)
    return resp


@app.get("/api/auth/login-link")
def login_link(token: str, next: Optional[str] = None):
    """Operator one-time sign-in links (python -m app.manage login-link ...). Single use, 15 minutes."""
    uid = auth.consume_login_link(token)
    if not uid:
        return _login_error("This sign-in link has expired or was already used.")
    resp = RedirectResponse(social.safe_next(next) if next else "/dashboard", status_code=303)
    auth.start_session(resp, uid)
    return resp


# ------------------------------------------------------------------ dashboard overview

@app.get("/api/me/overview")
def overview(user: User = Depends(require_user)):
    from app.fairness.scan import scan
    claims_out, activity, missing, pending, discrepancies = [], [], [], [], 0
    for c in store.list_claims(user.id):
        an = store.list_analyses(c.claim_id)
        last = an[-1] if an else None
        entry = {"claim_id": c.claim_id, "title": c.title, "synthetic": c.synthetic, "admission_date": c.admission_date,
                 "total_billed": str(c.bill.computed_total), "created_at": c.created_at}
        if last:
            entry.update({"payable": [str(last.summary.payable_low), str(last.summary.payable_high)],
                          "version": last.version.selected.label if last.version.selected else None,
                          "review_items": sum(r.manual_review for r in last.rows)})
            for r in last.rows:
                if r.manual_review:
                    pending.append({"claim_id": c.claim_id, "claim": c.title, "item": r.original_description, "status": r.status})
                for m in r.missing_information:
                    missing.append({"claim_id": c.claim_id, "claim": c.title, "need": m})
            try:
                f = scan(c, last, _docs_for(c))
                n = sum(1 for x in f["findings"] if x["category"] in ("representation_gap", "document_contradiction", "calculation_inconsistency"))
                entry["discrepancies"] = n
                discrepancies += n
            except HTTPException:
                entry["discrepancies"] = None
            for a in an[-4:]:
                activity.append({"at": a.created_at, "claim": c.title, "claim_id": c.claim_id, "what": a.cause})
        claims_out.append(entry)
    docs = store.list_documents(user.id)
    activity.sort(key=lambda x: x["at"], reverse=True)
    return {"user": user.model_dump(), "claims": claims_out,
            "documents": [{"document_id": d.document_id, "title": d.metadata.get("title", d.filename), "doc_type": d.doc_type.value,
                           "status": d.status, "clause_count": len(d.clauses), "synthetic": d.synthetic, "uploaded_at": d.uploaded_at} for d in docs],
            "pending_reviews": pending[:20], "missing_documents": missing[:20], "discrepancy_count": discrepancies,
            "reports": store.list_reports(user.id)[:10], "activity": activity[:12]}


# ------------------------------------------------------------------ documents

@app.post("/api/documents")
async def upload_document(file: UploadFile = File(...), doc_type: Literal["auto", "policy", "endorsement", "benefit_summary"] = Form("auto"),
                          user: User = Depends(require_user)):
    data = await _read_upload(file)
    if not data.strip():
        raise DocumentError("This file is empty. Choose the PDF of your policy, endorsement or brochure.", "empty_file")
    if not (data[:5] == b"%PDF-" or data[:3] == b"\xff\xd8\xff" or data[:8] == b"\x89PNG\r\n\x1a\n"):
        raise DocumentError("This file isn't a PDF, JPEG or PNG. Upload the PDF of your policy, endorsement or brochure.", "unsupported_type")
    kind = _sniff_upload(data)
    if kind == "image":
        data = _image_to_pdf(data)
    elif kind != "pdf":
        raise DocumentError("Upload a PDF, JPEG or PNG document.", "unsupported_type")
    doc = process_policy_document(data, file.filename or "document.pdf", None if doc_type == "auto" else DocType(doc_type))
    # Uploading the same file again is treated as a fresh upload: earlier copies are replaced by this one, so no stale
    # record is kept. The one exception is a copy that a saved claim is built on (deleting it would break the claim);
    # that copy is kept and returned as it is, with no extra message.
    digest = hashlib.sha256(data).hexdigest()
    in_use = {i for c in store.list_claims(user.id) for i in [c.policy_document_id, *c.endorsement_ids, *c.benefit_summary_ids]}
    copies = [d for d in store.list_documents(user.id) if d.sha256 == digest]
    kept = next((d for d in copies if d.document_id in in_use and d.doc_type == doc.doc_type), None)
    if kept:
        return _doc_summary(kept)
    for old in copies:
        if old.document_id not in in_use:
            store.delete_document(old.document_id)
    doc.owner_id = user.id
    store.save_document(doc, data)
    log.info("User %s processed %s %s: %d clauses", user.id, doc_type, doc.document_id, len(doc.clauses))
    return _doc_summary(doc)


@app.get("/api/documents")
def list_documents(user: User = Depends(require_user)):
    return [_doc_summary(d, with_clauses=False) for d in store.list_documents(user.id)]


@app.get("/api/documents/{doc_id}")
def get_document(doc_id: str, user: User = Depends(require_user)):
    return _doc_summary(_doc(doc_id, user))


@app.get("/api/documents/{doc_id}/download")
def download_document(doc_id: str, user: User = Depends(require_user)):
    d = _doc(doc_id, user)
    src = UPLOAD_DIR / f"{doc_id}.bin"
    if not src.exists():
        _404("Stored file")
    return Response(content=src.read_bytes(), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{d.filename}"', "Cache-Control": "private, no-store"})


@app.get("/api/documents/{doc_id}/pages/{page_no}.png")
def document_page_image(doc_id: str, page_no: int, highlight: Optional[str] = Query(None, max_length=120),
                        zoom: float = Query(1.6, ge=0.5, le=3.0), user: User = Depends(require_user)):
    """Render one page of the stored source PDF, optionally highlighting a clause. Rendering only."""
    import pymupdf
    d = _doc(doc_id, user)
    src = UPLOAD_DIR / f"{doc_id}.bin"
    if not src.exists():
        raise HTTPException(status_code=404, detail="The original file for this document is not stored")
    if not 1 <= page_no <= d.page_count:
        raise HTTPException(status_code=404, detail="Page out of range")
    with pymupdf.open(src) as pdf:
        page = pdf[page_no - 1]
        if highlight:
            clause = next((c for c in d.clauses if c.clause_id == highlight and c.page == page_no), None)
            if clause:
                rects = page.search_for(f"{clause.section} {clause.heading}")
                words = clause.text.split()
                for i in range(0, min(len(words), 60), 6):
                    rects += page.search_for(" ".join(words[i:i + 6]))
                for r in rects:
                    page.draw_rect(r + (-2, -1, 2, 1), color=None, fill=(0.21, 0.84, 1.0), fill_opacity=0.28, overlay=True)
        png = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False).tobytes("png")
    return Response(content=png, media_type="image/png", headers={"Cache-Control": "private, max-age=300"})


@app.get("/api/documents/{doc_id}/summary")
def policy_summary(doc_id: str, lang: Literal["en", "hi", "mr"] = "en", user: User = Depends(require_user)):
    """A plain-language summary of the whole document for read-aloud, in English, Hindi or Marathi."""
    from app.qa.speech import summarise
    doc = _doc(doc_id, user)
    return summarise(doc.clauses or [], doc.metadata.get("title") or doc.filename, lang, _sum_insured(doc))


def _sum_insured(doc: DocumentRecord):
    v = (doc.metadata or {}).get("sum_insured")
    try:
        return Decimal(str(v).replace(",", "")) if v and NOT_FOUND not in str(v) else None
    except Exception:
        return None


@app.get("/api/documents/{doc_id}/clauses/{section}/explain")
def explain_clause(doc_id: str, section: str, lang: Literal["en", "hi", "mr"] = "en", user: User = Depends(require_user)):
    """Plain-language summary of one clause in English, Hindi or Marathi, for reading aloud."""
    from app.qa.speech import explain
    d = _doc(doc_id, user)
    c = next((x for x in d.clauses if x.section == section), None) or _404("Clause")
    return {"lang": lang, "text": explain(c, lang), "original": c.text, "source": "structured reading of the clause (deterministic)"}


class TranslateBody(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


@app.post("/api/translate/hi")
def translate_hindi(body: TranslateBody, user: User = Depends(require_user)):
    out = llm.translate_hi(body.text)
    if not out:
        raise HTTPException(status_code=409, detail="Hindi translation of free-text answers needs the AI provider configured. "
                                                    "Clause explanations are always available in Hindi.")
    return {"lang": "hi", "text": out}


@app.delete("/api/documents/{doc_id}")
def delete_document(doc_id: str, with_claims: bool = False, user: User = Depends(require_user)):
    """Delete a document. If saved claims are built on it, the user is told which; with_claims=true (after the user
    confirms) deletes those claims and their analyses too."""
    _doc(doc_id, user)
    claims = [c for c in store.list_claims(user.id) if doc_id in [c.policy_document_id, *c.endorsement_ids, *c.benefit_summary_ids]]
    if claims and not with_claims:
        names = ", ".join(f"'{c.title}'" for c in claims)
        return JSONResponse(status_code=409, content={"error": "document_in_use", "claims": [c.title for c in claims],
                                                      "message": f"{len(claims)} saved claim{'s' if len(claims) > 1 else ''} ({names}) use{'' if len(claims) > 1 else 's'} this document."})
    for c in claims:
        store.delete_claim(c.claim_id)
    store.delete_document(doc_id)
    return {"deleted": doc_id, "deleted_claims": [c.claim_id for c in claims],
            "note": "The stored upload and its extracted data were deleted (standard file deletion)."}


@app.get("/api/policies/{policy_id}/versions")
def policy_versions(policy_id: str, endorsement_ids: Optional[str] = None, user: User = Depends(require_user)):
    pol = _doc(policy_id, user)
    if pol.doc_type != DocType.policy:
        raise HTTPException(status_code=400, detail="Not a policy document")
    ids = [e for e in (endorsement_ids.split(",") if endorsement_ids else
                       [d.document_id for d in store.list_documents(user.id) if d.doc_type == DocType.endorsement]) if e]
    ends = [_doc(e, user) for e in ids]
    versions, conflicts = build_versions(pol, ends)
    docs = {pol.document_id: pol} | {e.document_id: e for e in ends}
    return {"versions": [v.model_dump(mode="json") | {"active_clause_count": len(active_clauses(v, docs))} for v in versions],
            "conflicts": conflicts}


# ------------------------------------------------------------------ bills

@app.post("/api/bills/parse")
async def parse_bill(file: UploadFile = File(...), user: User = Depends(require_user)):
    data = await _read_upload(file)
    kind = _sniff_upload(data)
    if kind == "image":
        data, kind = _image_to_pdf(data), "pdf"
    raw = parse_bill_bytes(data, kind)
    if kind == "pdf" and not raw["items"]:
        from app.ingestion.extract import extract_pdf
        extract_pdf(data)  # raises a clear "unreadable / OCR unavailable" error for scanned images
    bill = build_bill(raw, synthetic=False)
    return bill.model_dump(mode="json") | {"extraction": "extracted — review and correct before analysing", "breakdown": _bill_breakdown(bill)}


def _bill_breakdown(bill) -> list[dict]:
    """Bill total split by kind of charge (room, medicines, tests…), largest first, for the bill summary chart."""
    from app.retrieval.text import normalize_item
    groups: dict[str, dict] = {}
    for it in bill.items:
        n = normalize_item(it.description, it.category_hint)
        g = groups.setdefault(n.category, {"category": n.category, "label": n.category_label, "amount": Decimal("0"), "count": 0})
        g["amount"] += Decimal(str(it.amount)); g["count"] += 1
    return [g | {"amount": f"{g['amount']:.2f}"} for g in sorted(groups.values(), key=lambda g: g["amount"], reverse=True)]


class ManualItem(BaseModel):
    description: str = Field(min_length=1, max_length=200)
    amount: Decimal = Field(ge=0)
    quantity: Decimal = Field(default=Decimal("1"), gt=0)
    unit_price: Optional[Decimal] = Field(default=None, ge=0)
    service_date: Optional[date] = None
    category: Optional[str] = None


class ItemEdit(BaseModel):
    """One bill line as the user wants it. `item_id` refers to an existing line; omit it to add a line."""
    item_id: Optional[str] = Field(default=None, max_length=20)
    description: str = Field(min_length=1, max_length=200)
    amount: Decimal = Field(ge=0)
    quantity: Decimal = Field(default=Decimal("1"), gt=0)
    unit_price: Optional[Decimal] = Field(default=None, ge=0)
    service_date: Optional[date] = None


def _edits(items) -> list[dict]:
    return [{"item_id": i.item_id, "description": i.description, "amount": str(i.amount), "quantity": str(i.quantity),
             "unit_price": None if i.unit_price is None else str(i.unit_price),
             "service_date": i.service_date.isoformat() if i.service_date else None} for i in items]


class ClaimCreate(BaseModel):
    title: str = Field(default="New claim", max_length=120)
    policy_document_id: str
    endorsement_ids: list[str] = Field(default_factory=list)
    benefit_summary_ids: list[str] = Field(default_factory=list)
    bill: Optional[Bill] = None
    bill_items: Optional[list[ItemEdit]] = Field(default=None, max_length=500)   # user corrections to `bill` before analysis
    items: Optional[list[ManualItem]] = None
    admission_date: date
    discharge_date: Optional[date] = None
    diagnosis: str = NOT_FOUND
    facts: ClaimFacts = Field(default_factory=ClaimFacts)


def _manual_bill(items: list[ManualItem]) -> Bill:
    raw = {"items": [{"line_no": i, "description": it.description, "amount": str(it.amount), "quantity": str(it.quantity),
                      "unit_price": str(it.unit_price) if it.unit_price is not None else None,
                      "service_date": it.service_date.isoformat() if it.service_date else None, "category": it.category}
                     for i, it in enumerate(items, start=1)], "stated_total": None}
    bill = build_bill(raw)
    for i in bill.items:
        i.source = "manual"
    return bill


def _analyse_and_store(claim: Claim, cause: str) -> tuple[AnalysisResult, Optional[dict]]:
    docs = _docs_for(claim)
    prev = store.list_analyses(claim.claim_id)
    a = adjudicate(claim, docs, cause=cause)
    store.save_analysis(a)
    cmp = None
    if prev:
        cmp = compare(prev[-1], a, cause)
        store.save_comparison(cmp["comparison_id"], claim.claim_id, cmp["created_at"], cmp)
    return a, cmp


@app.post("/api/claims")
def create_claim(body: ClaimCreate, user: User = Depends(require_user)):
    pol = _doc(body.policy_document_id, user)
    if pol.doc_type != DocType.policy:
        raise HTTPException(status_code=400, detail="policy_document_id must refer to one of your uploaded policies")
    for e in body.endorsement_ids:
        if _doc(e, user).doc_type != DocType.endorsement:
            raise HTTPException(status_code=400, detail=f"{e} is not one of your endorsements")
    for s in body.benefit_summary_ids:
        if _doc(s, user).doc_type != DocType.benefit_summary:
            raise HTTPException(status_code=400, detail=f"{s} is not one of your benefit summaries")
    if body.bill is None and not body.items:
        raise HTTPException(status_code=400, detail="Provide a parsed bill or at least one manual bill item")
    if body.bill is not None:
        # Totals and checks are recomputed on the server; a parsed bill's own totals are not trusted.
        bill, _ = revise_bill(body.bill, _edits(body.bill.items))
        if body.bill_items is not None:
            bill, _ = revise_bill(bill, _edits(body.bill_items), reviewed_at=_now())
    else:
        bill = _manual_bill(body.items or [])
    if body.discharge_date and body.discharge_date < body.admission_date:
        raise HTTPException(status_code=400, detail="Discharge date cannot be before admission date")
    claim = Claim(claim_id=f"clm-{uuid.uuid4().hex[:10]}", title=body.title, policy_document_id=body.policy_document_id,
                  endorsement_ids=body.endorsement_ids, benefit_summary_ids=body.benefit_summary_ids, bill=bill,
                  admission_date=body.admission_date, discharge_date=body.discharge_date, diagnosis=body.diagnosis, facts=body.facts,
                  synthetic=bill.synthetic or pol.synthetic, created_at=_now(), owner_id=user.id)
    store.save_claim(claim)
    a, _ = _analyse_and_store(claim, "Initial analysis")
    return {"claim": claim.model_dump(mode="json", exclude={"owner_id"}), "analysis": a.model_dump(mode="json")}


# ------------------------------------------------------------------ policy-only tools (before there is a claim)

def _policy(pid: str, user: User) -> DocumentRecord:
    pol = _doc(pid, user)
    if pol.doc_type != DocType.policy:
        raise HTTPException(status_code=400, detail="Choose one of your policy wordings.")
    return pol


class EstimateBody(BaseModel):
    items: list[ManualItem] = Field(min_length=1, max_length=60)
    admission_date: date
    discharge_date: Optional[date] = None
    diagnosis: str = Field(default="", max_length=200)
    facts: ClaimFacts = Field(default_factory=ClaimFacts)


@app.post("/api/policies/{policy_id}/estimate")
def policy_estimate(policy_id: str, body: EstimateBody, user: User = Depends(require_user)):
    """The real claim calculation on a hypothetical stay. Nothing is saved."""
    pol = _policy(policy_id, user)
    if body.discharge_date and body.discharge_date < body.admission_date:
        raise HTTPException(status_code=400, detail="Discharge date cannot be before admission date")
    docs = {pol.document_id: pol} | {d.document_id: d for d in store.list_documents(user.id) if d.doc_type == DocType.endorsement}
    _, a = policy_tools.estimate(pol, docs, _manual_bill(body.items), body.admission_date, body.discharge_date, body.diagnosis, body.facts, user.id)
    return {"analysis": a.model_dump(mode="json"), "saved": False}


class PolicyQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=500)


@app.post("/api/policies/{policy_id}/ask")
def policy_ask(policy_id: str, body: PolicyQuestion, user: User = Depends(require_user)):
    return policy_tools.ask(_policy(policy_id, user), body.question)


@app.get("/api/policies/{policy_id}/checklist")
def policy_checklist(policy_id: str, user: User = Depends(require_user)):
    return policy_tools.checklist(_policy(policy_id, user))


@app.get("/api/policies/{policy_id}/summary.pdf")
def policy_summary_pdf(policy_id: str, user: User = Depends(require_user)):
    pol = _policy(policy_id, user)
    name = re.sub(r"[^A-Za-z0-9]+", "_", (pol.metadata.get("title") or "policy"))[:60].strip("_") or "policy"
    return Response(content=policy_tools.summary_pdf(pol), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{name}_summary.pdf"'})


@app.get("/api/claims")
def list_claims(user: User = Depends(require_user)):
    out = []
    for c in store.list_claims(user.id):
        an = store.list_analyses(c.claim_id)
        last = an[-1] if an else None
        out.append({"claim_id": c.claim_id, "title": c.title, "created_at": c.created_at, "synthetic": c.synthetic,
                    "admission_date": c.admission_date, "items": len(c.bill.items), "total_billed": str(c.bill.computed_total),
                    "latest": None if not last else {
                        "analysis_id": last.analysis_id, "version": last.version.selected.label if last.version.selected else None,
                        "payable_low": str(last.summary.payable_low), "payable_high": str(last.summary.payable_high),
                        "patient_low": str(last.summary.patient_low), "patient_high": str(last.summary.patient_high),
                        "review_items": sum(r.manual_review for r in last.rows), "created_at": last.created_at}})
    return out


@app.get("/api/claims/{claim_id}")
def get_claim(claim_id: str, user: User = Depends(require_user)):
    c = _claim(claim_id, user)
    an = store.list_analyses(claim_id)
    return {"claim": c.model_dump(mode="json", exclude={"owner_id"}), "analysis": an[-1].model_dump(mode="json") if an else None,
            "history": [{"analysis_id": a.analysis_id, "created_at": a.created_at, "cause": a.cause,
                         "version": a.version.selected.label if a.version.selected else None,
                         "payable_low": str(a.summary.payable_low), "payable_high": str(a.summary.payable_high)} for a in an],
            "comparisons": store.list_comparisons(claim_id)}


@app.delete("/api/claims/{claim_id}")
def delete_claim(claim_id: str, user: User = Depends(require_user)):
    _claim(claim_id, user)
    store.delete_claim(claim_id)
    return {"deleted": claim_id}


class ClaimUpdate(BaseModel):
    facts: Optional[ClaimFacts] = None
    admission_date: Optional[date] = None
    discharge_date: Optional[date] = None
    endorsement_ids: Optional[list[str]] = None
    bill: Optional[Bill] = None                                   # legacy: treated as a full list of line edits
    bill_items: Optional[list[ItemEdit]] = Field(default=None, max_length=500)
    confirm_bill: bool = False                                    # record that the user reviewed the line items
    cause: Optional[str] = Field(default=None, max_length=200)


@app.patch("/api/claims/{claim_id}")
def update_claim(claim_id: str, body: ClaimUpdate, user: User = Depends(require_user)):
    c = _claim(claim_id, user)
    causes = []
    if body.facts is not None and body.facts != c.facts:
        changed = [k for k in ClaimFacts.model_fields if getattr(body.facts, k) != getattr(c.facts, k)]
        causes.append("Claim facts updated (" + ", ".join(k.replace("_", " ") for k in changed) + ")")
        c.facts = body.facts
    if body.admission_date and body.admission_date != c.admission_date:
        causes.append(f"Treatment date changed {c.admission_date} -> {body.admission_date}")
        c.admission_date = body.admission_date
    if body.discharge_date and body.discharge_date != c.discharge_date:
        causes.append(f"Discharge date changed to {body.discharge_date}")
        c.discharge_date = body.discharge_date
    if body.endorsement_ids is not None and body.endorsement_ids != c.endorsement_ids:
        ends = [_doc(e, user) for e in body.endorsement_ids]
        if any(d.doc_type != DocType.endorsement for d in ends):
            raise HTTPException(status_code=400, detail="Only endorsements can be attached here")
        added = [d.metadata.get("endorsement_number", d.document_id) for d in ends if d.document_id not in c.endorsement_ids]
        removed = [e for e in c.endorsement_ids if e not in body.endorsement_ids]
        causes.append(("Endorsement " + ", ".join(added) + " added" if added else "") + (" Endorsement(s) removed" if removed else ""))
        c.endorsement_ids = body.endorsement_ids
    edits = _edits(body.bill_items) if body.bill_items is not None else _edits(body.bill.items) if body.bill is not None else None
    if edits is not None or body.confirm_bill:
        revised, changes = revise_bill(c.bill, edits if edits is not None else _edits(c.bill.items),
                                       reviewed_at=_now() if body.confirm_bill else None)
        if changes:
            causes.append("Bill corrected by user: " + "; ".join(changes))
        elif body.confirm_bill and not c.bill.reviewed_at:
            causes.append("Bill line items confirmed by user")
        c.bill = revised
    if not causes:
        raise HTTPException(status_code=400, detail="No changes supplied")
    store.save_claim(c)
    a, cmp = _analyse_and_store(c, body.cause or "; ".join(x.strip() for x in causes if x.strip()))
    return {"claim": c.model_dump(mode="json", exclude={"owner_id"}), "analysis": a.model_dump(mode="json"), "comparison": cmp}


@app.post("/api/claims/{claim_id}/analyze")
def analyze_claim(claim_id: str, user: User = Depends(require_user)):
    c = _claim(claim_id, user)
    a, cmp = _analyse_and_store(c, "Re-analysis requested")
    return {"analysis": a.model_dump(mode="json"), "comparison": cmp}


@app.get("/api/claims/{claim_id}/analyses")
def claim_analyses(claim_id: str, user: User = Depends(require_user)):
    _claim(claim_id, user)
    return [a.model_dump(mode="json") for a in store.list_analyses(claim_id)]


@app.get("/api/analyses/{analysis_id}")
def get_analysis(analysis_id: str, user: User = Depends(require_user)):
    a = store.get_analysis(analysis_id) or _404("Analysis")
    _claim(a.claim_id, user)
    return a.model_dump(mode="json")


# ------------------------------------------------------------------ scenarios (never overwrite the saved analysis)

@app.post("/api/claims/{claim_id}/scenario")
def scenario(claim_id: str, hyp: Hypotheticals, user: User = Depends(require_user)):
    c, current, docs = _current(claim_id, user)
    a = adjudicate(c, docs, hyp, cause="What-If scenario (HYPOTHETICAL)")
    return {"analysis": a.model_dump(mode="json"), "comparison": compare(current, a, "What-If scenario (HYPOTHETICAL)")}


class SaveScenario(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    hypotheticals: Hypotheticals


@app.post("/api/claims/{claim_id}/scenarios")
def save_scenario(claim_id: str, body: SaveScenario, user: User = Depends(require_user)):
    c, current, docs = _current(claim_id, user)
    a = adjudicate(c, docs, body.hypotheticals, cause=f"Saved scenario: {body.name}")
    sid = f"scn-{uuid.uuid4().hex[:10]}"
    payload = {"name": body.name, "hypotheticals": body.hypotheticals.model_dump(mode="json"), "base_analysis_id": current.analysis_id,
               "payable": [str(a.summary.payable_low), str(a.summary.payable_high)], "patient": [str(a.summary.patient_low), str(a.summary.patient_high)],
               "base_payable": [str(current.summary.payable_low), str(current.summary.payable_high)]}
    store.save_row("scenarios", sid, claim_id, user.id, _now(), payload)
    return payload | {"id": sid}


@app.get("/api/claims/{claim_id}/scenarios")
def list_scenarios(claim_id: str, user: User = Depends(require_user)):
    _claim(claim_id, user)
    return store.list_rows("scenarios", claim_id, user.id)


@app.delete("/api/claims/{claim_id}/scenarios/{scenario_id}")
def delete_scenario(claim_id: str, scenario_id: str, user: User = Depends(require_user)):
    _claim(claim_id, user)
    if not store.delete_row("scenarios", scenario_id, user.id):
        _404("Scenario")
    return {"deleted": scenario_id}


@app.post("/api/claims/{claim_id}/compare-versions")
def compare_versions(claim_id: str, user: User = Depends(require_user)):
    c, current, docs = _current(claim_id, user)
    pol = docs[c.policy_document_id]
    versions, conflicts = build_versions(pol, [docs[e] for e in c.endorsement_ids])
    out = []
    for v in versions:
        a = adjudicate(c, docs, Hypotheticals(version_id=v.version_id), cause=f"Version comparison: {v.label}")
        out.append({"version": v.model_dump(mode="json"), "is_applicable": current.version.selected is not None and
                    current.version.selected.version_id == v.version_id, "summary": a.summary.model_dump(mode="json"),
                    "comparison_vs_current": compare(current, a, f"Version '{v.label}' applied (HYPOTHETICAL override)")})
    return {"versions": out, "conflicts": conflicts}


# ------------------------------------------------------------------ assistant (chat history persisted per user + claim)

class Question(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    context: Optional[dict[str, str]] = None


@app.post("/api/claims/{claim_id}/ask")
def ask(claim_id: str, body: Question, user: User = Depends(require_user)):
    c, current, docs = _current(claim_id, user)
    res = qa_answer(body.question, c, current, docs, body.context or {})
    store.save_row("chats", f"msg-{uuid.uuid4().hex[:10]}", claim_id, user.id, _now(), res)
    return res


@app.get("/api/claims/{claim_id}/chat")
def chat_history(claim_id: str, user: User = Depends(require_user)):
    _claim(claim_id, user)
    return store.list_rows("chats", claim_id, user.id)[-40:]


@app.delete("/api/claims/{claim_id}/chat")
def clear_chat(claim_id: str, user: User = Depends(require_user)):
    _claim(claim_id, user)
    store.execute("DELETE FROM chats WHERE claim_id=? AND owner_id=?", (claim_id, user.id))
    return {"cleared": True}


@app.get("/api/claims/{claim_id}/evidence")
def evidence_search(claim_id: str, q: str = Query(min_length=1, max_length=200), k: int = Query(8, ge=1, le=20), user: User = Depends(require_user)):
    c, current, docs = _current(claim_id, user)
    if not current.version.selected:
        raise HTTPException(status_code=409, detail="No applicable policy version")
    clauses = active_clauses(current.version.selected, docs)
    retr = retriever_for(clauses)
    by_id = {x.clause_id: x for x in clauses}
    norm = normalize_item(q)
    ctx = ItemContext(service_date=c.admission_date, admission_date=c.admission_date, discharge_date=c.discharge_date)
    res = {}
    for method in ("bm25", "semantic", "hybrid", "hybrid_rerank"):
        hits = retr.search(norm.query, method, k)
        res[method] = [{"rank": h.rank, "score": h.score, "evidence": verify(by_id[h.clause_id], norm, ctx).model_dump(mode="json")} for h in hits]
    return {"query": q, "normalized_query": norm.query, "category": norm.category_label, "results": res,
            "config": retr.config(), "note": "Scores are retrieval relevance only, not probabilities of coverage."}


def _fair(c, a, docs):
    from app.fairness.scan import scan
    return scan(c, a, docs)


def _acts(c, a, docs):
    from app.fairness.actions import build_actions
    return build_actions(c, a, _fair(c, a, docs), docs)


@app.get("/api/claims/{claim_id}/fairness")
def fairness(claim_id: str, user: User = Depends(require_user)):
    c, current, docs = _current(claim_id, user)
    return _fair(c, current, docs)


@app.get("/api/claims/{claim_id}/actions")
def actions(claim_id: str, user: User = Depends(require_user)):
    c, current, docs = _current(claim_id, user)
    return _acts(c, current, docs)


# ------------------------------------------------------------------ reports (recorded only after the file is generated)

@app.get("/api/claims/{claim_id}/report.pdf")
def report_pdf(claim_id: str, user: User = Depends(require_user)):
    c, current, docs = _current(claim_id, user)
    pdf = render_pdf(c, current, docs, _fair(c, current, docs), _acts(c, current, docs))
    store.record_report(f"rpt-{uuid.uuid4().hex[:10]}", claim_id, user.id, _now(), "pdf", current.analysis_id, len(pdf))
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="nivaaran-report-{claim_id}.pdf"', "Cache-Control": "private, no-store"})


@app.get("/api/claims/{claim_id}/report.json")
def report_json(claim_id: str, user: User = Depends(require_user)):
    c, current, docs = _current(claim_id, user)
    payload = {"product": "Nivaaran", "generated_at": _now(), "synthetic": c.synthetic, "claim": c.model_dump(mode="json", exclude={"owner_id"}),
               "analysis": current.model_dump(mode="json"), "comparisons": store.list_comparisons(claim_id),
               "fairness": _fair(c, current, docs), "actions": _acts(c, current, docs),
               "documents": [{"document_id": d.document_id, "filename": d.filename, "doc_type": d.doc_type,
                              "sha256": d.sha256, "metadata": d.metadata} for d in docs.values()]}
    body = json.dumps(payload, indent=2, default=str)
    store.record_report(f"rpt-{uuid.uuid4().hex[:10]}", claim_id, user.id, _now(), "json", current.analysis_id, len(body))
    return Response(content=body, media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="nivaaran-report-{claim_id}.json"', "Cache-Control": "private, no-store"})


@app.get("/api/reports")
def list_reports(user: User = Depends(require_user)):
    return store.list_reports(user.id)


# ------------------------------------------------------------------ costs (dataset is public; estimates use your claim)

@app.get("/api/costs")
def costs_dataset():
    ds = cost_mod.dataset()
    return {"dataset": ds["dataset"], "hospital_types": ds["hospital_types"],
            "procedures": [{"key": p["key"], "name": p["name"], "typical_room_days": p["typical_room_days"],
                            "typical_icu_days": p["typical_icu_days"], "components": p["components"],
                            "ranges": {ht: cost_mod.ranges(p["key"], ht) for ht in ds["hospital_types"]}} for p in ds["procedures"]]}


class CostEstimate(BaseModel):
    procedure: str
    claim_id: str
    hospital_type: Literal["private", "trust", "public"] = "private"
    tier: Literal["tier1", "tier2", "tier3"] = "tier1"
    percentile: Literal["p25", "median", "p75"] = "median"
    user_total: Optional[Decimal] = Field(default=None, gt=0)
    room_days: Optional[int] = Field(default=None, ge=0, le=60)
    icu_days: Optional[int] = Field(default=None, ge=0, le=60)


@app.post("/api/costs/estimate")
def costs_estimate(body: CostEstimate, user: User = Depends(require_user)):
    c = _claim(body.claim_id, user)
    docs = _docs_for(c)
    try:
        rng = cost_mod.ranges(body.procedure, body.hospital_type)[body.tier]
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown procedure")
    total = body.user_total if body.user_total is not None else Decimal(rng[body.percentile])
    res = cost_mod.estimate(body.procedure, total, docs[c.policy_document_id], [docs[e] for e in c.endorsement_ids], docs,
                            c.admission_date, body.room_days, body.icu_days, source="user" if body.user_total is not None else "illustrative")
    res["range"] = rng
    return res


# ------------------------------------------------------------------ evaluation (synthetic benchmark; results are public)

@app.post("/api/evaluation/run")
def evaluation_run(user: User = Depends(require_user)):
    from app.evaluation.run_eval import run as run_eval
    return run_eval()


@app.get("/api/evaluation/results")
def evaluation_results():
    p = EVAL_DIR / "results" / "latest.json"
    if not p.exists():
        raise HTTPException(status_code=404, detail="No evaluation has been run yet. Run it from the Evaluation workspace or "
                                                    "`python -m app.evaluation.run_eval`.")
    return json.loads(p.read_text(encoding="utf-8"))


# ------------------------------------------------------------------ demo (synthetic, isolated per visitor)

def _seed_demo(user: User) -> dict:
    """Seed the SYNTHETIC demo case into this user's workspace through the normal pipeline."""
    from demo.generate_demo import OUT_DIR, generate
    if not (OUT_DIR / "synthetic_benefits_brochure.pdf").exists():
        generate()

    def doc(name: str, t: DocType) -> DocumentRecord:
        data = (OUT_DIR / name).read_bytes()
        d = _existing_identical(data, t, user)
        if not d:
            d = process_policy_document(data, name, t, synthetic=True)
            d.owner_id = user.id
            store.save_document(d, data)
        return d

    pol = doc("synthetic_policy_v1.pdf", DocType.policy)
    end = doc("synthetic_endorsement_E01.pdf", DocType.endorsement)
    bro = doc("synthetic_benefits_brochure.pdf", DocType.benefit_summary)
    bill = build_bill(parse_bill_bytes((OUT_DIR / "synthetic_bill_appendicectomy.pdf").read_bytes(), "pdf"), synthetic=True)
    claim = Claim(claim_id=f"clm-{uuid.uuid4().hex[:10]}", title="Demo: laparoscopic appendicectomy (SYNTHETIC)",
                  policy_document_id=pol.document_id, endorsement_ids=[], benefit_summary_ids=[bro.document_id], bill=bill,
                  admission_date=bill.admission_date, discharge_date=bill.discharge_date, diagnosis=bill.diagnosis,
                  synthetic=True, created_at=_now(), owner_id=user.id)
    store.save_claim(claim)
    first, _ = _analyse_and_store(claim, "Initial analysis (policy wording only; endorsement not yet uploaded)")
    claim.endorsement_ids = [end.document_id]
    store.save_claim(claim)
    second, cmp = _analyse_and_store(claim, "Endorsement E-01 added")
    return {"claim_id": claim.claim_id, "policy_id": pol.document_id, "endorsement_id": end.document_id, "benefit_summary_id": bro.document_id,
            "before": {"payable_low": str(first.summary.payable_low), "payable_high": str(first.summary.payable_high)},
            "after": {"payable_low": str(second.summary.payable_low), "payable_high": str(second.summary.payable_high)},
            "comparison": cmp}


DEMO_ENABLED = os.environ.get("NIVAARAN_ENABLE_DEMO", "0") == "1"


def _demo_guard() -> None:
    if not DEMO_ENABLED:
        raise HTTPException(status_code=404, detail="Not found")


@app.post("/api/demo/enter")
def demo_enter(response: Response):
    """Test-only: a disposable demo account (removed after 24 h) seeded with the synthetic case."""
    _demo_guard()
    u = auth.create_test_user("Demo visitor", is_demo=True)
    auth.start_session(response, u.id, days=1)
    return {"user": u.model_dump(), **_seed_demo(u)}


@app.post("/api/demo/user")
def demo_user(response: Response, name: str = "Test user"):
    """Test-only: a signed-in, empty, non-demo account (used by the browser tests for isolation checks)."""
    _demo_guard()
    u = auth.create_test_user(name[:80])
    auth.start_session(response, u.id)
    return {"user": u.model_dump()}


@app.post("/api/demo/load")
def demo_load(user: User = Depends(require_user)):
    """Add the synthetic demo case to the current user's workspace (clearly labelled SYNTHETIC)."""
    _demo_guard()
    return _seed_demo(user)


# ---------------------------------------------------------------------------------------------------------------
# Production: security headers on every response, and the built web app (frontend/dist) served from the same
# origin when it exists, so a single process is the whole deployment. In development Vite serves the app instead.
# ---------------------------------------------------------------------------------------------------------------
_TRUSTED_ORIGINS = set(CORS_ORIGINS) | set(social.PUBLIC_URLS)


@app.middleware("http")
async def _origin_check(request: Request, call_next):
    """CSRF protection in addition to SameSite cookies: a browser request that changes data must come from this site."""
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and request.url.path.startswith("/api/"):
        origin = request.headers.get("origin")
        if origin and origin not in _TRUSTED_ORIGINS and origin != f"{request.url.scheme}://{request.url.netloc}":
            return JSONResponse({"error": "forbidden_origin", "message": "This request was blocked because it did not come from Nivaaran."},
                                status_code=403)
    return await call_next(request)


@app.middleware("http")
async def _security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resp.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if request.url.path.startswith("/api/"):
        resp.headers.setdefault("Cache-Control", "no-store")
    return resp


_DIST = BACKEND_DIR.parent / "frontend" / "dist"
if _DIST.is_dir():
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def _spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "Not found")
        f = (_DIST / path).resolve()
        if path and f.is_file() and _DIST.resolve() in f.parents:
            # The installable app: the service worker and manifest must always be fresh, with the right types.
            if path == "sw.js":
                return FileResponse(f, media_type="text/javascript", headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"})
            if path.endswith(".webmanifest"):
                return FileResponse(f, media_type="application/manifest+json", headers={"Cache-Control": "no-cache"})
            return FileResponse(f)
        return FileResponse(_DIST / "index.html", headers={"Cache-Control": "no-cache"})
