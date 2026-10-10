import { MessageCircle, Bot, Check, ClipboardCopy, CornerDownLeft, RotateCcw, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { cn } from "../lib/format";
import { useApp } from "../lib/store";
import type { AssistantAnswer, CopilotAction } from "../lib/types";
import { useClauseViewer } from "./ClauseViewer";
import { SpeakButtons } from "./SpeakButtons";

type Msg = { role: "user"; text: string } | { role: "bot"; a: AssistantAnswer } | { role: "error"; text: string; retry: string };

function suggestions(sel: Record<string, string>, path: string, itemName?: string): string[] {
  if (sel.finding_id) return ["Explain this discrepancy in simple words", "Is this evidence sufficient to conclude that I was misled?", "What should I ask my insurer?"];
  if (sel.item_id) return [`Why was ${itemName ?? "this item"} flagged?`, "Explain this in simpler language", "Which clause supports this finding?"];
  if (path === "/money-flow" || path === "/what-if") return ["How was the estimated payable amount calculated?", "What changes if the nebulizer kit is removed?", "Why might I have to pay this amount myself?"];
  return ["What does my policy cover?", "Does my amendment apply to my treatment date?", "What information is missing?", "Is there a discrepancy between these documents?", "Help me draft a request for clarification"];
}

/** Persistent, context-aware assistant. Answers come from /ask, which uses retrieved clauses and engine output only. */
export function Copilot() {
  const { activeClaimId, bundle, selection, copilotOpen, setCopilotOpen, pendingQuestion, clearPending } = useApp();
  const { openClause } = useClauseViewer();
  const nav = useNavigate();
  const loc = useLocation();
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState<number | null>(null);
  const end = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const itemName = bundle?.analysis?.rows.find((r) => r.item_id === selection.item_id)?.original_description;

  useEffect(() => {  // keep analyses isolated; reload this claim's saved conversation
    setMsgs([]);
    if (!activeClaimId) return;
    api.chatHistory(activeClaimId).then((h) => setMsgs(h.flatMap((a: AssistantAnswer) => [{ role: "user" as const, text: a.question }, { role: "bot" as const, a }]))).catch(() => {});
  }, [activeClaimId]);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [msgs, busy]);
  useEffect(() => {
    if (!copilotOpen) return;
    setTimeout(() => input.current?.focus(), 120);
    const k = (e: KeyboardEvent) => e.key === "Escape" && setCopilotOpen(false);
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [copilotOpen, setCopilotOpen]);

  const ask = useCallback(async (text: string) => {
    if (!text.trim() || busy || !activeClaimId) return;
    setMsgs((m) => [...m, { role: "user", text }]);
    setQ(""); setBusy(true);
    try {
      const ctx: Record<string, string> = { ...selection, view: loc.pathname };
      const a = await api.ask(activeClaimId, text, ctx);
      setMsgs((m) => [...m, { role: "bot", a }]);
    } catch (e) {
      setMsgs((m) => [...m, { role: "error", text: (e as Error).message, retry: text }]);
    } finally { setBusy(false); }
  }, [busy, activeClaimId, selection, loc.pathname]);

  useEffect(() => { if (pendingQuestion && copilotOpen) { ask(pendingQuestion); clearPending(); } }, [pendingQuestion, copilotOpen, ask, clearPending]);

  function run(a: CopilotAction) {
    if (a.type === "open_clause" && a.clause_id) openClause(a.clause_id);
    if (a.type === "open_item" && a.item_id) { nav(`/claim?item=${a.item_id}`); setCopilotOpen(false); }
    if (a.type === "navigate" && a.to) { nav(a.to); setCopilotOpen(false); }
  }

  return (
    <>
      <AnimatePresence>
        {!copilotOpen && (
          <motion.button key="launcher" onClick={() => setCopilotOpen(true)} aria-label="Open Nivaaran AI" data-testid="copilot-launcher"
            initial={{ scale: 0.6, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.6, opacity: 0 }} whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
            className="fixed bottom-5 right-5 z-50 flex items-center gap-2 rounded-full border border-brass/40 bg-forest py-2.5 pl-3.5 pr-4 text-[13.5px] font-medium text-ivory shadow-[0_14px_32px_-14px_rgb(20_45_39/0.7)] hover:bg-[#1e3f36]">
            <MessageCircle className="size-4" aria-hidden />
            Ask Nivaaran
          </motion.button>
        )}
      </AnimatePresence>
      <AnimatePresence>
        {copilotOpen && (
          <motion.aside key="panel" role="dialog" aria-label="Nivaaran AI" data-testid="copilot"
            initial={{ opacity: 0, y: 30, scale: 0.96, filter: "blur(6px)" }} animate={{ opacity: 1, y: 0, scale: 1, filter: "blur(0px)" }}
            exit={{ opacity: 0, y: 24, scale: 0.97 }} transition={{ type: "spring", stiffness: 360, damping: 32 }}
            className="fixed inset-x-2 bottom-2 z-50 flex max-h-[min(720px,calc(100dvh-1rem))] flex-col overflow-hidden rounded-[6px] border border-line-2 bg-card shadow-[0_40px_100px_-30px_rgb(20_45_39/0.45)] sm:inset-x-auto sm:bottom-5 sm:right-5 sm:w-[420px]">
            <header className="relative flex items-center gap-3 border-b border-line px-4 py-3">
              <div className="pointer-events-none absolute inset-x-0 top-0 h-[2px] bg-brass" aria-hidden />
              <span className="grid size-8 place-items-center rounded-[4px] bg-forest text-brass"><Bot className="size-4" aria-hidden /></span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-ink">Ask Nivaaran</p>
                <p className="truncate text-[11.5px] text-muted">{selection.item_id ? `Looking at: ${itemName}` : selection.finding_id ? "Looking at a fairness finding" : bundle?.claim.title ?? "No claim loaded"}</p>
              </div>
              <button className="btn-ghost p-2" aria-label="Close Nivaaran AI" onClick={() => setCopilotOpen(false)}><X className="size-4" /></button>
            </header>
            {bundle?.claim.policy_document_id && (
              <div className="flex flex-wrap items-center gap-2 border-b border-line bg-paper/60 px-4 py-2.5" data-testid="copilot-policy-audio">
                <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted">Hear your policy</span>
                <SpeakButtons compact getText={async (lang) => (await api.policySummary(bundle.claim.policy_document_id, lang)).text} />
              </div>
            )}
            <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4" aria-live="polite">
              {!activeClaimId && <p className="text-sm text-muted">Load a claim first, then ask about it.</p>}
              {msgs.length === 0 && activeClaimId && (
                <div>
                  <p className="text-sm text-text">Ask about your coverage, a bill item, a calculation or a discrepancy. Answers quote your documents.</p>
                  <div className="mt-3 flex flex-col gap-1.5">
                    {suggestions(selection, loc.pathname, itemName).map((s) => (
                      <button key={s} onClick={() => ask(s)} className="rounded-xl border border-line px-3 py-2 text-left text-[13px] text-text transition-colors hover:border-accent/50 hover:text-ink">{s}</button>))}
                  </div>
                </div>
              )}
              {msgs.map((m, i) => (
                <motion.div key={i} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
                  {m.role === "user" && <p className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-md bg-accent/15 px-3.5 py-2 text-[13.5px] text-ink ring-1 ring-inset ring-accent/25">{m.text}</p>}
                  {m.role === "error" && (
                    <div className="rounded-xl border border-conflict/30 bg-conflict-bg p-3 text-[13px] text-conflict">
                      {m.text} <button className="ml-2 inline-flex items-center gap-1 font-semibold underline" onClick={() => { setMsgs((x) => x.filter((_, j) => j !== i)); ask(m.retry); }}><RotateCcw className="size-3" /> Retry</button>
                    </div>
                  )}
                  {m.role === "bot" && (
                    <div className="space-y-2">
                      <div className="flex items-center gap-2 text-[11px]">
                        <span className={cn("rounded-full px-2 py-0.5", m.a.grounded ? "bg-covered-bg text-covered" : "bg-insufficient-bg text-insufficient")}>{m.a.grounded ? "Grounded in your documents" : "Not established by the documents"}</span>
                        <button className="ml-auto inline-flex items-center gap-1 text-faint hover:text-ink" aria-label="Copy answer"
                          onClick={async () => { try { await navigator.clipboard.writeText(m.a.draft ?? m.a.answer); setCopied(i); setTimeout(() => setCopied(null), 1500); } catch { /* clipboard blocked */ } }}>
                          {copied === i ? <Check className="size-3" /> : <ClipboardCopy className="size-3" />}{copied === i ? "Copied" : "Copy"}</button>
                      </div>
                      <p className="whitespace-pre-line text-[13.5px] leading-relaxed text-text" data-testid="copilot-answer">{m.a.answer}</p>
                      <SpeakButtons compact getText={async (lang) => {
                        if (lang === "en") return m.a.draft ?? m.a.answer;
                        // Hindi: the AI translation when configured; otherwise (and always for Marathi) the cited clauses,
                        // explained in that language from their structured reading.
                        if (lang === "hi") { try { return (await api.translateHi(m.a.answer)).text; } catch { /* fall back to cited clauses */ } }
                        const cites = m.a.citations.filter((c) => c.clause_id.includes(":")).slice(0, 3);
                        if (!cites.length) throw new Error(lang === "hi" ? "Hindi read-aloud of this answer needs the AI provider configured. Open a cited clause to hear it in Hindi."
                          : "This answer cites no policy clause to read in Marathi. Open Documents to hear the policy summary in Marathi.");
                        const parts = await Promise.all(cites.map((c) => api.explainClause(c.document_id, c.section, lang).then((r) => r.text)));
                        return (lang === "hi" ? "इस उत्तर से जुड़ी धाराएँ: " : "या उत्तराशी संबंधित कलमे: ") + parts.join(" ");
                      }} />
                      {m.a.engine && <p className="text-[10.5px] text-faint">Answered by: {m.a.engine}</p>}
                      {m.a.breakdown && (
                        <details className="rounded-lg border border-line bg-paper/60 px-2.5 py-1.5 text-[12px]">
                          <summary className="cursor-pointer text-muted">Facts, calculations, assumptions and gaps</summary>
                          <dl className="mt-1.5 space-y-1.5">
                            {([["Source facts", m.a.breakdown.source_facts], ["Calculated", m.a.breakdown.calculated], ["Assumptions", m.a.breakdown.assumptions], ["Missing evidence", m.a.breakdown.missing]] as [string, string[]][]).map(([k, v]) => v.length > 0 && (
                              <div key={k}><dt className="font-semibold text-ink">{k}</dt><dd><ul className="list-disc pl-4 text-muted">{v.map((x) => <li key={x}>{x}</li>)}</ul></dd></div>))}
                          </dl>
                        </details>
                      )}
                      {m.a.draft && <pre className="max-h-56 overflow-auto whitespace-pre-wrap rounded-xl border border-line bg-paper p-3 font-mono text-[11.5px] leading-relaxed text-text">{m.a.draft}</pre>}
                      {m.a.citations.length > 0 && (
                        <div className="space-y-1">
                          {m.a.citations.slice(0, 4).map((c) => (
                            <details key={c.clause_id} className="rounded-lg border border-line bg-paper/60 px-2.5 py-1.5 text-[12.5px]">
                              <summary className="cursor-pointer text-text"><span className="font-mono text-accent">{c.section}</span> {c.heading} <span className="text-faint">· p. {c.page ?? "?"}</span></summary>
                              <p className="mt-1 text-muted">“{c.excerpt}”</p>
                            </details>))}
                        </div>
                      )}
                      {(m.a.actions?.length ?? 0) > 0 && (
                        <div className="flex flex-wrap gap-1.5 pt-1">
                          {m.a.actions!.map((a, j) => <button key={j} onClick={() => run(a)} className="rounded-full border border-accent/35 px-2.5 py-1 text-[12px] font-medium text-accent transition-colors hover:bg-accent/10">{a.label}</button>)}
                        </div>
                      )}
                    </div>
                  )}
                </motion.div>
              ))}
              {busy && (
                <div className="flex items-center gap-1.5 text-muted" aria-label="Nivaaran AI is answering">
                  {[0, 1, 2].map((d) => <motion.span key={d} className="size-1.5 rounded-full bg-accent" animate={{ opacity: [0.25, 1, 0.25], y: [0, -3, 0] }} transition={{ duration: 0.9, repeat: Infinity, delay: d * 0.15 }} />)}
                  <span className="ml-1 text-[12px]">Checking the evidence</span>
                </div>
              )}
              <div ref={end} />
            </div>
            <form className="flex items-center gap-2 border-t border-line p-3" onSubmit={(e) => { e.preventDefault(); ask(q); }}>
              <input ref={input} value={q} onChange={(e) => setQ(e.target.value)} placeholder={activeClaimId ? "Ask about this claim" : "No claim loaded"} disabled={!activeClaimId}
                aria-label="Ask Nivaaran AI" maxLength={500} data-testid="copilot-input" className="input rounded-full" />
              <button className="btn-primary size-10 shrink-0 p-0" disabled={busy || !q.trim()} aria-label="Send"><CornerDownLeft className="size-4" /></button>
            </form>
            <p className="px-4 pb-3 text-[10.5px] text-faint">Decision support only. Answers use your documents and the rules engine; they can't guarantee what your insurer decides.</p>
          </motion.aside>
        )}
      </AnimatePresence>
    </>
  );
}
