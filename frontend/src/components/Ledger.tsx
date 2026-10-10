import { ChevronRight, Filter } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { Fragment, useMemo, useState } from "react";
import { cn, fmtDate, inr, STATUS_META, subMoney } from "../lib/format";
import { useApp } from "../lib/store";
import type { Analysis, ItemStatus, LedgerRow } from "../lib/types";
import { ClauseRef, EvidenceCard, StatusBadge, Tag } from "./ui";

function PayableCell({ r }: { r: LedgerRow }) {
  if (r.eligible_amount === null) {
    return (
      <div className="text-right">
        <p className="num text-sm text-muted">{inr("0.00")} – {inr(r.payable_high)}</p>
        <p className="text-[11px] text-faint">unresolved</p>
      </div>
    );
  }
  return <p className="num text-right text-sm font-semibold text-ink">{inr(r.payable_low)}</p>;
}

export function RowDetail({ r, analysis }: { r: LedgerRow; analysis: Analysis }) {
  const decisive = new Set(r.supporting_clause_ids);
  const adjustments = analysis.adjustments.filter((a) => a.item_id === r.item_id && a.adjustment_id.startsWith(r.eligible_amount === null ? "high" : "low"));
  const [showAll, setShowAll] = useState(false);
  const evidence = showAll ? r.evidence : r.evidence.filter((e) => decisive.has(e.clause_id) || !["irrelevant", "inapplicable"].includes(e.relation));
  const hidden = r.evidence.length - evidence.length;
  return (
    <div className="grid gap-5 lg:grid-cols-[1.25fr_1fr]">
      <div>
        <p className="eyebrow mb-2">Evidence</p>
        <p className="mb-3 text-sm text-text leading-relaxed">{r.explanation}</p>
        <div className="space-y-2">
          {evidence.map((e) => <EvidenceCard key={e.clause_id} e={e} decisive={decisive.has(e.clause_id)} />)}
          {evidence.length === 0 && <p className="text-sm text-muted">No clause in the applicable version addresses this item.</p>}
        </div>
        {hidden > 0 && (
          <button className="btn-ghost mt-2 px-0 text-xs" onClick={() => setShowAll(true)}>
            Show {hidden} rejected candidate{hidden > 1 ? "s" : ""} (retrieved by similarity but not evidence)
          </button>
        )}
      </div>
      <div className="space-y-4">
        <div>
          <p className="eyebrow mb-2">Item details</p>
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
            <dt className="text-muted">Original</dt><dd className="text-text">{r.original_description}</dd>
            <dt className="text-muted">Normalised</dt><dd className="text-text">{r.normalized_description}</dd>
            <dt className="text-muted">Category</dt><dd>{r.category}</dd>
            <dt className="text-muted">Service date</dt><dd className="num">{fmtDate(r.service_date)}</dd>
            <dt className="text-muted">Quantity</dt><dd className="num">{r.quantity}</dd>
            <dt className="text-muted">Policy version</dt><dd>{analysis.version.selected?.label ?? "—"}</dd>
            {r.applicable_limit && (<><dt className="text-muted">Limit applied</dt><dd>{r.applicable_limit}</dd></>)}
            <dt className="text-muted">Evidence quality</dt><dd className="capitalize">{r.evidence_quality}</dd>
          </dl>
        </div>
        <div>
          <p className="eyebrow mb-2">Calculation trace {r.eligible_amount === null && <span className="normal-case tracking-normal text-faint">(upper bound — if resolved favourably)</span>}</p>
          <ol className="space-y-1.5 text-sm">
            <li className="flex justify-between gap-3"><span className="text-muted">Claimed (as billed)</span><span className="num">{inr(r.claimed_amount)}</span></li>
            {adjustments.map((a) => (
              <li key={a.adjustment_id} className="flex justify-between gap-3">
                <span className="text-text">{a.description} {a.clause_ids.map((c) => <ClauseRef key={c} id={c} />)}{a.hypothetical && <Tag tone="partial" className="ml-1">Hypothetical</Tag>}</span>
                <span className="num whitespace-nowrap text-excluded">−{inr(a.amount, { symbol: true })}</span>
              </li>
            ))}
            <li className="flex justify-between gap-3 border-t border-line pt-1.5 font-semibold">
              <span>Estimated payable</span><span className="num">{inr(r.eligible_amount === null ? r.payable_high : r.payable_low)}</span>
            </li>
          </ol>
        </div>
        {(r.missing_information.length > 0 || r.review_reasons.length > 0) && (
          <div className="rounded-lg border border-review/25 bg-review-bg p-3 text-sm">
            <p className="font-medium text-review">Needs review</p>
            <ul className="mt-1 list-disc pl-5 text-text">
              {r.missing_information.map((m) => <li key={m}>Missing: {m}</li>)}
              {r.review_reasons.map((m) => <li key={m}>{m}</li>)}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

export function Ledger({ analysis, initialOpen }: { analysis: Analysis; initialOpen?: string }) {
  const { setSelection } = useApp();
  const [open, setOpenRaw] = useState<string | null>(initialOpen ?? null);
  const setOpen = (id: string | null) => { setOpenRaw(id); setSelection(id ? { item_id: id } : {}); };
  const [filter, setFilter] = useState<ItemStatus | "">("");
  const rows = useMemo(() => analysis.rows.filter((r) => !filter || r.status === filter), [analysis.rows, filter]);
  const statuses = [...new Set(analysis.rows.map((r) => r.status))];
  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-1.5">
        <Filter className="size-3.5 text-faint" aria-hidden />
        <button onClick={() => setFilter("")} className={cn("rounded-full px-2.5 py-1 text-xs", !filter ? "chip-on" : "bg-paper text-muted hover:text-text")}>All ({analysis.rows.length})</button>
        {statuses.map((s) => (
          <button key={s} onClick={() => setFilter(s)} aria-pressed={filter === s}
            className={cn("rounded-full px-2.5 py-1 text-xs", filter === s ? "chip-on" : "bg-paper text-muted hover:text-text")}>
            {STATUS_META[s].short} ({analysis.rows.filter((r) => r.status === s).length})
          </button>
        ))}
      </div>
      {/* Desktop table */}
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full text-sm" data-testid="ledger">
          <thead>
            <tr className="border-b border-line text-left text-[12px] font-semibold text-muted">
              <th className="w-8 py-2" />
              <th className="py-2 pr-3 font-medium">Bill item</th>
              <th className="py-2 pr-3 font-medium">Status</th>
              <th className="py-2 pr-3 text-right font-medium">Claimed</th>
              <th className="py-2 pr-3 text-right font-medium">Eligible</th>
              <th className="py-2 pr-3 text-right font-medium">Deductions</th>
              <th className="py-2 pr-3 text-right font-medium">Est. payable</th>
              <th className="py-2 font-medium">Clause</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const isOpen = open === r.item_id;
              const deductions = subMoney(r.claimed_amount, r.payable_low);
              return (
                <Fragment key={r.item_id}>
                  <tr className={cn("border-b border-line align-top hover:bg-paper/70 cursor-pointer", isOpen && "bg-paper/70", r.hypothetical && "bg-partial-bg/40")}
                    onClick={() => setOpen(isOpen ? null : r.item_id)} data-testid={`row-${r.line_no}`}>
                    <td className="py-3 pl-1">
                      <button aria-expanded={isOpen} aria-label={`${isOpen ? "Collapse" : "Expand"} ${r.original_description}`} className="rounded p-0.5 text-faint hover:text-text" onClick={(e) => { e.stopPropagation(); setOpen(isOpen ? null : r.item_id); }}>
                        <ChevronRight className={cn("size-4 transition-transform", isOpen && "rotate-90")} />
                      </button>
                    </td>
                    <td className="py-3 pr-3">
                      <p className="font-medium text-text">{r.original_description}</p>
                      <p className="text-xs text-muted">{r.category}{r.manual_review && <span className="ml-1.5 text-review">· review</span>}</p>
                    </td>
                    <td className="py-3 pr-3"><StatusBadge status={r.status} /></td>
                    <td className="py-3 pr-3 text-right num">{inr(r.claimed_amount)}</td>
                    <td className="py-3 pr-3 text-right num text-muted">{r.eligible_amount === null ? "—" : inr(r.eligible_amount)}</td>
                    <td className="py-3 pr-3 text-right num text-muted" title="Exclusions, limits, deductible share and co-payment share">{r.eligible_amount === null ? "—" : inr(deductions)}</td>
                    <td className="py-3 pr-3"><PayableCell r={r} /></td>
                    <td className="py-3"><div className="flex flex-wrap gap-1">{r.supporting_clause_ids.slice(0, 3).map((c) => <ClauseRef key={c} id={c} />)}{r.supporting_clause_ids.length === 0 && <span className="text-xs text-faint">none</span>}</div></td>
                  </tr>
                  <AnimatePresence initial={false}>
                    {isOpen && (
                      <tr className="border-b border-line bg-paper/40">
                        <td colSpan={8} className="p-0">
                          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
                            <div className="p-4"><RowDetail r={r} analysis={analysis} /></div>
                          </motion.div>
                        </td>
                      </tr>
                    )}
                  </AnimatePresence>
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
      {/* Mobile cards */}
      <ul className="space-y-2 md:hidden">
        {rows.map((r) => (
          <li key={r.item_id} className="rounded-lg border border-line">
            <button className="w-full p-3 text-left" aria-expanded={open === r.item_id} onClick={() => setOpen(open === r.item_id ? null : r.item_id)}>
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm font-medium text-text">{r.original_description}</p>
                <StatusBadge status={r.status} short />
              </div>
              <div className="mt-2 grid grid-cols-2 gap-1 text-xs">
                <span className="text-muted">Claimed</span><span className="num text-right">{inr(r.claimed_amount)}</span>
                <span className="text-muted">Est. payable</span><span className="num text-right font-semibold">{r.eligible_amount === null ? `0 – ${inr(r.payable_high)}` : inr(r.payable_low)}</span>
              </div>
            </button>
            {open === r.item_id && <div className="border-t border-line p-3"><RowDetail r={r} analysis={analysis} /></div>}
          </li>
        ))}
      </ul>
      <p className="mt-3 text-xs text-faint">Claimed amounts are exactly as billed. "Est. payable" is an estimate for resolved items; unresolved items show 0 to the amount payable only if resolved favourably.</p>
    </div>
  );
}
