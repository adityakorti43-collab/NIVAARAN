"""Optional live-AI layer for Nivaaran AI.

Off by default. Enabled only when the operator sets NIVAARAN_AI_PROVIDER=anthropic and Anthropic credentials are
available (ANTHROPIC_API_KEY or an `ant auth login` profile). When enabled, Claude only *rewords* the
deterministic, evidence-grounded answer for readability: it receives the answer and the cited excerpts, nothing
else, and is told not to add facts. A guard rejects any rewrite that introduces a number not present in the
evidence, in which case the deterministic answer is returned unchanged. Without configuration, answers are
labelled "deterministic evidence engine" — never presented as live AI.
"""
from __future__ import annotations

import os
import re
from typing import Optional

from app.config import log

PROVIDER = os.environ.get("NIVAARAN_AI_PROVIDER", "").lower()
MODEL = os.environ.get("NIVAARAN_AI_MODEL", "claude-opus-5-5")
SYSTEM = (
    "You rewrite answers for Nivaaran, an insurance decision-support tool, so a non-expert can follow them. "
    "Use ONLY the facts in the draft answer and the quoted policy excerpts. Do not add, remove or change any "
    "number, amount, date, percentage or clause reference. Do not speculate about the insurer's decision. "
    "Keep any statement of uncertainty or missing information. Plain sentences, no headings, under 170 words."
)
_client = None


def enabled() -> bool:
    return PROVIDER == "anthropic"


def mode_label() -> str:
    return f"Live AI ({MODEL}) rewording evidence-grounded answers" if enabled() else "Deterministic evidence engine (no external AI configured)"


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "") for n in re.findall(r"\d[\d,]*(?:\.\d+)?", text)}


CHAT_SYSTEM = (
    "You are Nivaaran AI, a careful health-insurance assistant for consumers in India. Answer ONLY from the CONTEXT: "
    "policy clauses (with section and page), the itemised ledger and calculation produced by a deterministic engine, "
    "and document-consistency findings. Rules: (1) Never invent a clause, page, amount, date or percentage; every "
    "number you write must appear in the CONTEXT. (2) Cite clauses as [section] after the sentence they support. "
    "(3) Separate what the documents state from what is calculated and from what is assumed or missing. "
    "(4) If the CONTEXT does not answer the question, say so and name the missing document or fact. (5) Never "
    "promise the insurer will pay; amounts are estimates. (6) Do not call anything fraud. (7) Lead with the direct "
    "answer in one or two sentences, then brief supporting points. Under 220 words. Plain language."
)


def _client_once():
    global _client
    import anthropic
    _client = _client or anthropic.Anthropic()
    return _client


def grounded_answer(question: str, context: str, draft: str) -> Optional[str]:
    """Full answer from Claude using only the supplied context; None if disabled, refused, failed or unsafe."""
    if not enabled():
        return None
    try:
        resp = _client_once().beta.messages.create(
            model=MODEL, max_tokens=2000, system=CHAT_SYSTEM, output_config={"effort": "medium"},
            betas=["server-side-fallback-2026-07-01"], fallbacks="default",
            messages=[{"role": "user", "content": f"CONTEXT:\n{context}\n\nENGINE DRAFT ANSWER (verified, may be terse):\n{draft}\n\nQUESTION: {question}"}],
        )
        if resp.stop_reason == "refusal":
            return None
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        if not text or not _numbers(text) <= (_numbers(context) | _numbers(draft) | _numbers(question)):
            log.warning("AI answer rejected: introduced numbers not present in the context")
            return None
        return text
    except Exception as exc:
        log.warning("AI provider unavailable (%s); using deterministic answer", type(exc).__name__)
        return None


def translate_hi(text: str) -> Optional[str]:
    """Hindi translation for read-aloud (only when the operator has configured the AI provider)."""
    if not enabled():
        return None
    try:
        resp = _client_once().messages.create(
            model=MODEL, max_tokens=2000, output_config={"effort": "low"},
            system="Translate the user's text into clear, simple Hindi (Devanagari) for being read aloud. Keep every number, "
                   "₹ amount, percentage and clause reference exactly as written. Output only the translation.",
            messages=[{"role": "user", "content": text}],
        )
        out = "".join(b.text for b in resp.content if b.type == "text").strip()
        return out if out and _numbers(out) <= _numbers(text) else None
    except Exception as exc:
        log.warning("Translation unavailable (%s)", type(exc).__name__)
        return None


def reword(answer: str, citations: list[dict]) -> Optional[str]:
    """Return a reworded answer, or None to keep the deterministic text (disabled, refused, failed or unsafe)."""
    global _client
    if not enabled():
        return None
    try:
        import anthropic
        _client = _client or anthropic.Anthropic()
        evidence = "\n".join(f"[{c.get('section')}] {c.get('heading')}: \"{c.get('excerpt')}\"" for c in citations[:6])
        resp = _client.beta.messages.create(
            model=MODEL, max_tokens=1200, system=SYSTEM,
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"], fallbacks="default",
            messages=[{"role": "user", "content": f"Draft answer:\n{answer}\n\nPolicy excerpts:\n{evidence or '(none)'}"}],
        )
        if resp.stop_reason == "refusal":
            return None
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        allowed = _numbers(answer) | _numbers(evidence)
        if not text or not _numbers(text) <= allowed:
            log.warning("AI rewrite rejected: introduced numbers not present in the evidence")
            return None
        return text
    except Exception as exc:  # provider unavailable, auth, network, rate limits: fall back honestly
        log.warning("AI provider unavailable (%s); using deterministic answer", type(exc).__name__)
        return None
