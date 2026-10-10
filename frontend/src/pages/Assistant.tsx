import { Bot, Eraser, Send, User } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { NeedClaim } from "../components/NeedClaim";
import { Disclaimer, ErrorNote, PageHeader, Spinner, SyntheticBanner, Tag } from "../components/ui";
import { api } from "../lib/api";
import { cn, inr, RELATION_META } from "../lib/format";
import type { Analysis, AssistantAnswer, ClaimBundle } from "../lib/types";

const SUGGESTIONS = [
  "Which policy version applies to my treatment date?",
  "Why was the room charge reduced?",
  "Which clause applies to the nebulizer kit?",
  "How was the estimated payable amount calculated?",
  "What information is missing?",
  "What changes if the dietitian consultation is removed?",
  "Why did the estimate change after the amendment?",
  "What does the waiting period clause mean?",
  "Is physiotherapy covered?",
  "मेरी जेब से कितना पैसा जाएगा?",
  "माझ्या खोलीचे पूर्ण भाडे मिळेल का?",
];

export default function Assistant() {
  return (
    <div>
      <PageHeader eyebrow="Assistant" title="Ask about your policy and this claim"
        description="Ask anything about this claim. Every answer quotes your documents, and every amount comes from the calculation. If the documents don't say, it tells you so instead of guessing." />
      <NeedClaim>{(b) => <Chat bundle={b} />}</NeedClaim>
    </div>
  );
}

