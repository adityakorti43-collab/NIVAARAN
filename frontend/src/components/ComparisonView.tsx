import { ArrowRight, TrendingDown, TrendingUp } from "lucide-react";
import { motion } from "motion/react";
import { cn, inr, STAGE_LABEL } from "../lib/format";
import type { Comparison } from "../lib/types";
import { StatusBadge, Tag } from "./ui";

function Delta({ v, invert = false }: { v: string; invert?: boolean }) {
  const n = Number(v);
  if (n === 0) return <span className="text-muted num">no change</span>;
  const good = invert ? n < 0 : n > 0;
  const Icon = n > 0 ? TrendingUp : TrendingDown;
  return <span className={cn("inline-flex items-center gap-1 font-semibold num", good ? "text-covered" : "text-excluded")}><Icon className="size-4" aria-hidden />{inr(v, { sign: true })}</span>;
}

export function ComparisonView({ c }: { c: Comparison }) {
  return (
    <div data-testid="comparison">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Tag tone={c.hypothetical ? "partial" : "neutral"}>{c.hypothetical ? "Hypothetical" : "Recorded change"}</Tag>
        <p className="text-sm font-medium text-ink">Cause: {c.cause}</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-lg bg-paper p-3">
          <p className="eyebrow">Estimated payable (definite)</p>
          <div className="mt-1.5 flex flex-wrap items-center gap-2 text-lg num">
            <span className="text-muted">{inr(c.payable_before[0])}</span><ArrowRight className="size-4 text-faint" aria-hidden />
            <motion.span key={c.payable_after[0]} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} className="font-semibold text-ink">{inr(c.payable_after[0])}</motion.span>
          </div>
          <Delta v={c.payable_delta} />
        </div>
        <div className="rounded-lg bg-paper p-3">
          <p className="eyebrow">Potential out-of-pocket (maximum)</p>
          <div className="mt-1.5 flex flex-wrap items-center gap-2 text-lg num">
            <span className="text-muted">{inr(c.patient_before[1])}</span><ArrowRight className="size-4 text-faint" aria-hidden />
            <span className="font-semibold text-ink">{inr(c.patient_after[1])}</span>
          </div>
          <Delta v={c.patient_delta} invert />
        </div>
      </div>
      {(c.previous_version !== c.updated_version) && (
        <p className="mt-3 text-sm"><span className="text-muted">Policy version:</span> {c.previous_version} <ArrowRight className="inline size-3.5" aria-hidden /> <strong>{c.updated_version}</strong></p>
      )}
      <div className="mt-3">
        <p className="eyebrow mb-1.5">Why it changed</p>
        <ul className="list-disc space-y-1 pl-5 text-sm text-text">{c.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
      </div>
      {(c.changed_clauses.added.length > 0 || c.changed_clauses.removed.length > 0) && (
        <p className="mt-3 text-sm text-text">
          Clauses now cited: {c.changed_clauses.added.map((s) => <Tag key={s} tone="covered" className="mr-1">+ {s}</Tag>)}
          {c.changed_clauses.removed.length > 0 && <> no longer cited: {c.changed_clauses.removed.map((s) => <Tag key={s} tone="excluded" className="mr-1">− {s}</Tag>)}</>}
        </p>
      )}
      {c.changed_items.length > 0 && (
        <div className="mt-4 overflow-x-auto">
          <p className="eyebrow mb-1.5">Changed bill items ({c.changed_items.length})</p>
          <table className="w-full text-sm">
            <thead><tr className="border-b border-line text-left text-[12px] font-semibold text-muted">
              <th className="py-1.5 pr-3 font-medium">Item</th><th className="py-1.5 pr-3 font-medium">Status</th>
              <th className="py-1.5 pr-3 text-right font-medium">Before</th><th className="py-1.5 pr-3 text-right font-medium">After</th>
              <th className="py-1.5 font-medium">Reason</th></tr></thead>
            <tbody>
              {c.changed_items.map((i) => (
                <tr key={i.item_id} className="border-b border-line align-top">
                  <td className="py-2 pr-3 font-medium">{i.description}</td>
                  <td className="py-2 pr-3">
                    {i.status_before && i.status_after && i.status_before !== i.status_after ? (
                      <div className="flex flex-col gap-1"><StatusBadge status={i.status_before} short /><StatusBadge status={i.status_after} short /></div>
                    ) : i.status_after ? <StatusBadge status={i.status_after} short /> : <Tag>{i.change}</Tag>}
                  </td>
                  <td className="py-2 pr-3 text-right num text-muted">{inr(i.payable_before)}</td>
                  <td className="py-2 pr-3 text-right num font-medium">{inr(i.payable_after)}</td>
                  <td className="py-2 text-xs text-muted">{i.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {c.changed_steps.length > 0 && (
        <div className="mt-4">
          <p className="eyebrow mb-1.5">Changed calculation steps</p>
          <ul className="space-y-1.5 text-sm">
            {c.changed_steps.map((s) => (
              <li key={s.stage} className="rounded-lg border border-line p-2">
                <span className="font-medium">{STAGE_LABEL[s.stage] ?? s.stage}:</span>{" "}
                {s.before && <span className="text-muted line-through decoration-faint">{s.before}</span>} {s.before && <ArrowRight className="inline size-3.5" aria-hidden />} {s.after}
                <span className="ml-2 text-xs text-muted num">({s.amount_before ? inr(s.amount_before) : "—"} → {inr(s.amount_after)})</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
