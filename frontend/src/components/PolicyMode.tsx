import { Bot, CalendarCheck2, CheckCircle2, Clock3, Download, FileText, Hourglass, Plus, Send, Trash2, User, Wallet } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../lib/api";
import { cn, fmtDate, fromPaise, inr, toPaise } from "../lib/format";
import type { Analysis, DocumentRecord, PolicyAnswer, PolicyChecklist } from "../lib/types";
import { useClauseViewer } from "./ClauseViewer";
import { Ledger } from "./Ledger";
import { SpeakButtons } from "./SpeakButtons";
import { Disclaimer, ErrorNote, Section, Spinner } from "./ui";
import { AskTopics, BillSplit, ClaimJourney, CutReasons, HowEstimateWorks, KeyTerms } from "./PolicyGuide";
import { PolicyBrief } from "./PolicyBrief";

const rupees = (v: string | number) => "₹" + Number(v).toLocaleString("en-IN", { maximumFractionDigits: 0 });
const iso = (d: Date) => d.toISOString().slice(0, 10);

function ClauseRefBtn({ docId, section }: { docId: string; section: string }) {
  const { openClause } = useClauseViewer();
  return (
    <button type="button" onClick={() => openClause(`${docId}:${section}`)} aria-label={`Open clause ${section}`}
      className="shrink-0 rounded-[3px] border border-line-2 px-1.5 py-px font-mono text-[10.5px] text-muted transition-colors hover:border-accent hover:text-accent">{section}</button>
  );
}

/* ============================================================== What-if: estimate a stay against the policy */

type Row = { description: string; quantity: string; amount: string };
// Typical lines on an Indian hospital bill, as a starting point. The amounts are blank until you enter yours.
const STARTER: Row[] = [
  { description: "Room rent", quantity: "3", amount: "" },
  { description: "Surgeon and doctor fees", quantity: "1", amount: "" },
  { description: "Medicines and drugs", quantity: "1", amount: "" },
  { description: "Laboratory tests", quantity: "1", amount: "" },
];
const QUICK = ["ICU charges", "Operation theatre charges", "Ambulance", "Consumables", "Implant / stent", "Attendant charges"];

