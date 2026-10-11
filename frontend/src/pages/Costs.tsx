import { FlaskConical } from "lucide-react";
import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ErrorBar, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { NeedClaim } from "../components/NeedClaim";
import { ErrorNote, HypotheticalBanner, PageHeader, Range, Section, Spinner, StatusBadge, Tag } from "../components/ui";
import { api } from "../lib/api";
import { cn, inr, num } from "../lib/format";
import type { Analysis, ClaimBundle } from "../lib/types";

export default function Costs() {
  return (
    <div>
      <PageHeader eyebrow="Treatment costs" title="What might a treatment cost, and what might the policy pay?"
        description="Nivaaran does not have live hospital prices. The cost table below is illustrative synthetic data, clearly labelled; enter your own quotation for a real analysis. Policy outcomes are computed by the same rules engine as real claims." />
      <NeedClaim>{(b) => <CostLab bundle={b} />}</NeedClaim>
    </div>
  );
}

function CostLab({ bundle }: { bundle: ClaimBundle & { analysis: Analysis } }) {
  const [ds, setDs] = useState<any>(null);
  const [proc, setProc] = useState("lap_appendicectomy");
  const [ht, setHt] = useState("private");
  const [tier, setTier] = useState("tier1");
  const [pct, setPct] = useState("median");
  const [userTotal, setUserTotal] = useState("");
  const [roomDays, setRoomDays] = useState("");
  const [res, setRes] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { api.costs().then(setDs).catch((e) => setErr(e.message)); }, []);
  if (!ds) return err ? <ErrorNote error={err} /> : <Spinner />;
  const p = ds.procedures.find((x: any) => x.key === proc);
  const chart = Object.entries(p.ranges[ht] as Record<string, any>).map(([t, r]) => ({ tier: t.replace("tier", "Tier "), median: num(r.median), err: [num(r.median) - num(r.p25), num(r.p75) - num(r.median)] }));
  const an: Analysis | undefined = res?.analysis;

  return (
    <div className="space-y-5">
      <div role="note" className="flex items-start gap-2.5 rounded-lg border border-conditional/25 bg-conditional-bg px-3.5 py-3 text-sm text-conditional">
        <FlaskConical className="mt-0.5 size-4 shrink-0" aria-hidden />
        <div><p className="font-semibold">{ds.dataset.name} — {ds.dataset.data_type.replace("_", " ")}</p>
          <p className="mt-0.5">{ds.dataset.source}</p>
          <p className="mt-1 text-xs">Units: {ds.dataset.units}. Coverage: {ds.dataset.geographic_coverage}. Collected: {ds.dataset.collection_date}.</p>
          <ul className="mt-1 list-disc pl-5 text-xs">{ds.dataset.limitations.map((l: string) => <li key={l}>{l}</li>)}</ul></div>
      </div>
      <div className="grid gap-5 xl:grid-cols-[380px_1fr]">
        <Section title="Scenario">
          <div className="space-y-3">
            <label className="block"><span className="label">Treatment</span>
              <select className="input" value={proc} onChange={(e) => setProc(e.target.value)}>{ds.procedures.map((x: any) => <option key={x.key} value={x.key}>{x.name}</option>)}</select></label>
            <div className="grid grid-cols-2 gap-3">
              <label><span className="label">Hospital type</span>
                <select className="input" value={ht} onChange={(e) => setHt(e.target.value)}>{Object.entries(ds.hospital_types).map(([k, v]: any) => <option key={k} value={k}>{v.label.replace(" (illustrative)", "")}</option>)}</select></label>
              <label><span className="label">City tier</span>
                <select className="input" value={tier} onChange={(e) => setTier(e.target.value)}>{["tier1", "tier2", "tier3"].map((t) => <option key={t} value={t}>{t.replace("tier", "Tier ")}</option>)}</select></label>
            </div>
            <fieldset><legend className="label">Illustrative cost point</legend>
              <div className="flex rounded-lg border border-line-2 p-0.5">{["p25", "median", "p75"].map((x) => (
                <button key={x} type="button" onClick={() => setPct(x)} className={cn("flex-1 rounded-md px-2 py-1 text-xs", pct === x ? "chip-on" : "text-muted")}>{x === "median" ? "Median" : x.toUpperCase()}</button>))}</div></fieldset>
            <label className="block"><span className="label">Or enter your own total (₹)</span>
              <input className="input num" inputMode="decimal" placeholder="e.g. a hospital quotation" value={userTotal} onChange={(e) => setUserTotal(e.target.value)} />
              <span className="mt-1 block text-xs text-faint">User-provided amounts replace the illustrative value.</span></label>
            <label className="block"><span className="label">Room days</span>
              <input className="input num" inputMode="numeric" placeholder={String(p.typical_room_days)} value={roomDays} onChange={(e) => setRoomDays(e.target.value)} /></label>
            <ErrorNote error={err} />
            <button className="btn-primary w-full" disabled={busy} onClick={async () => {
              setBusy(true); setErr(null);
              try {
                setRes(await api.costEstimate({ procedure: proc, claim_id: bundle.claim.claim_id, hospital_type: ht, tier, percentile: pct,
                  user_total: userTotal || null, room_days: roomDays ? Number(roomDays) : null }));
              } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
            }}>{busy ? <Spinner label="Estimating…" /> : "Estimate under my policy"}</button>
            <p className="text-xs text-faint">Uses the policy and endorsements of the active claim, at its treatment date.</p>
          </div>
        </Section>
        <div className="space-y-5 min-w-0">
          <Section title={`Illustrative cost range — ${p.name}`} description={`${ds.hospital_types[ht].label}. Bars show the illustrative median; whiskers span P25–P75. Synthetic values.`}>
            <div className="h-56" role="img" aria-label="Illustrative cost range by city tier">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chart} margin={{ left: 8, right: 8, top: 8 }}>
                  <CartesianGrid vertical={false} stroke="#e3ddcf" />
                  <XAxis dataKey="tier" tick={{ fontSize: 12, fill: "#6c7068" }} axisLine={{ stroke: "#d3cab6" }} tickLine={false} />
                  <YAxis tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`} tick={{ fontSize: 11, fill: "#6c7068" }} axisLine={false} tickLine={false} width={52} />
                  <Tooltip formatter={(v) => [`₹${Number(v).toLocaleString("en-IN")}`, "Illustrative median"]} />
                  <Bar dataKey="median" fill="#142d27" fillOpacity={0.9} radius={[2, 2, 0, 0]} barSize={46}><ErrorBar dataKey="err" width={10} stroke="#b69a62" /></Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <table className="mt-3 w-full text-sm">
              <thead><tr className="text-left text-[12px] font-semibold text-muted"><th className="py-1 font-medium">Component</th><th className="py-1 text-right font-medium">Share of total</th></tr></thead>
              <tbody>{p.components.map(([n, s]: [string, string]) => <tr key={n} className="border-t border-line"><td className="py-1">{n}</td><td className="py-1 text-right num">{(Number(s) * 100).toFixed(0)}%</td></tr>)}</tbody>
            </table>
          </Section>
          {an && (
            <>
              <HypotheticalBanner>{res.label}. Total {inr(res.total)} split by the component shares above; evaluated under '{an.version.selected?.label}'.</HypotheticalBanner>
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="card p-4"><p className="eyebrow">Hypothetical cost</p><p className="mt-2 text-xl font-semibold num">{inr(an.summary.total_billed)}</p></div>
                <div className="card p-4"><p className="eyebrow">Estimated payable</p><p className="mt-2 text-xl font-semibold num text-covered"><Range low={an.summary.payable_low} high={an.summary.payable_high} /></p></div>
                <div className="card p-4"><p className="eyebrow">Potential exposure</p><p className="mt-2 text-xl font-semibold num"><Range low={an.summary.patient_low} high={an.summary.patient_high} /></p></div>
              </div>
              <Section title="Components vs policy limits">
                <ul className="divide-y divide-line text-sm">
                  {an.rows.map((r) => (
                    <li key={r.item_id} className="flex flex-wrap items-center gap-2 py-2">
                      <span className="min-w-0 flex-1">{r.original_description}{r.applicable_limit && <span className="block text-xs text-muted">Limit: {r.applicable_limit}</span>}</span>
                      <StatusBadge status={r.status} short />
                      <span className="w-28 text-right num">{inr(r.claimed_amount)}</span>
                      <span className="w-32 text-right num font-medium">{r.eligible_amount === null ? `0 – ${inr(r.payable_high)}` : inr(r.payable_low)}</span>
                    </li>))}
                </ul>
                <p className="mt-2 text-xs text-faint"><Tag tone="partial">Hypothetical</Tag> Not a quotation and not an insurer decision.</p>
              </Section>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