function Chat({ bundle }: { bundle: ClaimBundle & { analysis: Analysis } }) {
  const [msgs, setMsgs] = useState<AssistantAnswer[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const end = useRef<HTMLDivElement>(null);
  const cid = bundle.claim.claim_id;
  // Conversations are stored on the server per account and claim, so they survive reloads and new sign-ins.
  useEffect(() => {
    setLoaded(false);
    api.chatHistory(cid).then((h) => setMsgs(h as AssistantAnswer[])).catch((e) => setErr((e as Error).message)).finally(() => setLoaded(true));
  }, [cid]);
  // A question handed over from the landing page's ask box (?q=...) is asked once, then removed from the URL.
  const [params, setParams] = useSearchParams();
  const handed = useRef(false);
  useEffect(() => {
    const pending = params.get("q");
    if (!loaded || handed.current || !pending) return;
    handed.current = true;
    setParams({}, { replace: true });
    void ask(pending.slice(0, 500));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded]);
  useEffect(() => { if (loaded) end.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [msgs, busy, loaded]);

  async function ask(text: string) {
    if (!text.trim() || busy) return;
    setBusy(true); setErr(null); setQ("");
    try { const r = await api.ask(bundle.claim.claim_id, text); setMsgs((m) => [...m, r]); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[1fr_300px]">
      <div className="card flex min-h-[560px] flex-col">
        <div className="flex-1 space-y-5 overflow-y-auto p-4 md:p-5" aria-live="polite">
          <SyntheticBanner show={bundle.analysis.synthetic} />
          {!loaded && <Spinner label="Loading this claim's conversation" />}
          {loaded && msgs.length === 0 && !busy && <p className="text-sm text-muted">Ask a question, or pick one of the suggestions.</p>}
          <AnimatePresence initial={false}>
            {msgs.map((m, i) => (
              <motion.div key={i} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="space-y-3">
                <div className="flex justify-end gap-2">
                  <p className="max-w-[80%] rounded-2xl rounded-tr-sm bg-accent/15 px-3.5 py-2 text-sm text-ink ring-1 ring-inset ring-accent/25">{m.question}</p>
                  <User className="mt-1.5 size-4 text-faint" aria-hidden />
                </div>
                <div className="flex gap-2">
                  <Bot className="mt-1.5 size-4 shrink-0 text-accent" aria-hidden />
                  <div className="min-w-0 max-w-[92%] space-y-2">
                    <div className="flex flex-wrap gap-1.5">
                      <Tag tone={m.grounded ? "covered" : "insufficient"}>{m.grounded ? "Grounded in documents" : "Not established by documents"}</Tag>
                      {m.kind === "what_if" && <Tag tone="partial">Hypothetical recalculation</Tag>}
                    </div>
                    <p className="whitespace-pre-line rounded-2xl rounded-tl-sm bg-paper px-3.5 py-2.5 text-sm leading-relaxed text-text" data-testid="answer">{m.answer}</p>
                    {m.breakdown && <Breakdown b={m.breakdown} />}
                    {m.engine && <p className="text-[11px] text-faint">Answered by: {m.engine}</p>}
                    {m.data && m.kind === "what_if" && (
                      <p className="text-xs text-muted num">Δ estimated payable {inr(m.data.payable_delta, { sign: true })} · Δ maximum out-of-pocket {inr(m.data.patient_delta, { sign: true })}</p>
                    )}
                    {m.citations.length > 0 && (
                      <div className="space-y-1.5">
                        <p className="eyebrow">Sources</p>
                        {m.citations.map((c) => (
                          <details key={c.clause_id} className="rounded-lg border border-line bg-card px-3 py-2 text-sm">
                            <summary className="cursor-pointer"><span className="font-mono text-xs">{c.section}</span> {c.heading} <span className="text-xs text-faint">· p. {c.page ?? "?"}</span>
                              {c.relation && <Tag tone={RELATION_META[c.relation]?.tone ?? "neutral"} className="ml-1.5">{RELATION_META[c.relation]?.label ?? c.relation}</Tag>}</summary>
                            <blockquote className="mt-1.5 border-l-2 border-line-2 pl-3 text-[13px]">"{c.excerpt}"</blockquote>
                          </details>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
          {busy && <Spinner label="Retrieving evidence…" />}
          <ErrorNote error={err} />
          <div ref={end} />
        </div>
        <form className="flex gap-2 border-t border-line p-3" onSubmit={(e) => { e.preventDefault(); ask(q); }}>
          <input className="input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask about coverage, clauses, calculations or missing information" aria-label="Question" maxLength={500} data-testid="ask-input" />
          <button className="btn-primary" disabled={busy || !q.trim()} aria-label="Send"><Send className="size-4" /></button>
        </form>
      </div>
      <div className="space-y-3">
        {msgs.length > 0 && (
          <button className="btn-ghost px-0 text-xs" disabled={busy} onClick={async () => {
            try { await api.clearChat(cid); setMsgs([]); } catch (e) { setErr((e as Error).message); }
          }}><Eraser className="size-3.5" /> Clear this conversation</button>)}
        <p className="eyebrow">Suggested questions</p>
        {SUGGESTIONS.map((s) => (
          <button key={s} onClick={() => ask(s)} disabled={busy} className={cn("block w-full rounded-lg border border-line bg-card px-3 py-2 text-left text-sm text-text hover:border-line-2 hover:bg-paper")}>{s}</button>
        ))}
        <Disclaimer className="pt-2" />
      </div>
    </div>
  );
}

const PARTS: [keyof NonNullable<AssistantAnswer["breakdown"]>, string, string][] = [
  ["source_facts", "Source facts", "text-covered"], ["calculated", "Calculated by the engine", "text-accent"],
  ["interpretation", "Interpretation", "text-text"], ["assumptions", "Assumptions", "text-conditional"], ["missing", "Missing evidence", "text-review"],
];

/** Separates what the documents say, what the engine calculated, how it was read, what was assumed, and what is missing. */
function Breakdown({ b }: { b: NonNullable<AssistantAnswer["breakdown"]> }) {
  const rows = PARTS.map(([k, label, tone]) => [label, tone, ([] as string[]).concat(b[k] ?? []).filter(Boolean)] as const).filter(([, , v]) => v.length > 0);
  if (!rows.length) return null;
  return (
    <details className="rounded-lg border border-line bg-card px-3 py-2 text-[13px]">
      <summary className="cursor-pointer text-muted">How this answer is built</summary>
      <dl className="mt-2 space-y-2">
        {rows.map(([label, tone, v]) => (
          <div key={label}><dt className={cn("text-[11px] font-semibold uppercase tracking-wide", tone)}>{label}</dt>
            <dd><ul className="mt-0.5 space-y-0.5 text-text">{v.map((x) => <li key={x}>• {x}</li>)}</ul></dd></div>))}
      </dl>
    </details>
  );
}