export function PolicyEstimator({ policy }: { policy: DocumentRecord }) {
  const [rows, setRows] = useState<Row[]>(STARTER);
  const today = new Date();
  const [adm, setAdm] = useState(iso(today));
  const [dis, setDis] = useState(iso(new Date(today.getTime() + 3 * 86_400_000)));
  const [result, setResult] = useState<Analysis | null>(null);
  const [busy, setBusy] = useState(false), [err, setErr] = useState<string | null>(null);
  const filled = rows.filter((r) => r.description.trim() && /^\d[\d,]*(\.\d{1,2})?$/.test(r.amount.trim()));
  const total = filled.reduce((s, r) => s + toPaise(r.amount.replace(/,/g, "")), 0n);
  const set = (i: number, p: Partial<Row>) => setRows(rows.map((r, j) => (j === i ? { ...r, ...p } : r)));

  async function run() {
    setBusy(true); setErr(null);
    try {
      const r = await api.policyEstimate(policy.document_id, { admission_date: adm, discharge_date: dis || null,
        items: filled.map((r) => ({ description: r.description.trim(), quantity: r.quantity || "1", amount: r.amount.replace(/,/g, "") })) });
      setResult(r.analysis);
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }

  const s = result?.summary;
  return (
    <div className="space-y-5">
      <div className="grid gap-5 xl:grid-cols-[1.15fr_1fr]">
        <Section title="Your hospital stay" description="Enter the charges you expect, or ones from a quote. Room rent is the total for all nights.">
          <div className="grid gap-3 sm:grid-cols-2">
            <label><span className="label">Admitted on</span><input type="date" className="input" value={adm} onChange={(e) => setAdm(e.target.value)} /></label>
            <label><span className="label">Discharged on</span><input type="date" className="input" value={dis} onChange={(e) => setDis(e.target.value)} /></label>
          </div>
          <div className="mt-4 overflow-hidden rounded-[6px] border border-line">
            <div className="grid grid-cols-[1fr_64px_130px_32px] gap-2 border-b border-line bg-paper px-3 py-2 font-mono text-[10.5px] uppercase tracking-[0.12em] text-faint">
              <span>Charge</span><span className="text-right">Qty</span><span className="text-right">Amount ₹</span><span />
            </div>
            {rows.map((r, i) => (
              <div key={i} className="grid grid-cols-[1fr_64px_130px_32px] items-center gap-2 border-b border-line/70 px-3 py-1 last:border-b-0">
                <input className="w-full rounded-[4px] border border-transparent bg-transparent px-2 py-1.5 text-[14px] outline-none hover:border-line-2 focus:border-accent" value={r.description}
                  onChange={(e) => set(i, { description: e.target.value })} aria-label={`Charge ${i + 1}`} placeholder="What is charged" />
                <input className="w-full rounded-[4px] border border-transparent bg-transparent px-2 py-1.5 text-right text-[14px] text-muted outline-none hover:border-line-2 focus:border-accent num" value={r.quantity}
                  onChange={(e) => set(i, { quantity: e.target.value })} aria-label={`Charge ${i + 1} quantity`} inputMode="decimal" />
                <input className="w-full rounded-[4px] border border-line-2 bg-card px-2 py-1.5 text-right text-[14px] font-medium text-ink outline-none focus:border-accent num" value={r.amount}
                  onChange={(e) => set(i, { amount: e.target.value })} aria-label={`Charge ${i + 1} amount`} inputMode="decimal" placeholder="0" />
                <button type="button" className="grid size-8 place-items-center rounded-[4px] text-faint hover:bg-excluded-bg hover:text-excluded" aria-label={`Remove charge ${i + 1}`}
                  onClick={() => setRows(rows.filter((_, j) => j !== i))}><Trash2 className="size-4" /></button>
              </div>))}
          </div>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {QUICK.filter((q) => !rows.some((r) => r.description === q)).map((q) => (
              <button key={q} type="button" onClick={() => setRows([...rows, { description: q, quantity: "1", amount: "" }])}
                className="inline-flex items-center gap-1 rounded-full border border-line-2 px-2.5 py-1 text-[12px] text-muted hover:border-ink/40 hover:text-ink"><Plus className="size-3" />{q}</button>))}
            <button type="button" onClick={() => setRows([...rows, { description: "", quantity: "1", amount: "" }])}
              className="inline-flex items-center gap-1 rounded-full border border-dashed border-line-2 px-2.5 py-1 text-[12px] text-muted hover:text-ink"><Plus className="size-3" />Other</button>
          </div>
          <div className="mt-5 flex flex-wrap items-center gap-4">
            <p className="text-[13px] text-muted">Total <span className="font-display text-[22px] text-ink num">{total ? inr(fromPaise(total)).replace(/\.00$/, "") : "₹0"}</span></p>
            <div className="flex-1" />
            <button className="btn-primary h-11 px-6" disabled={busy || !filled.length || !adm} onClick={run} data-testid="run-estimate">
              {busy ? <Spinner label="Calculating…" /> : "Estimate what's covered"}</button>
          </div>
          <ErrorNote error={err} className="mt-3" />
        </Section>

        <div className="theme-forest relative overflow-hidden rounded-[6px] bg-forest p-6 text-ivory" data-testid="estimate-result">
          <div className="pointer-events-none absolute -right-16 -top-20 size-64 rounded-full bg-brass/15 blur-3xl" aria-hidden />
          {!s ? (
            <div className="relative flex h-full min-h-[260px] flex-col justify-center">
              <p className="font-mono text-[10.5px] uppercase tracking-[0.18em] text-brass">Estimate</p>
              <p className="mt-3 font-display text-[34px] leading-tight text-ivory">How much would your policy pay?</p>
              <p className="mt-3 max-w-sm text-[14px] leading-relaxed text-ivory/70">Fill in the charges and press <em>Estimate</em>. Nivaaran applies your policy's room-rent caps, exclusions, deductible and co-payment, exactly as it does for a real claim. Nothing is saved.</p>
            </div>
          ) : (
            <div className="relative">
              <p className="font-mono text-[10.5px] uppercase tracking-[0.18em] text-brass">Your policy would likely pay</p>
              <p className="mt-2 font-display text-[56px] leading-none num">{rupees(s.payable_low)}</p>
              {s.payable_high !== s.payable_low && <p className="mt-1 text-[13px] text-ivory/70">up to {rupees(s.payable_high)} if the open questions go your way</p>}
              <div className="mt-6 grid grid-cols-2 gap-px overflow-hidden rounded-[4px] bg-ivory/10">
                <div className="bg-forest/95 p-3.5"><p className="text-[11.5px] text-ivory/60">You'd pay yourself</p><p className="mt-1 font-display text-[26px] num">{rupees(s.patient_low)}</p></div>
                <div className="bg-forest/95 p-3.5"><p className="text-[11.5px] text-ivory/60">Total billed</p><p className="mt-1 font-display text-[26px] num">{rupees(s.total_billed)}</p></div>
              </div>
              <p className="mt-6 text-[12px] font-medium uppercase tracking-[0.12em] text-ivory/55">Why you'd pay {rupees(s.patient_low)}</p>
              <ul className="mt-2 space-y-2 text-[13.5px]">
                {([["Not covered, or above a cap", s.item_reductions], ["Deductible (you pay first)", s.deductible_applied_low], ["Co-payment (your share)", s.copay_low], ["Not decided yet (needs a paper or a check)", s.unresolved_claimed]] as [string, string][])
                  .filter(([, v]) => Number(v) > 0).map(([k, v]) => (
                    <li key={k} className="flex items-center gap-3"><span className="flex-1 text-ivory/80">{k}</span><span className="font-semibold text-ivory num">{rupees(v)}</span></li>))}
              </ul>
              <p className="mt-4 text-[12px] leading-relaxed text-ivory/55">The table below shows the clause behind each amount.</p>
            </div>
          )}
        </div>
      </div>
      <div className="grid gap-5 xl:grid-cols-2"><HowEstimateWorks /><BillSplit policy={policy} /></div>
      {result && (
        <Section title="Line by line" description="Each charge, the clause that decides it, and what it would pay. Open a row for the exact wording.">
          <Ledger analysis={result} />
        </Section>)}
      <Disclaimer />
    </div>
  );
}

/* ============================================================== Assistant: questions about the policy */

const ASK = ["Is room rent capped?", "What isn't covered?", "How long are the waiting periods?", "What do I pay myself on a claim?",
  "Is ambulance covered?", "Which documents do I need to claim?", "कमरे का किराया कितना मिलेगा?", "मेरी जेब से कितना जाएगा?"];

export function PolicyAsk({ policy }: { policy: DocumentRecord }) {
  const [msgs, setMsgs] = useState<{ q: string; a?: PolicyAnswer; err?: string }[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { setMsgs([]); }, [policy.document_id]);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth", block: "nearest" }); }, [msgs.length, busy]);

  async function ask(question: string) {
    const text = question.trim();
    if (!text || busy) return;
    setQ(""); setBusy(true); setMsgs((m) => [...m, { q: text }]);
    try { const a = await api.policyAsk(policy.document_id, text); setMsgs((m) => m.map((x, i) => (i === m.length - 1 ? { ...x, a } : x))); }
    catch (e) { setMsgs((m) => m.map((x, i) => (i === m.length - 1 ? { ...x, err: (e as Error).message } : x))); }
    finally { setBusy(false); }
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[1fr_300px]">
      <div className="card flex min-h-[520px] flex-col overflow-hidden p-0">
        <div className="flex-1 space-y-5 overflow-y-auto p-5" aria-live="polite" data-testid="policy-chat">
          {msgs.length === 0 && (
            <div className="grid h-full place-items-center py-10 text-center">
              <div>
                <span className="mx-auto grid size-12 place-items-center rounded-full bg-forest text-brass"><Bot className="size-6" /></span>
                <p className="mt-4 font-display text-[26px] text-ink">Ask about {policy.metadata.title?.split(/\s+[-–—]\s+/)[0] ?? "your policy"}</p>
                <p className="mx-auto mt-1.5 max-w-md text-[13.5px] text-muted">Answers come straight from your policy's clauses, in English or Hindi. If the policy doesn't say, you'll be told so.</p>
              </div>
            </div>)}
          <AnimatePresence initial={false}>
            {msgs.map((m, i) => (
              <motion.div key={i} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-3">
                <div className="flex justify-end gap-2.5">
                  <p className="max-w-[80%] rounded-[14px] rounded-br-[4px] bg-ink px-4 py-2.5 text-[14px] text-paperwhite">{m.q}</p>
                  <span className="grid size-8 shrink-0 place-items-center rounded-full bg-paper text-muted"><User className="size-4" /></span>
                </div>
                <div className="flex gap-2.5">
                  <span className="grid size-8 shrink-0 place-items-center rounded-full bg-forest text-brass"><Bot className="size-4" /></span>
                  <div className="min-w-0 max-w-[85%] rounded-[14px] rounded-tl-[4px] border border-line bg-card px-4 py-3">
                    {!m.a && !m.err && <Spinner label="Reading your policy…" />}
                    {m.err && <p className="text-sm text-excluded">{m.err}</p>}
                    {m.a && <>
                      <p className="whitespace-pre-line text-[14px] leading-relaxed text-text" data-testid="policy-answer">{m.a.answer}</p>
                      {m.a.citations.length > 0 && (
                        <div className="mt-3 space-y-2 border-t border-line pt-3">
                          {m.a.citations.map((c) => (
                            <div key={c.clause_id} className="flex items-start gap-2 text-[12.5px]">
                              <ClauseRefBtn docId={c.document_id} section={c.section} />
                              <span className="min-w-0 text-muted"><span className="font-medium text-ink">{c.heading}</span> · “{c.excerpt.slice(0, 160)}{c.excerpt.length > 160 ? "…" : ""}”</span>
                            </div>))}
                        </div>)}
                      <div className="mt-3 flex flex-wrap items-center gap-2">
                        <span className={cn("rounded-full px-2 py-0.5 text-[11px]", m.a.grounded ? "bg-covered-bg text-covered" : "bg-insufficient-bg text-insufficient")}>{m.a.grounded ? "From your policy" : "Not clearly covered by the policy"}</span>
                        <SpeakButtons compact getText={async () => m.a!.answer_en ?? m.a!.answer} />
                      </div>
                    </>}
                  </div>
                </div>
              </motion.div>))}
          </AnimatePresence>
          <div ref={end} />
        </div>
        <form className="flex items-center gap-2 border-t border-line bg-paper p-3" onSubmit={(e) => { e.preventDefault(); void ask(q); }}>
          <input className="input h-11 flex-1" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask in English or हिंदी, e.g. Is cataract surgery covered?" aria-label="Ask about your policy" maxLength={500} />
          <button className="btn-primary h-11 w-11 p-0" disabled={busy || !q.trim()} aria-label="Send"><Send className="size-4" /></button>
        </form>
      </div>
      <div className="xl:col-span-2 xl:row-start-2"><Section title="Explore by topic" description="Not sure what to ask? Start here."><AskTopics onAsk={(x) => void ask(x)} /></Section></div>
      <Section title="Try asking" description="Tap a question.">
        <div className="flex flex-wrap gap-1.5 xl:flex-col xl:items-stretch">
          {ASK.map((s) => <button key={s} type="button" onClick={() => void ask(s)} disabled={busy}
            className="rounded-[6px] border border-line px-3 py-2 text-left text-[13px] text-text transition-colors hover:border-accent hover:text-accent">{s}</button>)}
        </div>
      </Section>
    </div>
  );
}

/* ============================================================== Next steps: what to do with this policy */

export function PolicyChecklistView({ policy }: { policy: DocumentRecord }) {
  return (
    <div className="space-y-5">
      <ClaimJourney policy={policy} />
      <ChecklistCards policy={policy} />
      <CutReasons policy={policy} />
    </div>
  );
}

function ChecklistCards({ policy }: { policy: DocumentRecord }) {
  const [ck, setCk] = useState<PolicyChecklist | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const key = `nivaaran.docs-ready.${policy.document_id}`;
  const [ready, setReady] = useState<string[]>(() => { try { return JSON.parse(localStorage.getItem(key) ?? "[]"); } catch { return []; } });
  useEffect(() => { setCk(null); api.policyChecklist(policy.document_id).then(setCk).catch((e) => setErr(e.message)); }, [policy.document_id]);
  const toggle = (t: string) => {
    const next = ready.includes(t) ? ready.filter((x) => x !== t) : [...ready, t];
    setReady(next); try { localStorage.setItem(key, JSON.stringify(next)); } catch { /* per-device convenience only */ }
  };
  if (err) return <ErrorNote error={err} />;
  if (!ck) return <Spinner label="Reading your policy…" />;
  const id = policy.document_id;
  const done = ck.claim_documents.filter((d) => ready.includes(d.text)).length;

  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <Section title="Keep these ready for a claim" description={ck.claim_documents.length ? `${done} of ${ck.claim_documents.length} ready. Tick them off as you collect them.` : undefined}
        actions={ck.claim_documents[0] && <ClauseRefBtn docId={id} section={ck.claim_documents[0].clause} />}>
        {ck.claim_documents.length === 0 ? <p className="text-sm text-muted">Your policy doesn't list specific claim documents. Keep the discharge summary, itemised bill, prescriptions and test reports.</p> : (
          <>
            <div className="mb-4 h-1.5 overflow-hidden rounded-full bg-line"><motion.div className="h-full rounded-full bg-covered" animate={{ width: `${(done / ck.claim_documents.length) * 100}%` }} /></div>
            <ul className="space-y-1.5">
              {ck.claim_documents.map((d) => {
                const on = ready.includes(d.text);
                return (
                  <li key={d.text}>
                    <button type="button" onClick={() => toggle(d.text)} aria-pressed={on}
                      className={cn("flex w-full items-center gap-3 rounded-[6px] border px-3 py-2.5 text-left text-[14px] transition-colors", on ? "border-covered/30 bg-covered-bg text-ink" : "border-line hover:border-line-2")}>
                      {on ? <CheckCircle2 className="size-[18px] text-covered" /> : <span className="size-[18px] rounded-full border-2 border-line-2" aria-hidden />}
                      <span className={cn(on && "line-through decoration-covered/40")}>{d.text}</span>
                    </button>
                  </li>);
              })}
            </ul>
          </>)}
        {ck.notice.map((n) => <p key={n.text} className="mt-3 flex items-start gap-2 text-[13px] text-conditional"><Clock3 className="mt-0.5 size-4 shrink-0" />{n.text}</p>)}
      </Section>

      <Section title="When waiting periods end" description={ck.policy_start ? `Counted from your cover start, ${fmtDate(ck.policy_start)}.` : "Your policy's start date wasn't found, so exact dates can't be worked out."}>
        {ck.waits.length === 0 ? <p className="text-sm text-muted">No waiting periods were found in this policy.</p> : (
          <ul className="space-y-3">
            {ck.waits.map((w) => (
              <li key={w.clause + w.label} className="flex items-start gap-3 rounded-[6px] border border-line p-3">
                <span className={cn("grid size-9 shrink-0 place-items-center rounded-full", w.done ? "bg-covered-bg text-covered" : "bg-review-bg text-review")}>
                  {w.done ? <CalendarCheck2 className="size-[18px]" /> : <Hourglass className="size-[18px]" />}</span>
                <div className="min-w-0 flex-1">
                  <p className="text-[14px] text-ink">{w.label}</p>
                  <p className="mt-0.5 text-[12.5px] text-muted">{w.months ? `${w.months} months` : `${w.days} days`} wait
                    {w.covered_from && <> · <span className={cn("font-medium", w.done ? "text-covered" : "text-review")}>{w.done ? `covered since ${fmtDate(w.covered_from)}` : `covered from ${fmtDate(w.covered_from)}`}</span></>}</p>
                </div>
                <ClauseRefBtn docId={id} section={w.clause} />
              </li>))}
          </ul>)}
      </Section>

      <Section title="What you'll pay yourself" description="Set aside for these on any claim.">
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-[6px] bg-paper p-4"><p className="flex items-center gap-1.5 text-[12px] text-muted"><Wallet className="size-3.5" />First, each year</p>
            <p className="mt-1 font-display text-[30px] text-ink num">{ck.deductible ? rupees(ck.deductible.amount) : "None found"}</p>
            {ck.deductible && <div className="mt-1"><ClauseRefBtn docId={id} section={ck.deductible.clause} /></div>}</div>
          <div className="rounded-[6px] bg-paper p-4"><p className="flex items-center gap-1.5 text-[12px] text-muted"><Wallet className="size-3.5" />Then, of every claim</p>
            <p className="mt-1 font-display text-[30px] text-ink num">{ck.copay ? `${ck.copay.percent}%` : "None found"}</p>
            {ck.copay && <div className="mt-1"><ClauseRefBtn docId={id} section={ck.copay.clause} /></div>}</div>
        </div>
      </Section>

      <Section title="Bills from before and after a stay" description="Related costs your policy pays around a hospital admission.">
        {ck.window ? (
          <div className="flex items-center gap-4">
            <div className="flex-1 rounded-[6px] bg-paper p-4 text-center"><p className="font-display text-[34px] text-ink num">{ck.window.before}</p><p className="text-[12px] text-muted">days before admission</p></div>
            <span className="text-faint">→ stay →</span>
            <div className="flex-1 rounded-[6px] bg-paper p-4 text-center"><p className="font-display text-[34px] text-ink num">{ck.window.after}</p><p className="text-[12px] text-muted">days after discharge</p></div>
            <ClauseRefBtn docId={id} section={ck.window.clause} />
          </div>
        ) : <p className="text-sm text-muted">Your policy doesn't mention pre- or post-hospitalisation cover.</p>}
        <p className="mt-3 text-[12.5px] text-muted">Keep those bills and prescriptions too: they can be claimed with the hospital bill.</p>
      </Section>
    </div>
  );
}

