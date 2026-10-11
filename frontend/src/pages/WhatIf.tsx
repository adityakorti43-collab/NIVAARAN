import { RotateCcw, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { ComparisonView } from "../components/ComparisonView";
import { Ledger } from "../components/Ledger";
import { NeedClaim } from "../components/NeedClaim";
import { PolicyEstimator } from "../components/PolicyMode";
import { ErrorNote, HypotheticalBanner, PageHeader, Range, Section, Spinner, SyntheticBanner, Tag } from "../components/ui";
import { api } from "../lib/api";
import { cn, inr, sec } from "../lib/format";
import type { Analysis, ClaimBundle, Clause, Comparison, Hypotheticals } from "../lib/types";

export default function WhatIf() {
  return (
    <div>
      <PageHeader eyebrow="What-if calculator" title="Explore scenarios before you decide"
        description="Change the date, the policy version or the bill and see the new estimate. It uses the same calculation as the real claim, and anything you change is marked as hypothetical." />
      <NeedClaim policyView={(p) => <PolicyEstimator policy={p} />}>{(b) => <Lab bundle={b} />}</NeedClaim>
    </div>
  );
}

function Lab({ bundle }: { bundle: ClaimBundle & { analysis: Analysis } }) {
  const a = bundle.analysis;
  const [clauses, setClauses] = useState<Record<string, Clause>>({});
  const [versions, setVersions] = useState<{ version_id: string; label: string }[]>([]);
  const [hyp, setHyp] = useState<Hypotheticals>({});
  const [result, setResult] = useState<{ analysis: Analysis; comparison: Comparison } | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [vcmp, setVcmp] = useState<Awaited<ReturnType<typeof api.compareVersions>> | null>(null);
  const [saved, setSaved] = useState<any[]>([]);
  const [scName, setScName] = useState("");
  useEffect(() => { api.scenarios(bundle.claim.claim_id).then(setSaved).catch(() => setSaved([])); }, [bundle.claim.claim_id]);

  useEffect(() => {
    const ids = [bundle.claim.policy_document_id, ...bundle.claim.endorsement_ids];
    Promise.all(ids.map((i) => api.document(i))).then((docs) => {
      const m: Record<string, Clause> = {};
      docs.forEach((d) => d.clauses?.forEach((c) => (m[c.clause_id] = c)));
      setClauses(m);
    });
    api.versions(bundle.claim.policy_document_id).then((v) => setVersions(v.versions.filter((x) => x.endorsement_ids.every((e) => bundle.claim.endorsement_ids.includes(e)))));
  }, [bundle.claim]);

  const dedClause = a.trace_low.find((s) => s.stage === "deductible")?.clause_ids[0];
  const copayClause = a.trace_low.find((s) => s.stage === "copay")?.clause_ids[0];
  const limitClauses = useMemo(() => {
    const ids = new Set<string>();
    a.rows.forEach((r) => r.evidence.forEach((e) => (e.relation === "limit" || e.relation === "override_support") && r.supporting_clause_ids.includes(e.clause_id) && ids.add(e.clause_id)));
    return [...ids].filter((i) => clauses[i]?.interpretation.limit?.amount);
  }, [a.rows, clauses]);

  const set = (patch: Partial<Hypotheticals>) => setHyp({ ...hyp, ...patch });
  const active = Object.values(hyp).some((v) => v !== undefined && v !== null && v !== "" && !(Array.isArray(v) && !v.length) && !(typeof v === "object" && !Array.isArray(v) && !Object.keys(v).length));

  async function run() {
    setBusy(true); setErr(null);
    try { setResult(await api.scenario(bundle.claim.claim_id, hyp)); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }

  return (
    <>
      <SyntheticBanner show={a.synthetic} />
      <div className="grid gap-5 xl:grid-cols-[400px_1fr]">
        <div className="space-y-5">
          <Section title="Scenario inputs" description="Leave a field empty to use the documented value."
            actions={active && <button className="btn-ghost text-xs" onClick={() => { setHyp({}); setResult(null); }}><RotateCcw className="size-3.5" /> Reset</button>}>
            <div className="space-y-4">
              <label className="block"><span className="label">Treatment (admission) date</span>
                <input type="date" className="input" value={hyp.treatment_date ?? ""} onChange={(e) => set({ treatment_date: e.target.value || null })} />
                <span className="mt-1 block text-xs text-faint">Documented: {bundle.claim.admission_date}. The version registry re-selects the applicable version.</span></label>
              <label className="block"><span className="label">Policy version (override)</span>
                <select className="input" value={hyp.version_id ?? ""} onChange={(e) => set({ version_id: e.target.value || null })}>
                  <option value="">Select by treatment date (documented rule)</option>
                  {versions.map((v) => <option key={v.version_id} value={v.version_id}>{v.label}</option>)}
                </select></label>
              <div className="grid grid-cols-2 gap-3">
                <label><span className="label">Deductible (₹)</span>
                  <input className="input num" inputMode="decimal" placeholder={dedClause ? clauses[dedClause]?.interpretation.amount ?? "" : "not in policy"}
                    disabled={!dedClause} value={hyp.deductible ?? ""} onChange={(e) => set({ deductible: e.target.value || null })} />
                  <span className="mt-1 block text-[11px] text-faint">{dedClause ? `Policy: clause ${sec(dedClause)}` : "Not supported: no deductible clause"}</span></label>
                <label><span className="label">Co-payment (%)</span>
                  <input className="input num" inputMode="decimal" placeholder={copayClause ? clauses[copayClause]?.interpretation.percent ?? "" : "not in policy"}
                    disabled={!copayClause} value={hyp.copay_percent ?? ""} onChange={(e) => set({ copay_percent: e.target.value || null })} />
                  <span className="mt-1 block text-[11px] text-faint">{copayClause ? `Policy: clause ${sec(copayClause)}` : "Not supported"}</span></label>
              </div>
              {limitClauses.length > 0 && (
                <div><p className="label">Limits</p>
                  <div className="space-y-2">
                    {limitClauses.map((cid) => {
                      const lim = clauses[cid].interpretation.limit!;
                      return (
                        <label key={cid} className="grid grid-cols-[1fr_120px] items-center gap-2">
                          <span className="text-sm">{sec(cid)} {clauses[cid].heading} <span className="text-xs text-faint">({lim.basis.replace("_", " ")})</span></span>
                          <input className="input num" inputMode="decimal" placeholder={lim.amount ?? ""} aria-label={`Limit for ${clauses[cid].heading}`}
                            value={hyp.limit_overrides?.[cid] ?? ""} onChange={(e) => {
                              const lo = { ...(hyp.limit_overrides ?? {}) };
                              if (e.target.value) lo[cid] = e.target.value; else delete lo[cid];
                              set({ limit_overrides: lo });
                            }} />
                        </label>);
                    })}
                  </div>
                </div>
              )}
            </div>
          </Section>
          <Section title="Bill items" description="Edit amounts or exclude items from the scenario.">
            <ul className="max-h-[420px] space-y-1.5 overflow-y-auto pr-1">
              {bundle.claim.bill.items.map((i) => {
                const removed = hyp.removed_items?.includes(i.item_id);
                return (
                  <li key={i.item_id} className={cn("grid grid-cols-[auto_1fr_110px] items-center gap-2 rounded-lg px-1.5 py-1", removed && "opacity-50")}>
                    <input type="checkbox" checked={!removed} aria-label={`Include ${i.description}`} onChange={(e) => {
                      const r = new Set(hyp.removed_items ?? []);
                      e.target.checked ? r.delete(i.item_id) : r.add(i.item_id);
                      set({ removed_items: [...r] });
                    }} />
                    <span className={cn("truncate text-sm", removed && "line-through")}>{i.description}</span>
                    <input className="input num py-1 text-right" inputMode="decimal" placeholder={i.amount} aria-label={`Amount for ${i.description}`}
                      value={hyp.item_amounts?.[i.item_id] ?? ""} onChange={(e) => {
                        const m = { ...(hyp.item_amounts ?? {}) };
                        if (e.target.value) m[i.item_id] = e.target.value; else delete m[i.item_id];
                        set({ item_amounts: m });
                      }} />
                  </li>);
              })}
            </ul>
          </Section>
          <ErrorNote error={err} />
          <button className="btn-primary w-full" disabled={!active || busy} onClick={run} data-testid="run-scenario">
            {busy ? <Spinner label="Recalculating…" /> : <><Sparkles className="size-4" /> Recalculate scenario</>}
          </button>
        </div>
        <div className="space-y-5 min-w-0">
          {!result ? (
            <Section title="Current estimate" description="Based only on the documents and stated claim facts.">
              <p className="text-2xl font-semibold num text-ink"><Range low={a.summary.payable_low} high={a.summary.payable_high} /></p>
              <p className="mt-1 text-sm text-muted">Estimated payable under '{a.version.selected?.label}'. Change an input and recalculate to compare.</p>
            </Section>
          ) : (
            <>
              <HypotheticalBanner>{result.analysis.summary.explanation.filter((e) => e.startsWith("HYPOTHETICAL")).join(" ") || "Scenario inputs are assumptions, not policy terms."}</HypotheticalBanner>
              <Section title="Scenario vs current claim" description="Your saved analysis is unchanged; this is a separate calculation."
                actions={<form className="flex gap-2" onSubmit={async (e) => { e.preventDefault(); if (!scName.trim()) return;
                  try { const s = await api.saveScenario(bundle.claim.claim_id, scName.trim(), hyp); setSaved([...saved, s]); setScName(""); } catch (x) { setErr((x as Error).message); } }}>
                  <input className="input h-9 w-44 text-xs" placeholder="Name this scenario" value={scName} onChange={(e) => setScName(e.target.value)} aria-label="Scenario name" data-testid="scenario-name" />
                  <button className="btn-secondary h-9 text-xs" disabled={!scName.trim()} data-testid="save-scenario">Save</button></form>}>
                <ComparisonView c={result.comparison} /></Section>
              <Section title="Scenario ledger" description={`Version used: ${result.analysis.version.selected?.label ?? "none"}${result.analysis.version.overridden ? " (manual override)" : ""}`}>
                <Ledger analysis={result.analysis} />
              </Section>
            </>
          )}
          <Section title={`Saved scenarios (${saved.length})`} description="Stored in your account; reopen them any time.">
            {saved.length === 0 ? <p className="text-sm text-muted">No saved scenarios yet. Run one and give it a name.</p> : (
              <ul className="divide-y divide-line" data-testid="saved-scenarios">
                {saved.map((s) => (
                  <li key={s.id} className="flex flex-wrap items-center gap-3 py-2.5 text-sm">
                    <span className="min-w-0 flex-1 font-medium text-ink">{s.name}</span>
                    <span className="num text-muted">base {inr(s.base_payable[0])} → <span className="text-ink">{inr(s.payable[0])}</span></span>
                    <button className="btn-ghost h-8 px-2 text-xs" onClick={() => { setHyp(s.hypotheticals); setResult(null); }}>Load inputs</button>
                    <button className="btn-ghost h-8 px-2 text-xs" onClick={async () => { await api.deleteScenario(bundle.claim.claim_id, s.id); setSaved(saved.filter((x) => x.id !== s.id)); }}>Delete</button>
                  </li>))}
              </ul>)}
          </Section>
          <Section title="Compare policy versions" description="Apply each documented version to this claim. Only one applies to the treatment date; others are shown as hypothetical alternatives."
            actions={<button className="btn-secondary text-xs" onClick={async () => setVcmp(await api.compareVersions(bundle.claim.claim_id))}>Run comparison</button>}>
            {!vcmp ? <p className="text-sm text-muted">Not run yet.</p> : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead><tr className="border-b border-line text-left text-[12px] font-semibold text-muted">
                    <th className="py-1.5 pr-3 font-medium">Version</th><th className="py-1.5 pr-3 font-medium">Effective</th>
                    <th className="py-1.5 pr-3 text-right font-medium">Est. payable</th><th className="py-1.5 pr-3 text-right font-medium">Out-of-pocket</th><th className="py-1.5 font-medium">Key differences</th></tr></thead>
                  <tbody>{vcmp.versions.map((v) => (
                    <tr key={v.version.version_id} className="border-b border-line align-top">
                      <td className="py-2 pr-3 font-medium">{v.version.label} {v.is_applicable ? <Tag tone="covered">Applies</Tag> : <Tag tone="partial">Hypothetical</Tag>}</td>
                      <td className="py-2 pr-3 text-xs text-muted num">{v.version.effective_from} → {v.version.effective_to}</td>
                      <td className="py-2 pr-3 text-right num"><Range low={v.summary.payable_low} high={v.summary.payable_high} /></td>
                      <td className="py-2 pr-3 text-right num"><Range low={v.summary.patient_low} high={v.summary.patient_high} /></td>
                      <td className="py-2 text-xs text-muted">{v.is_applicable ? "Current analysis" : v.comparison_vs_current.changed_items.slice(0, 3).map((c) => `${c.description}: ${c.reason}`).join(" · ")} {!v.is_applicable && `Δ payable ${inr(v.comparison_vs_current.payable_delta, { sign: true })}`}</td>
                    </tr>))}</tbody>
                </table>
              </div>
            )}
          </Section>
        </div>
      </div>
    </>
  );
}
