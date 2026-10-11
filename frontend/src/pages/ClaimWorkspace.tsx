import { CheckCircle2, ChevronDown, CircleAlert, GitBranch, Plus, Trash2, Upload, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { BillEditor, BillReview } from "../components/BillEditor";
import { ComparisonView } from "../components/ComparisonView";
import { Ledger } from "../components/Ledger";
import { ClauseRef, Disclaimer, ErrorNote, PageHeader, Range, Section, Spinner, Stat, SyntheticBanner, Tag } from "../components/ui";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { cn, fmtDate, inr, STAGE_LABEL } from "../lib/format";
import { useApp } from "../lib/store";
import { BillSnapshot } from "../components/BillSnapshot";
import type { Analysis, Bill, BillItemEdit, ClaimBundle, ClaimFacts, Tri } from "../lib/types";

const FACTS: { key: keyof ClaimFacts; label: string; help: string }[] = [
  { key: "vitamin_prescription", label: "Vitamin/supplement prescribed by treating doctor", help: "Exception in exclusion 4.2-type clauses" },
  { key: "implant_invoice_submitted", label: "Implant invoice and barcode sticker submitted", help: "Condition in implant coverage clauses" },
  { key: "post_hospitalisation_same_condition", label: "Post-hospitalisation expenses relate to the same condition", help: "Condition in pre/post-hospitalisation cover" },
  { key: "pre_existing_condition", label: "Condition is pre-existing", help: "Pre-existing disease waiting period" },
  { key: "accident", label: "Treatment arose from an accident or injury", help: "Exception to waiting periods / cosmetic exclusion" },
];

function FactsEditor({ bundle, onChanged }: { bundle: ClaimBundle; onChanged: () => Promise<void> }) {
  const [facts, setFacts] = useState<ClaimFacts>(bundle.claim.facts);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => setFacts(bundle.claim.facts), [bundle.claim.facts]);
  const dirty = JSON.stringify(facts) !== JSON.stringify(bundle.claim.facts);
  return (
    <Section title="Claim facts" description="User-asserted facts that resolve conditions in the policy. Changing them re-runs the analysis and records why the result changed.">
      <div className="space-y-3">
        {FACTS.map((f) => (
          <div key={f.key} className="flex flex-col gap-1.5 sm:flex-row sm:items-center sm:justify-between">
            <div><p className="text-sm text-text">{f.label}</p><p className="text-xs text-faint">{f.help}</p></div>
            <div className="flex shrink-0 rounded-lg border border-line-2 p-0.5" role="radiogroup" aria-label={f.label}>
              {(["yes", "no", "unknown"] as Tri[]).map((v) => (
                <button key={v} role="radio" aria-checked={facts[f.key] === v} onClick={() => setFacts({ ...facts, [f.key]: v })}
                  className={cn("rounded-md px-2.5 py-1 text-xs capitalize", facts[f.key] === v ? "chip-on" : "text-muted hover:text-text")}>{v}</button>
              ))}
            </div>
          </div>
        ))}
        <div className="grid gap-3 sm:grid-cols-2">
          <label><span className="label">Deductible already used this policy year (₹)</span>
            <input className="input num" inputMode="decimal" value={facts.deductible_used_this_year} onChange={(e) => setFacts({ ...facts, deductible_used_this_year: e.target.value })} /></label>
          <label><span className="label">Sum insured already used this year (₹)</span>
            <input className="input num" inputMode="decimal" value={facts.sum_insured_used_this_year} onChange={(e) => setFacts({ ...facts, sum_insured_used_this_year: e.target.value })} /></label>
        </div>
        <ErrorNote error={err} />
        <button className="btn-primary" disabled={!dirty || busy} data-testid="save-facts" onClick={async () => {
          setBusy(true); setErr(null);
          try { await api.updateClaim(bundle.claim.claim_id, { facts }); await onChanged(); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
        }}>{busy ? <Spinner label="Recalculating…" /> : "Save facts and re-analyse"}</button>
      </div>
    </Section>
  );
}

function VersionCard({ a }: { a: Analysis }) {
  const v = a.version;
  return (
    <Section title="Applicable policy version" description="Selected from effective dates and applicability statements in the documents.">
      <div className="flex items-start gap-3">
        <GitBranch className="mt-0.5 size-5 text-accent" aria-hidden />
        <div className="min-w-0">
          <p className="font-semibold text-ink" data-testid="version-label">{v.selected?.label ?? "Not determined"}</p>
          <p className="text-xs text-muted num">Treatment date {fmtDate(v.treatment_date)}{v.selected && ` · effective ${fmtDate(v.selected.effective_from)} – ${fmtDate(v.selected.effective_to)}`}</p>
        </div>
        {v.review_required && <Tag tone="review" className="ml-auto">Review</Tag>}
      </div>
      <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-text">{v.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
      {v.conflicts.map((c) => <ErrorNote key={c} error={c} className="mt-2" />)}
      {v.alternatives.length > 0 && <p className="mt-3 text-xs text-muted">Other versions: {v.alternatives.map((x) => x.label).join(", ")} — compare them in the What-If Lab.</p>}
      {a.claim_checks.length > 0 && (
        <div className="mt-4 border-t border-line pt-3">
          <p className="eyebrow mb-2">Claim-level eligibility checks</p>
          <ul className="space-y-1.5">
            {a.claim_checks.map((c) => (
              <li key={c.check} className="flex items-start gap-2 text-sm">
                {c.status === "satisfied" ? <CheckCircle2 className="mt-0.5 size-4 text-covered" aria-label="satisfied" /> :
                  c.status === "not_satisfied" ? <XCircle className="mt-0.5 size-4 text-excluded" aria-label="not satisfied" /> :
                    c.status === "unknown" ? <CircleAlert className="mt-0.5 size-4 text-review" aria-label="unknown" /> :
                      <span className="mt-0.5 size-4 text-center text-faint" aria-label="not applicable">–</span>}
                <span><span className="font-medium">{c.check}</span> {c.clause_ids.map((x) => <ClauseRef key={x} id={x} />)} <span className="text-muted">{c.detail}</span></span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Section>
  );
}

function Trace({ a }: { a: Analysis }) {
  const [mode, setMode] = useState<"low" | "high">("low");
  const steps = mode === "low" ? a.trace_low : a.trace_high;
  return (
    <Section title="Calculation trace" description={`Deterministic, in the order stated by ${a.summary.order_source}.`}
      actions={<div className="flex rounded-lg border border-line-2 p-0.5 text-xs">
        <button className={cn("rounded-md px-2.5 py-1", mode === "low" ? "chip-on" : "text-muted")} onClick={() => setMode("low")}>Definite</button>
        <button className={cn("rounded-md px-2.5 py-1", mode === "high" ? "chip-on" : "text-muted")} onClick={() => setMode("high")}>Upper bound</button>
      </div>}>
      <ol className="space-y-2" data-testid="trace">
        {steps.map((s) => (
          <li key={s.step_no} className="grid grid-cols-[28px_1fr_auto] items-start gap-3 rounded-lg border border-line p-2.5">
            <span className="grid size-7 place-items-center rounded-full bg-paper text-xs font-semibold text-ink num">{s.step_no}</span>
            <div className="min-w-0">
              <p className="text-sm font-medium text-ink">{STAGE_LABEL[s.stage] ?? s.stage}</p>
              <p className="text-xs text-muted">{s.description} {s.clause_ids.map((c) => <ClauseRef key={c} id={c} />)}</p>
              {s.adjustments.length > 0 && <p className="mt-0.5 text-[11px] text-faint">{s.adjustments.length} tracked adjustment(s)</p>}
            </div>
            <div className="text-right text-sm num">
              {s.amount_before !== s.amount_after && <p className="text-xs text-faint line-through">{inr(s.amount_before)}</p>}
              <p className="font-semibold text-ink">{inr(s.amount_after)}</p>
            </div>
          </li>
        ))}
      </ol>
      <details className="mt-3 text-sm">
        <summary className="cursor-pointer text-muted">Engine invariant checks ({a.invariants.filter((i) => i.passed).length}/{a.invariants.length} passed)</summary>
        <ul className="mt-2 space-y-1">{a.invariants.map((i) => (
          <li key={i.name} className="flex items-start gap-2 text-xs">{i.passed ? <CheckCircle2 className="size-3.5 text-covered" /> : <XCircle className="size-3.5 text-excluded" />}<span>{i.name} {i.detail && <span className="text-faint">({i.detail})</span>}</span></li>
        ))}</ul>
      </details>
    </Section>
  );
}

/** One numbered step of the claim form, joined to the next by a thin rule. */
function Step({ n, title, hint, done, last, children }: { n: number; title: string; hint?: string; done?: boolean; last?: boolean; children: React.ReactNode }) {
  return (
    <section className="relative grid grid-cols-[36px_1fr] gap-x-4">
      {!last && <span className="absolute bottom-0 left-[17px] top-10 w-px bg-line-2" aria-hidden />}
      <span className={cn("relative z-[1] grid size-9 place-items-center rounded-full border font-display text-[18px] transition-colors",
        done ? "border-covered bg-covered text-paperwhite" : "border-brass bg-card text-ink")}>
        {done ? <CheckCircle2 className="size-[18px]" /> : n}</span>
      <div className={cn("min-w-0", !last && "pb-8")}>
        <h3 className="pt-1.5 text-[16px] font-semibold tracking-tight text-ink">{title}</h3>
        {hint && <p className="mt-0.5 text-[12.5px] text-muted">{hint}</p>}
        <div className="mt-4">{children}</div>
      </div>
    </section>
  );
}

function NewClaimForm({ onDone }: { onDone: () => void }) {
  const { documents, refresh, setActiveClaimId } = useApp();
  const policies = documents.filter((d) => d.doc_type === "policy");
  const ends = documents.filter((d) => d.doc_type === "endorsement");
  const [policyId, setPolicyId] = useState(policies[0]?.document_id ?? "");
  const [endIds, setEndIds] = useState<string[]>([]);
  const [bill, setBill] = useState<Bill | null>(null);
  const [billRows, setBillRows] = useState<BillItemEdit[] | null>(null);   // lines the user reviewed (and possibly corrected)
  const [manual, setManual] = useState([{ description: "", amount: "", quantity: "1", service_date: "" }]);
  const [mode, setMode] = useState<"upload" | "manual">("upload");
  const [title, setTitle] = useState("");
  const [adm, setAdm] = useState("");
  const [dis, setDis] = useState("");
  const [diag, setDiag] = useState("");
  const [progress, setProgress] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (!policies.length) return <div className="flex flex-wrap items-center gap-3 text-sm text-muted">Upload your policy wording first. <Link to="/documents" className="btn-secondary">Go to Documents</Link></div>;

  const billReady = mode === "upload" ? !!bill && !!billRows : manual.some((m) => m.description && m.amount);
  const ready = !!policyId && billReady && !!adm;
  const analyse = async () => {
        setBusy(true); setErr(null);
        try {
          const body: Record<string, unknown> = { title: title || "New claim", policy_document_id: policyId, endorsement_ids: endIds, admission_date: adm,
            discharge_date: dis || null, diagnosis: diag || "Not found in the provided documents" };
          if (mode === "upload") { body.bill = bill; body.bill_items = billRows; }
          else body.items = manual.filter((m) => m.description && m.amount).map((m) => ({ description: m.description, amount: m.amount, quantity: m.quantity || "1", service_date: adm }));
          const r = await api.createClaim(body);
          setActiveClaimId(r.claim.claim_id);
          await refresh();
          onDone();
        } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }};

  return (
    <div className="pt-1">
      <Step n={1} title="Which policy should we check against?" hint="Nivaaran works out which endorsements apply from their effective dates." done={!!policyId}>
        <div className="grid gap-4 md:grid-cols-2">
          <label><span className="label">Policy wording</span>
            <select className="input" value={policyId} onChange={(e) => setPolicyId(e.target.value)}>
              {policies.map((p) => <option key={p.document_id} value={p.document_id}>{p.metadata.title ?? p.filename}</option>)}
            </select></label>
          <fieldset><legend className="label">Endorsements to consider</legend>
            {ends.length === 0 ? <p className="pt-2 text-sm text-muted">None uploaded.</p> : (
              <div className="flex flex-wrap gap-2 pt-0.5">
                {ends.map((e) => {
                  const on = endIds.includes(e.document_id);
                  return (
                    <label key={e.document_id} className={cn("inline-flex cursor-pointer items-center gap-2 rounded-full border px-3 py-1.5 text-[13px] transition-colors",
                      on ? "border-accent bg-covered-bg text-accent" : "border-line-2 text-muted hover:border-ink/40")}>
                      <input type="checkbox" className="sr-only" checked={on} onChange={(ev) => setEndIds(ev.target.checked ? [...endIds, e.document_id] : endIds.filter((x) => x !== e.document_id))} />
                      {on ? <CheckCircle2 className="size-3.5" /> : <Plus className="size-3.5" />}
                      {e.metadata.endorsement_number} <span className="text-faint">from {e.metadata.effective_date}</span>
                    </label>);
                })}
              </div>)}
          </fieldset>
        </div>
      </Step>

      <Step n={2} title="The hospital bill" hint="Upload the itemised bill and check each line, or type the charges in yourself." done={billReady}>
        <div className="mb-4 inline-flex rounded-full border border-line-2 bg-paper p-1" role="tablist">
          {(["upload", "manual"] as const).map((m) => (
            <button key={m} role="tab" aria-selected={mode === m} onClick={() => setMode(m)}
              className={cn("rounded-full px-4 py-1.5 text-[13px] font-medium transition-colors", mode === m ? "bg-ink text-paperwhite" : "text-muted hover:text-ink")}>
              {m === "upload" ? "Upload itemised bill" : "Enter items manually"}</button>
          ))}
        </div>
        {mode === "upload" ? (
          <div>
          <label className={cn("flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-line-2 px-4 py-8 text-center transition-colors hover:bg-paper",
            progress !== null && "pointer-events-none opacity-60")}>
            <Upload className="size-6 text-muted" aria-hidden />
            <span className="mt-2 text-sm font-medium text-text">{bill ? "Upload a different bill" : "Drop your itemised hospital bill here or click to choose"}</span>
            <span className="text-xs text-muted">PDF, JPEG, PNG, CSV or JSON · every line is read for you to check</span>
            <input type="file" accept=".pdf,.csv,.json,.png,.jpg,.jpeg,application/pdf,text/csv,application/json,image/png,image/jpeg" className="sr-only" data-testid="bill-upload" onChange={async (e) => {
              const f = e.target.files?.[0]; if (!f) return;
              setErr(null); setBill(null); setBillRows(null); setProgress(0);
              try {
                const b = await api.parseBill(f, setProgress);
                setBill(b);
                if (b.admission_date) setAdm(b.admission_date);
                if (b.discharge_date) setDis(b.discharge_date);
                if (b.diagnosis && !b.diagnosis.startsWith("Not found")) setDiag(b.diagnosis);
              } catch (er) { setErr((er as Error).message); } finally { setProgress(null); }
            }} /></label>
          {progress !== null && <Spinner label={`Reading bill… ${progress}%`} />}
          {bill && (
            <div className="mt-4 space-y-4">
              <BillSnapshot bill={bill} />
              {billRows ? (
                <div className="flex flex-wrap items-center gap-3 rounded-[6px] border border-covered/30 bg-covered-bg px-4 py-3 text-sm">
                  <CheckCircle2 className="size-5 text-covered" />
                  <span className="text-ink"><strong>{billRows.length} lines checked.</strong> <span className="text-muted">The bill's original wording is kept next to anything you corrected.</span></span>
                  <div className="flex-1" />
                  <button className="btn-ghost h-8 px-3 text-[12.5px]" onClick={() => setBillRows(null)}>Check again</button>
                </div>
              ) : (
                <div>
                  <p className="mb-2.5 text-[13px] text-muted">Read down the lines and compare them with your paper bill. Click any description, quantity or amount to fix it.</p>
                  <BillEditor items={bill.items} statedTotal={bill.stated_total} onSave={setBillRows} saveLabel="These lines are correct" />
                </div>
              )}
            </div>
          )}
          </div>
        ) : (
        <div className="space-y-2">
          {manual.map((m, i) => (
            <div key={i} className="grid grid-cols-[1fr_110px_70px_auto] gap-2">
              <input className="input" placeholder="Description (as billed)" value={m.description} aria-label={`Item ${i + 1} description`} onChange={(e) => setManual(manual.map((x, j) => j === i ? { ...x, description: e.target.value } : x))} />
              <input className="input num" placeholder="Amount ₹" inputMode="decimal" value={m.amount} aria-label={`Item ${i + 1} amount`} onChange={(e) => setManual(manual.map((x, j) => j === i ? { ...x, amount: e.target.value } : x))} />
              <input className="input num" placeholder="Qty" value={m.quantity} aria-label={`Item ${i + 1} quantity`} onChange={(e) => setManual(manual.map((x, j) => j === i ? { ...x, quantity: e.target.value } : x))} />
              <button className="btn-ghost px-2" aria-label="Remove item" onClick={() => setManual(manual.filter((_, j) => j !== i))}><Trash2 className="size-4" /></button>
            </div>
          ))}
          <button className="btn-ghost text-xs" onClick={() => setManual([...manual, { description: "", amount: "", quantity: "1", service_date: "" }])}><Plus className="size-3.5" /> Add item</button>
        </div>
        )}
      </Step>

      <Step n={3} title="About the treatment" hint="Dates decide which policy version and waiting periods apply. We filled in what the bill says." done={!!adm} last>
        <div className="grid gap-4 md:grid-cols-4">
          <label className="md:col-span-2"><span className="label">Name this claim</span><input className="input" value={title} placeholder="e.g. Angioplasty, March 2026" onChange={(e) => setTitle(e.target.value)} /></label>
          <label><span className="label">Admitted on</span><input type="date" className="input" value={adm} onChange={(e) => setAdm(e.target.value)} required /></label>
          <label><span className="label">Discharged on</span><input type="date" className="input" value={dis} onChange={(e) => setDis(e.target.value)} /></label>
          <label className="md:col-span-4"><span className="label">Diagnosis or procedure</span><input className="input" value={diag} onChange={(e) => setDiag(e.target.value)} placeholder="Used to check waiting periods" /></label>
        </div>
      </Step>

      <ErrorNote error={err} className="mt-6" />
      <div className="mt-6 flex flex-wrap items-center gap-x-5 gap-y-3 rounded-[6px] border border-line bg-paper px-4 py-3.5">
        <ul className="flex flex-1 flex-wrap gap-x-5 gap-y-1 text-[12.5px]">
          {[["Policy chosen", !!policyId], [mode === "upload" ? "Bill lines checked" : "Charges entered", billReady], ["Admission date", !!adm]].map(([label, ok]) => (
            <li key={label as string} className={cn("inline-flex items-center gap-1.5", ok ? "text-covered" : "text-faint")}>
              {ok ? <CheckCircle2 className="size-3.5" /> : <span className="size-3.5 rounded-full border border-current" aria-hidden />}{label}</li>))}
        </ul>
        <button className="btn-primary h-11 px-6 text-[15px]" disabled={busy || !ready} onClick={analyse}>{busy ? <Spinner label="Adjudicating…" /> : "Analyse claim"}</button>
      </div>
    </div>
  );
}

export default function ClaimWorkspace() {
  const { bundle, refreshClaim, refresh, claims, loading } = useApp();
  const [showNew, setShowNew] = useState(false);
  const [cmpIdx, setCmpIdx] = useState<number | null>(null);
  const a = bundle?.analysis;
  const comps = bundle?.comparisons ?? [];
  const cmp = comps.length ? comps[cmpIdx ?? comps.length - 1] : null;
  const onChanged = async () => { await refreshClaim(); await refresh(); setCmpIdx(null); };

  return (
    <div>
      <PageHeader eyebrow="Claim workspace" title={bundle?.claim.title ?? "Itemised claim adjudication"}
        description="Every charge on the bill, matched to the clause that decides it. Anything the documents don't settle stays unresolved rather than guessed."
        actions={<button className="btn-secondary" onClick={() => setShowNew(!showNew)}><Plus className="size-4" /> New claim <ChevronDown className={cn("size-4 transition-transform", showNew && "rotate-180")} /></button>} />
      {(showNew || (!loading && claims.length === 0)) && (
        <Section title="Create a claim" description="Choose the policy, upload or enter the itemised bill, and give the treatment date." className="mb-5">
          <NewClaimForm onDone={() => setShowNew(false)} />
        </Section>
      )}
      {loading && <Spinner />}
      {a && bundle && (
        <>
          <SyntheticBanner show={a.synthetic} />
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <Stat label="Total billed" value={inr(a.summary.total_billed)} sub={`${a.rows.length} items, original amounts`} />
            <Stat label="Eligible (definite)" value={inr(a.summary.eligible_definite)} sub="After exclusions and item limits" />
            <Stat testId="claim-payable" label="Estimated payable" value={<Range low={a.summary.payable_low} high={a.summary.payable_high} />} sub="Not an insurer decision" tone="covered" />
            <Stat label="Potential out-of-pocket" value={<Range low={a.summary.patient_low} high={a.summary.patient_high} />} sub="Patient responsibility range" />
            <Stat label="Unresolved exposure" value={inr(a.summary.unresolved_exposure)} sub={`${a.rows.filter((r) => r.manual_review).length} items need review`} tone="conditional" />
          </div>
          {a.bill_issues.length > 0 && <div className="mt-4 space-y-2">{a.bill_issues.map((i) => <ErrorNote key={i.message} error={`Bill check: ${i.message}`} />)}</div>}
          <Section title="Itemised adjudication ledger" description="Expand a row to see the exact clause excerpts, page references, verification outcome and calculation." className="mt-5">
            <Ledger analysis={a} initialOpen={new URLSearchParams(window.location.search).get("item") ?? undefined} />
          </Section>
          <Section title="Hospital bill lines" className="mt-5"
            description="What was read from the bill, and what you corrected. Corrections re-run the analysis; the originally extracted values are kept.">
            <BillReview items={bundle.claim.bill.items} removed={bundle.claim.bill.removed_items ?? []} reviewedAt={bundle.claim.bill.reviewed_at}
              statedTotal={bundle.claim.bill.stated_total} computedTotal={bundle.claim.bill.computed_total}
              onSave={async (rows) => { await api.updateClaim(bundle.claim.claim_id, { bill_items: rows }); await onChanged(); }}
              onConfirm={async () => { await api.updateClaim(bundle.claim.claim_id, { confirm_bill: true }); await onChanged(); }} />
          </Section>
          <div className="mt-5 grid gap-5 xl:grid-cols-2">
            <VersionCard a={a} />
            <Trace a={a} />
          </div>
          {cmp && (
            <Section title="Before and after" className="mt-5" description="Every recorded change to this claim's estimate, with the reason for each difference."
              actions={comps.length > 1 && (
                <select className="input w-auto text-xs" value={cmpIdx ?? comps.length - 1} onChange={(e) => setCmpIdx(Number(e.target.value))} aria-label="Select recorded change">
                  {comps.map((c, i) => <option key={c.comparison_id} value={i}>{i + 1}. {c.cause}</option>)}
                </select>)}>
              <ComparisonView c={cmp} />
            </Section>
          )}
          <div className="mt-5 grid gap-5 xl:grid-cols-2">
            <FactsEditor bundle={bundle} onChanged={onChanged} />
            <Section title="Financial summary" description="How the estimate is composed.">
              <ul className="space-y-1.5 text-sm text-text">{a.summary.explanation.map((e) => <li key={e} className="leading-relaxed">• {e}</li>)}</ul>
              <Disclaimer className="mt-4" />
            </Section>
          </div>
        </>
      )}
    </div>
  );
}