/* ============================================================== Reports: a printable policy summary */

function ReportPreview({ policy }: { policy: DocumentRecord }) {
  const [sum, setSum] = useState<import("../lib/types").PolicySummary | null>(null);
  useEffect(() => { api.policySummary(policy.document_id, "en").then(setSum).catch(() => setSum(null)); }, [policy.document_id]);
  if (!sum) return <Spinner label="Preparing the preview…" />;
  return <PolicyBrief summary={sum} docId={policy.document_id} lang="en" clauseCount={policy.clause_count} title={policy.metadata.title ?? undefined} />;
}

export function PolicyReport({ policy }: { policy: DocumentRecord }) {
  const contents = useMemo(() => ["Policy details: insurer, number, period, sum insured", "Key numbers: what you pay first, co-payment, caps",
    "What is covered, with clause references", "Limits on what is paid", "What is not covered", "Waiting periods and the dates they end",
    "Documents to keep for a claim"], []);
  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_340px]">
      <Section title={policy.metadata.title ?? policy.filename} description="A printable summary of your policy, made from its clauses.">
        <p className="eyebrow mb-2">What's in it</p>
        <ul className="grid gap-1.5 text-sm sm:grid-cols-2">{contents.map((c) => <li key={c} className="flex items-center gap-2"><span className="size-1.5 rounded-full bg-accent" aria-hidden />{c}</li>)}</ul>
        <p className="mt-4 text-[13px] text-muted">Once you analyse a hospital bill, a full claim report (line-by-line decisions, evidence and calculation) appears here too.</p>
      </Section>
      <Section title="Download">
        <a className="btn-primary w-full" href={api.policySummaryPdfUrl(policy.document_id)} download data-testid="download-policy-pdf"><FileText className="size-4" /> Policy summary (PDF) <Download className="ml-auto size-4" /></a>
        <Disclaimer className="mt-4" />
      </Section>
      <div className="lg:col-span-2"><Section title="Preview" description="What the PDF contains, as it appears on screen."><ReportPreview policy={policy} /></Section></div>
      <div className="lg:col-span-2"><KeyTerms policy={policy} /></div>
    </div>
  );
}
