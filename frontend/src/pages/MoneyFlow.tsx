import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { NeedClaim } from "../components/NeedClaim";
import { ClauseRef, Disclaimer, PageHeader, Section, SyntheticBanner } from "../components/ui";
import { cn, inr, num, STAGE_LABEL, subMoney } from "../lib/format";
import type { Analysis } from "../lib/types";

export default function MoneyFlow() {
  return (
    <div>
      <PageHeader eyebrow="Money flow" title="From billed amount to estimated payable"
        description="Start with the full bill and watch each deduction come off, in the order your policy applies them. Each bar is one step." />
      <NeedClaim>{(b) => <Flow a={b.analysis} />}</NeedClaim>
    </div>
  );
}

function Flow({ a }: { a: Analysis }) {
  const [mode, setMode] = useState<"low" | "high">("low");
  const trace = mode === "low" ? a.trace_low : a.trace_high;
  const data = useMemo(() => {
    const out: { name: string; base: number; value: number; kind: string; before: string; after: string; delta: string }[] = [];
    trace.forEach((s) => {
      if (s.stage === "billed") out.push({ name: "Billed", base: 0, value: num(s.amount_after), kind: "total", before: s.amount_before, after: s.amount_after, delta: "0.00" });
      else if (s.stage === "estimated_payable") out.push({ name: "Est. payable", base: 0, value: num(s.amount_after), kind: "payable", before: s.amount_before, after: s.amount_after, delta: "0.00" });
      else {
        const d = subMoney(s.amount_before, s.amount_after);
        out.push({ name: STAGE_LABEL[s.stage] ?? s.stage, base: num(s.amount_after), value: num(d), kind: "reduction", before: s.amount_before, after: s.amount_after, delta: d });
      }
    });
    const billed = trace[0]?.amount_after ?? "0";
    const payable = trace[trace.length - 1]?.amount_after ?? "0";
    out.push({ name: "Out-of-pocket", base: 0, value: num(subMoney(billed, payable)), kind: "patient", before: billed, after: payable, delta: subMoney(billed, payable) });
    return out;
  }, [trace]);
  const color = { total: "#222521", reduction: "#a2463a", payable: "#2e6b50", patient: "#b69a62" } as Record<string, string>;
  const stageAdjust = (stage: string) => a.adjustments.filter((x) => x.adjustment_id.startsWith(mode) && (x.stage === stage || (stage === "exclusion" && x.stage === "unresolved_hold")));
  return (
    <>
      <SyntheticBanner show={a.synthetic} />
      <Section title="Waterfall" description={mode === "low" ? "Definite case: unresolved items are held out, not assumed payable." : "Upper bound: as if every unresolved item were resolved favourably."}
        actions={<div className="flex rounded-lg border border-line-2 p-0.5 text-xs">
          <button className={cn("rounded-md px-2.5 py-1", mode === "low" ? "chip-on" : "text-muted")} onClick={() => setMode("low")}>Definite</button>
          <button className={cn("rounded-md px-2.5 py-1", mode === "high" ? "chip-on" : "text-muted")} onClick={() => setMode("high")}>Upper bound</button>
        </div>}>
        <div className="h-[340px]" role="img" aria-label="Waterfall chart of the claim calculation">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 10, right: 8, left: 8, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke="#e3ddcf" />
              <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#6c7068" }} interval={0} tickLine={false} axisLine={{ stroke: "#d3cab6" }} />
              <YAxis tick={{ fontSize: 11, fill: "#6c7068" }} tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`} width={52} axisLine={false} tickLine={false} />
              <Tooltip cursor={{ fill: "rgba(34,37,33,0.04)" }} content={({ active, payload }) => {
                if (!active || !payload?.length) return null;
                const d = payload[0].payload as (typeof data)[number];
                return (<div className="card px-3 py-2 text-xs shadow-sm"><p className="font-semibold text-ink">{d.name}</p>
                  {d.kind === "reduction" ? <p className="num">{inr(d.before)} − {inr(d.delta)} = {inr(d.after)}</p> : <p className="num">{inr(d.kind === "patient" ? d.delta : d.after)}</p>}</div>);
              }} />
              <Bar dataKey="base" stackId="w" fill="transparent" isAnimationActive={false} />
              <Bar dataKey="value" stackId="w" radius={[3, 3, 0, 0]}>
                {data.map((d) => <Cell key={d.name} fill={color[d.kind]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Section>
      <Section title="Stage by stage" className="mt-5" description="Every amount below comes from the calculation trace and its tracked adjustments.">
        <ol className="space-y-3">
          {trace.map((s) => {
            const adj = stageAdjust(s.stage);
            return (
              <li key={s.step_no} className="rounded-lg border border-line p-3">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <p className="text-sm font-semibold text-ink">{s.step_no}. {STAGE_LABEL[s.stage] ?? s.stage}</p>
                  <p className="text-sm num">{s.amount_before !== s.amount_after && <span className="text-excluded">−{inr(subMoney(s.amount_before, s.amount_after))} · </span>}<strong>{inr(s.amount_after)}</strong></p>
                </div>
                <p className="mt-0.5 text-xs text-muted">{s.description} {s.clause_ids.map((c) => <ClauseRef key={c} id={c} />)}</p>
                {adj.length > 0 && (
                  <details className="mt-2"><summary className="cursor-pointer text-xs text-muted">{adj.length} adjustment(s)</summary>
                    <ul className="mt-1.5 space-y-1 text-xs">
                      {adj.map((x) => <li key={x.adjustment_id} className="flex justify-between gap-3"><span>{x.description}</span><span className="num whitespace-nowrap">{inr(x.amount)}</span></li>)}
                    </ul></details>
                )}
              </li>
            );
          })}
        </ol>
        <Disclaimer className="mt-4" />
      </Section>
    </>
  );
}
